import os
from datetime import datetime, timedelta
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort,
    jsonify,
    current_app,
)
from flask_login import login_required, current_user
from sqlalchemy import func
from app import db, csrf
from app.models.user import User
from app.models.scan import Scan
from app.models.product import Product, ReferenceImage
from app.models.audit import AdminActivity
from app.forms.product_forms import ProductForm, ReferenceImageUploadForm
from app.utils.decorators import admin_required
from app.utils.file_handlers import validate_and_save_image, delete_file_safe

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.before_request
@login_required
@admin_required
def admin_security_check():
    """Ensure all admin endpoints require authentication and admin privileges."""
    pass


# ---------------------------------------------------------------------------
# Helper: Aggregate complete system analytics for Admin Dashboard
# ---------------------------------------------------------------------------

def _get_system_analytics():
    """Calculate system-wide statistics for the admin dashboard and analytics."""
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    total_products = Product.query.count()
    total_reference_images = ReferenceImage.query.count()
    total_scans = Scan.query.count()

    # Status distribution
    status_counts_raw = (
        db.session.query(Scan.assessment_status, func.count(Scan.id))
        .group_by(Scan.assessment_status)
        .all()
    )
    status_map = {
        "HIGH_SIMILARITY": 0,
        "MODERATE_SIMILARITY": 0,
        "LOW_SIMILARITY": 0,
        "INSUFFICIENT_DATA": 0,
    }
    for status, count in status_counts_raw:
        if status in status_map:
            status_map[status] = count

    # Category distribution of scans
    category_counts_raw = (
        db.session.query(Product.category, func.count(Scan.id))
        .join(Scan, Scan.matched_product_id == Product.id)
        .group_by(Product.category)
        .all()
    )
    scan_category_map = {cat: cnt for cat, cnt in category_counts_raw}

    # Product category distribution
    prod_cat_raw = (
        db.session.query(Product.category, func.count(Product.id))
        .group_by(Product.category)
        .all()
    )
    prod_category_map = {cat: cnt for cat, cnt in prod_cat_raw}

    # Average processing time
    avg_latency = (
        db.session.query(func.avg(Scan.processing_time_ms)).scalar() or 0
    )

    # Scans over last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    daily_scans_raw = (
        db.session.query(
            func.date(Scan.scanned_at).label("day"),
            func.count(Scan.id).label("cnt"),
        )
        .filter(Scan.scanned_at >= thirty_days_ago)
        .group_by(func.date(Scan.scanned_at))
        .order_by(func.date(Scan.scanned_at))
        .all()
    )
    daily_scans = {str(row.day): row.cnt for row in daily_scans_raw}

    # Products with zero reference images
    products_needing_refs = (
        Product.query.outerjoin(ReferenceImage)
        .group_by(Product.id)
        .having(func.count(ReferenceImage.id) == 0)
        .all()
    )

    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_products": total_products,
        "total_reference_images": total_reference_images,
        "total_scans": total_scans,
        "avg_latency_ms": round(avg_latency, 1),
        "status_map": status_map,
        "scan_category_map": scan_category_map,
        "prod_category_map": prod_category_map,
        "daily_scans": daily_scans,
        "products_needing_refs_count": len(products_needing_refs),
        "products_needing_refs": products_needing_refs,
    }


# ---------------------------------------------------------------------------
# HTML Views for Admin Dashboard, Users & Analytics
# ---------------------------------------------------------------------------


@admin_bp.route("")
@admin_bp.route("/")
@admin_bp.route("/dashboard")
def dashboard():
    """Admin dashboard featuring system KPIs, recent scans, and activity logs."""
    stats = _get_system_analytics()
    recent_scans = (
        Scan.query.order_by(Scan.scanned_at.desc()).limit(8).all()
    )
    recent_activities = (
        AdminActivity.query.order_by(AdminActivity.created_at.desc()).limit(8).all()
    )

    return render_template(
        "admin/dashboard.html",
        stats=stats,
        recent_scans=recent_scans,
        recent_activities=recent_activities,
    )


