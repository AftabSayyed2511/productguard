import os
from datetime import datetime
from flask import (
    Blueprint,
    render_template,
    abort,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    current_app,
)
from flask_login import login_required, current_user
from app import db, csrf, limiter
from app.models.scan import Scan
from app.models.product import Product
from app.utils.file_handlers import validate_and_save_image, delete_file_safe
from app.ai.matcher import match_query_image

scan_bp = Blueprint("scan", __name__)

SUPPORTED_CATEGORIES = [
    "Electronics",
    "Cosmetics",
    "Clothing",
    "Personal Care",
    "Packaged Goods",
]


# ---------------------------------------------------------------------------
# HTML Form & Page Controllers
# ---------------------------------------------------------------------------


@scan_bp.route("/scan")
@login_required
def scan_page():
    """Render the interactive product scanning portal."""
    return render_template(
        "scan/scan.html",
        categories=SUPPORTED_CATEGORIES,
    )


@scan_bp.route("/scan/history")
@login_required
def history():
    """Render the user's historical packaging verification scans."""
    category_filter = request.args.get("category", "").strip()
    status_filter = request.args.get("status", "").strip()
    search_query = request.args.get("q", "").strip()

    query = Scan.query.filter_by(user_id=current_user.id)

    if status_filter:
        query = query.filter_by(assessment_status=status_filter)

    scans = query.order_by(Scan.scanned_at.desc()).all()

    # Filter in memory for joins/search
    if category_filter:
        scans = [
            s
            for s in scans
            if s.matched_product and s.matched_product.category == category_filter
        ]
    if search_query:
        q_lower = search_query.lower()
        scans = [
            s
            for s in scans
            if (
                s.matched_product
                and (
                    q_lower in s.matched_product.product_name.lower()
                    or q_lower in s.matched_product.brand.lower()
                )
            )
            or (q_lower in s.assessment_status.lower())
        ]

    return render_template(
        "scan/history.html",
        scans=scans,
        categories=SUPPORTED_CATEGORIES,
        current_category=category_filter,
        current_status=status_filter,
        search_query=search_query,
    )


@scan_bp.route("/scan/<scan_id>")
@login_required
def view_result(scan_id):
    """View detailed comparison report for a specific scan."""
    scan = db.session.get(Scan, scan_id)
    if not scan:
        abort(404)

    # Security check: users can only view their own private scans unless admin
    if scan.user_id != current_user.id and not current_user.is_admin():
        abort(403)

    return render_template("scan/result.html", scan=scan)


@scan_bp.route("/scan/<scan_id>/delete", methods=["POST"])
@login_required
def delete_scan(scan_id):
    """Allow user to remove a record from their personal scan history."""
    scan = db.session.get(Scan, scan_id)
    if not scan:
        abort(404)

    if scan.user_id != current_user.id and not current_user.is_admin():
        abort(403)

    # Safely remove uploaded query image file from disk
    file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], scan.uploaded_image_path)
    delete_file_safe(file_path)

    db.session.delete(scan)
    db.session.commit()
    flash("Scan record deleted from history.", "info")
    return redirect(url_for("scan.history"))


# ---------------------------------------------------------------------------
# REST API Endpoints for Real-Time Scanning
# ---------------------------------------------------------------------------