@admin_bp.route("/users")
def list_users():
    """List registered users with search, role filtering, and status controls."""
    role_filter = request.args.get("role", "").strip()
    status_filter = request.args.get("status", "").strip()
    search_query = request.args.get("q", "").strip()

    query = User.query

    if role_filter:
        query = query.filter_by(role=role_filter)
    if status_filter == "active":
        query = query.filter_by(is_active=True)
    elif status_filter == "inactive":
        query = query.filter_by(is_active=False)

    if search_query:
        pattern = f"%{search_query}%"
        query = query.filter(
            (User.username.ilike(pattern))
            | (User.email.ilike(pattern))
            | (User.full_name.ilike(pattern))
        )

    users = query.order_by(User.created_at.desc()).all()

    return render_template(
        "admin/users.html",
        users=users,
        role_filter=role_filter,
        status_filter=status_filter,
        search_query=search_query,
    )


@admin_bp.route("/users/<user_id>/toggle-status", methods=["POST"])
def toggle_user_status(user_id):
    """Toggle a user's active/suspended status (cannot deactivate self)."""
    user = db.session.get(User, user_id)
    if not user:
        abort(404)

    if user.id == current_user.id:
        flash("Action denied: You cannot suspend your own administrative account.", "danger")
        return redirect(url_for("admin.list_users"))

    user.is_active = not user.is_active
    action_type = "ACTIVATE_USER" if user.is_active else "DEACTIVATE_USER"
    status_str = "activated" if user.is_active else "suspended"

    log = AdminActivity(
        admin_id=current_user.id,
        action=action_type,
        details=f"{action_type.replace('_', ' ').title()}: User '{user.username}' ({user.email}).",
        ip_address=request.remote_addr,
    )
    db.session.add(log)
    db.session.commit()

    flash(f"User account '{user.username}' has been {status_str}.", "info")
    return redirect(url_for("admin.list_users"))


@admin_bp.route("/users/<user_id>/change-role", methods=["POST"])
def change_user_role(user_id):
    """Promote or demote a user account role (cannot change own role)."""
    user = db.session.get(User, user_id)
    if not user:
        abort(404)

    if user.id == current_user.id:
        flash("Action denied: You cannot modify your own administrative role.", "danger")
        return redirect(url_for("admin.list_users"))

    new_role = request.form.get("role", "").strip()
    if new_role not in ["user", "admin"]:
        flash("Invalid role specified.", "warning")
        return redirect(url_for("admin.list_users"))

    old_role = user.role
    user.role = new_role

    log = AdminActivity(
        admin_id=current_user.id,
        action="CHANGE_USER_ROLE",
        details=f"Changed role for '{user.username}' from '{old_role}' to '{new_role}'.",
        ip_address=request.remote_addr,
    )
    db.session.add(log)
    db.session.commit()

    flash(f"User '{user.username}' role updated to '{new_role}'.", "success")
    return redirect(url_for("admin.list_users"))


@admin_bp.route("/analytics")
def analytics():
    """System analytics and audit logs page."""
    stats = _get_system_analytics()
    audit_logs = (
        AdminActivity.query.order_by(AdminActivity.created_at.desc()).limit(50).all()
    )

    return render_template(
        "admin/analytics.html",
        stats=stats,
        audit_logs=audit_logs,
    )


# ---------------------------------------------------------------------------
# HTML Views for Product & Reference Image Management
# ---------------------------------------------------------------------------