@scan_bp.route("/api/scans", methods=["POST"])
@csrf.exempt
@limiter.limit("30 per minute")
def api_create_scan():
    """
    Real-Time AI Verification Scan API Endpoint.

    Accepts multipart/form-data:
        - image: Packaging image file (JPEG, JPG, PNG <= 5 MB)
        - category: Product category to constrain comparison space
        - notes: Optional user notes

    Workflow:
        1. Validates user session.
        2. Validates image payload and saves to uploads/scans/.
        3. Executes MobileNetV2 feature extraction & cosine similarity matching.
        4. Persists the Scan record with latency and similarity metrics.
        5. Returns structured JSON report.
    """
    if not current_user.is_authenticated:
        return (
            jsonify({"status": "error", "message": "Authentication required to scan products."}),
            401,
        )

    category = request.form.get("category", "").strip()
    if not category:
        return (
            jsonify({"status": "error", "message": "Product category selection is required."}),
            400,
        )

    if "image" not in request.files:
        return (
            jsonify({"status": "error", "message": "Packaging image file is required."}),
            400,
        )

    file_storage = request.files["image"]
    scan_dir = current_app.config["SCAN_UPLOAD_DIR"]

    # 1. Validate and save uploaded query image
    success, result, orig_name = validate_and_save_image(file_storage, scan_dir)
    if not success:
        return (
            jsonify({"status": "error", "message": result}),
            400,
        )

    saved_filename = result
    saved_full_path = os.path.join(scan_dir, saved_filename)

    try:
        # 2. Run AI Inference and Similarity Comparison
        match_result = match_query_image(
            saved_full_path,
            category=category,
            uploads_folder=current_app.config["UPLOAD_FOLDER"],
            threshold_high=current_app.config["SIMILARITY_THRESHOLD_HIGH"],
            threshold_mod=current_app.config["SIMILARITY_THRESHOLD_MODERATE"],
            threshold_min=current_app.config["SIMILARITY_THRESHOLD_MINIMUM"],
        )

        # 3. Persist Scan record in relational database
        scan = Scan(
            user_id=current_user.id,
            matched_product_id=match_result.get("matched_product_id"),
            matched_reference_image_id=match_result.get("matched_reference_image_id"),
            uploaded_image_path=f"scans/{saved_filename}",
            similarity_score=match_result["similarity_score"],
            assessment_status=match_result["assessment_status"],
            processing_time_ms=match_result["processing_time_ms"],
            notes=request.form.get("notes", "").strip() or None,
            scanned_at=datetime.utcnow(),
        )
        db.session.add(scan)
        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Packaging verification scan completed.",
                    "scan_id": scan.id,
                    "scan": scan.to_dict(),
                    "match": match_result,
                }
            ),
            201,
        )

    except Exception as e:
        # Clean up uploaded file if AI pipeline fails unexpectedly
        delete_file_safe(saved_full_path)
        db.session.rollback()
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f"Inference processing anomaly: {str(e)}",
                }
            ),
            500,
        )


@scan_bp.route("/api/scans", methods=["GET"])
def api_list_scans():
    """REST API: Get authenticated user's scan history."""
    if not current_user.is_authenticated:
        return jsonify({"status": "error", "message": "Authentication required."}), 401

    scans = (
        Scan.query.filter_by(user_id=current_user.id)
        .order_by(Scan.scanned_at.desc())
        .all()
    )
    return jsonify(
        {
            "status": "success",
            "total": len(scans),
            "scans": [s.to_dict() for s in scans],
        }
    )


@scan_bp.route("/api/scans/<scan_id>", methods=["GET"])
def api_get_scan(scan_id):
    """REST API: Get details of a single scan."""
    if not current_user.is_authenticated:
        return jsonify({"status": "error", "message": "Authentication required."}), 401

    scan = db.session.get(Scan, scan_id)
    if not scan:
        return jsonify({"status": "error", "message": "Scan not found."}), 404

    if scan.user_id != current_user.id and not current_user.is_admin():
        return (
            jsonify({"status": "error", "message": "Forbidden. Unauthorized access."}),
            403,
        )

    return jsonify({"status": "success", "scan": scan.to_dict()})


@scan_bp.route("/api/scans/<scan_id>", methods=["DELETE"])
@csrf.exempt
def api_delete_scan(scan_id):
    """REST API: Delete scan record and remove query image file from disk."""
    if not current_user.is_authenticated:
        return jsonify({"status": "error", "message": "Authentication required."}), 401

    scan = db.session.get(Scan, scan_id)
    if not scan:
        return jsonify({"status": "error", "message": "Scan not found."}), 404

    if scan.user_id != current_user.id and not current_user.is_admin():
        return (
            jsonify({"status": "error", "message": "Forbidden. Unauthorized access."}),
            403,
        )

    file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], scan.uploaded_image_path)
    delete_file_safe(file_path)

    db.session.delete(scan)
    db.session.commit()
    return jsonify({"status": "success", "message": "Scan deleted successfully."})