@admin_bp.route("/products")
def list_products():
    """List all verified reference products with search and category filters."""
    category_filter = request.args.get("category", "").strip()
    search_query = request.args.get("q", "").strip()

    query = Product.query

    if category_filter:
        query = query.filter_by(category=category_filter)
    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter(
            (Product.product_name.ilike(search_pattern))
            | (Product.brand.ilike(search_pattern))
            | (Product.sku_or_upc.ilike(search_pattern))
        )

    products = query.order_by(Product.created_at.desc()).all()

    categories = [
        "Electronics",
        "Cosmetics",
        "Clothing",
        "Personal Care",
        "Packaged Goods",
    ]

    return render_template(
        "admin/products.html",
        products=products,
        categories=categories,
        current_category=category_filter,
        search_query=search_query,
    )


@admin_bp.route("/products/new", methods=["GET", "POST"])
def create_product():
    """Add a new genuine reference product with multiple reference images."""
    form = ProductForm()

    if form.validate_on_submit():
        product = Product(
            product_name=form.product_name.data.strip(),
            brand=form.brand.data.strip(),
            category=form.category.data,
            description=form.description.data.strip() if form.description.data else None,
            sku_or_upc=form.sku_or_upc.data.strip() if form.sku_or_upc.data else None,
        )
        db.session.add(product)
        db.session.flush()  # Generates product.id before adding images

        # Handle multiple reference image uploads
        uploaded_files = request.files.getlist("images")
        saved_count = 0
        error_count = 0

        ref_dir = current_app.config["REFERENCE_UPLOAD_DIR"]

        for file_storage in uploaded_files:
            if file_storage and file_storage.filename != "":
                success, result, orig_name = validate_and_save_image(file_storage, ref_dir)
                if success:
                    ref_image = ReferenceImage(
                        product_id=product.id,
                        image_path=f"references/{result}",
                        angle_or_view=form.angle_or_view.data,
                        verification_status="verified",
                    )
                    db.session.add(ref_image)
                    saved_count += 1
                else:
                    error_count += 1
                    flash(f"Error saving {orig_name}: {result}", "warning")

        # Log admin activity
        log = AdminActivity(
            admin_id=current_user.id,
            action="CREATE_PRODUCT",
            details=f"Created product '{product.product_name}' by '{product.brand}' with {saved_count} verified images.",
            ip_address=request.remote_addr,
        )
        db.session.add(log)
        db.session.commit()

        flash(
            f"Product '{product.product_name}' added successfully with {saved_count} reference images.",
            "success",
        )
        return redirect(url_for("admin.view_product", product_id=product.id))

    return render_template("admin/product_form.html", form=form, title="Add New Product")


@admin_bp.route("/products/<product_id>")
def view_product(product_id):
    """View product details, reference image gallery, and multi-angle upload form."""
    product = db.session.get(Product, product_id)
    if not product:
        abort(404)

    image_form = ReferenceImageUploadForm()
    return render_template(
        "admin/product_detail.html",
        product=product,
        image_form=image_form,
    )


@admin_bp.route("/products/<product_id>/edit", methods=["GET", "POST"])
def edit_product(product_id):
    """Update metadata for an existing product."""
    product = db.session.get(Product, product_id)
    if not product:
        abort(404)

    form = ProductForm(obj=product)

    if form.validate_on_submit():
        product.product_name = form.product_name.data.strip()
        product.brand = form.brand.data.strip()
        product.category = form.category.data
        product.description = form.description.data.strip() if form.description.data else None
        product.sku_or_upc = form.sku_or_upc.data.strip() if form.sku_or_upc.data else None

        # Log admin activity
        log = AdminActivity(
            admin_id=current_user.id,
            action="UPDATE_PRODUCT",
            details=f"Updated details for product '{product.product_name}' ({product.id}).",
            ip_address=request.remote_addr,
        )
        db.session.add(log)
        db.session.commit()

        flash(f"Product '{product.product_name}' updated successfully.", "success")
        return redirect(url_for("admin.view_product", product_id=product.id))

    return render_template(
        "admin/product_form.html",
        form=form,
        title=f"Edit {product.product_name}",
        is_edit=True,
        product=product,
    )


@admin_bp.route("/products/<product_id>/images/upload", methods=["POST"])
def upload_reference_image(product_id):
    """Upload an additional reference image to an existing product."""
    product = db.session.get(Product, product_id)
    if not product:
        abort(404)

    form = ReferenceImageUploadForm()
    if form.validate_on_submit():
        file_storage = form.image.data
        ref_dir = current_app.config["REFERENCE_UPLOAD_DIR"]

        success, result, orig_name = validate_and_save_image(file_storage, ref_dir)
        if success:
            ref_image = ReferenceImage(
                product_id=product.id,
                image_path=f"references/{result}",
                angle_or_view=form.angle_or_view.data,
                verification_status="verified",
            )
            db.session.add(ref_image)

            # Log admin activity
            log = AdminActivity(
                admin_id=current_user.id,
                action="ADD_REFERENCE_IMAGE",
                details=f"Added '{form.angle_or_view.data}' angle image for '{product.product_name}'.",
                ip_address=request.remote_addr,
            )
            db.session.add(log)
            db.session.commit()

            flash("Reference image uploaded and registered successfully.", "success")
        else:
            flash(f"Upload failed: {result}", "danger")
    else:
        for field, errors in form.errors.items():
            for err in errors:
                flash(f"{field}: {err}", "danger")

    return redirect(url_for("admin.view_product", product_id=product.id))


@admin_bp.route("/reference-images/<image_id>/delete", methods=["POST"])
def delete_reference_image(image_id):
    """Delete a single reference image record and remove the file from storage."""
    ref_image = db.session.get(ReferenceImage, image_id)
    if not ref_image:
        abort(404)

    product_id = ref_image.product_id
    product = db.session.get(Product, product_id)
    product_name = product.product_name if product else "Unknown"

    # Remove image file from uploads
    file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], ref_image.image_path)
    delete_file_safe(file_path)

    # Remove embedding file if present
    if ref_image.embedding_path:
        emb_path = os.path.join(current_app.config["UPLOAD_FOLDER"], ref_image.embedding_path)
        delete_file_safe(emb_path)

    db.session.delete(ref_image)

    # Log admin activity
    log = AdminActivity(
        admin_id=current_user.id,
        action="DELETE_REFERENCE_IMAGE",
        details=f"Deleted reference image {image_id} from product '{product_name}'.",
        ip_address=request.remote_addr,
    )
    db.session.add(log)
    db.session.commit()

    flash("Reference image removed successfully.", "info")
    return redirect(url_for("admin.view_product", product_id=product_id))


@admin_bp.route("/products/<product_id>/delete", methods=["POST"])
def delete_product(product_id):
    """Delete a product and all associated reference images and embeddings."""
    product = db.session.get(Product, product_id)
    if not product:
        abort(404)

    product_name = product.product_name

    # Delete all physical image files and embeddings linked to this product
    for ref_img in product.reference_images:
        img_path = os.path.join(current_app.config["UPLOAD_FOLDER"], ref_img.image_path)
        delete_file_safe(img_path)
        if ref_img.embedding_path:
            emb_path = os.path.join(current_app.config["UPLOAD_FOLDER"], ref_img.embedding_path)
            delete_file_safe(emb_path)

    db.session.delete(product)

    # Log admin activity
    log = AdminActivity(
        admin_id=current_user.id,
        action="DELETE_PRODUCT",
        details=f"Deleted product '{product_name}' and all associated reference images.",
        ip_address=request.remote_addr,
    )
    db.session.add(log)
    db.session.commit()

    flash(f"Product '{product_name}' and its references have been deleted.", "info")
    return redirect(url_for("admin.list_products"))


# ---------------------------------------------------------------------------
# REST API Endpoints for Products & Reference Images
# ---------------------------------------------------------------------------


@admin_bp.route("/api/products", methods=["GET"])
@csrf.exempt
def api_list_products():
    """REST API: Get all products."""
    products = Product.query.order_by(Product.created_at.desc()).all()
    return jsonify({"status": "success", "products": [p.to_dict() for p in products]})


@admin_bp.route("/api/products", methods=["POST"])
@csrf.exempt
def api_create_product():
    """REST API: Create a new product."""
    data = request.get_json() or {}
    product_name = data.get("product_name", "").strip()
    brand = data.get("brand", "").strip()
    category = data.get("category", "").strip()

    if not product_name or not brand or not category:
        return (
            jsonify({"status": "error", "message": "product_name, brand, and category are required."}),
            400,
        )

    product = Product(
        product_name=product_name,
        brand=brand,
        category=category,
        description=data.get("description"),
        sku_or_upc=data.get("sku_or_upc"),
    )
    db.session.add(product)
    db.session.commit()

    return jsonify({"status": "success", "product": product.to_dict()}), 201


@admin_bp.route("/api/products/<product_id>", methods=["GET"])
@csrf.exempt
def api_get_product(product_id):
    """REST API: Get single product details."""
    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({"status": "error", "message": "Product not found"}), 404
    return jsonify({"status": "success", "product": product.to_dict()})


@admin_bp.route("/api/products/<product_id>", methods=["PUT"])
@csrf.exempt
def api_update_product(product_id):
    """REST API: Update product metadata."""
    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({"status": "error", "message": "Product not found"}), 404

    data = request.get_json() or {}
    if "product_name" in data:
        product.product_name = data["product_name"].strip()
    if "brand" in data:
        product.brand = data["brand"].strip()
    if "category" in data:
        product.category = data["category"].strip()
    if "description" in data:
        product.description = data["description"]
    if "sku_or_upc" in data:
        product.sku_or_upc = data["sku_or_upc"]

    db.session.commit()
    return jsonify({"status": "success", "product": product.to_dict()})


@admin_bp.route("/api/products/<product_id>", methods=["DELETE"])
@csrf.exempt
def api_delete_product(product_id):
    """REST API: Delete product and references."""
    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({"status": "error", "message": "Product not found"}), 404

    for ref in product.reference_images:
        delete_file_safe(os.path.join(current_app.config["UPLOAD_FOLDER"], ref.image_path))
        if ref.embedding_path:
            delete_file_safe(os.path.join(current_app.config["UPLOAD_FOLDER"], ref.embedding_path))

    db.session.delete(product)
    db.session.commit()
    return jsonify({"status": "success", "message": "Product deleted."})


# ---------------------------------------------------------------------------
# REST API Endpoints for Admin System & User Management
# ---------------------------------------------------------------------------


@admin_bp.route("/api/stats", methods=["GET"])
def api_admin_stats():
    """REST API: Get all system KPIs and analytics for admin charts."""
    stats = _get_system_analytics()
    # Serialize models in response
    stats_json = {
        "total_users": stats["total_users"],
        "active_users": stats["active_users"],
        "total_products": stats["total_products"],
        "total_reference_images": stats["total_reference_images"],
        "total_scans": stats["total_scans"],
        "avg_latency_ms": stats["avg_latency_ms"],
        "status_map": stats["status_map"],
        "scan_category_map": stats["scan_category_map"],
        "prod_category_map": stats["prod_category_map"],
        "daily_scans": stats["daily_scans"],
        "products_needing_refs_count": stats["products_needing_refs_count"],
    }
    return jsonify({"status": "success", "data": stats_json})


@admin_bp.route("/api/users/<user_id>/toggle-status", methods=["POST"])
@csrf.exempt
def api_toggle_user_status(user_id):
    """REST API: Toggle user active state."""
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    if user.id == current_user.id:
        return jsonify({"status": "error", "message": "Cannot deactivate own account"}), 400

    user.is_active = not user.is_active
    db.session.commit()
    return jsonify({
        "status": "success",
        "user_id": user.id,
        "is_active": user.is_active,
        "message": f"User is now {'active' if user.is_active else 'inactive'}",
    })

