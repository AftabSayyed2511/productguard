import io
import os
import pytest
from PIL import Image
from app import create_app, db
from app.models.user import User
from app.models.product import Product, ReferenceImage
from app.models.audit import AdminActivity


def create_test_image(format="JPEG", size=(100, 100), color=(0, 210, 255)):
    """Helper to generate in-memory dummy image file for upload testing."""
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format=format)
    buf.seek(0)
    return buf


@pytest.fixture
def app():
    """Create test application context with in-memory database."""
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_and_user(app):
    """Seed administrator and regular user."""
    with app.app_context():
        admin = User(
            full_name="Lead Admin",
            username="adminlead",
            email="adminlead@example.com",
            role="admin",
        )
        admin.set_password("AdminSecure2026!")

        user = User(
            full_name="Regular Citizen",
            username="regcitizen",
            email="citizen@example.com",
            role="user",
        )
        user.set_password("UserPass2026!")

        db.session.add_all([admin, user])
        db.session.commit()

        return {"admin_id": admin.id, "user_id": user.id}


def test_admin_product_access_control(client, admin_and_user):
    """Verify non-admin users cannot access administrative product management."""
    # 1. Anonymous access
    anon_res = client.get("/admin/products", follow_redirects=True)
    assert anon_res.status_code == 200
    assert "Please sign in" in anon_res.data.decode("utf-8")

    # 2. Regular user access
    client.post(
        "/auth/login",
        data={"email": "citizen@example.com", "password": "UserPass2026!"},
        follow_redirects=True,
    )
    user_res = client.get("/admin/products")
    assert user_res.status_code == 403

    # 3. Admin access
    client.get("/auth/logout")
    client.post(
        "/auth/login",
        data={"email": "adminlead@example.com", "password": "AdminSecure2026!"},
        follow_redirects=True,
    )
    admin_res = client.get("/admin/products")
    assert admin_res.status_code == 200
    assert "Product & Reference Repository" in admin_res.data.decode("utf-8")


def test_create_product_with_reference_image(client, admin_and_user, app):
    """Test creating a verified product with an uploaded reference image."""
    client.post(
        "/auth/login",
        data={"email": "adminlead@example.com", "password": "AdminSecure2026!"},
        follow_redirects=True,
    )

    img_data = create_test_image(format="JPEG")

    response = client.post(
        "/admin/products/new",
        data={
            "product_name": "Moisturizing Cream 50ml",
            "brand": "CeraVe",
            "category": "Cosmetics",
            "sku_or_upc": "CRV-MC-50",
            "description": "Original packaging with holographic seal",
            "angle_or_view": "front",
            "images": (img_data, "cerave_front.jpg"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "CeraVe Moisturizing Cream 50ml" in html
    assert "front" in html.lower()

    # Verify DB records
    with app.app_context():
        product = Product.query.filter_by(product_name="Moisturizing Cream 50ml").first()
        assert product is not None
        assert product.brand == "CeraVe"
        assert product.category == "Cosmetics"
        assert len(product.reference_images) == 1

        ref_img = product.reference_images[0]
        assert ref_img.angle_or_view == "front"
        assert ref_img.verification_status == "verified"

        # Verify audit activity
        activity = AdminActivity.query.filter_by(action="CREATE_PRODUCT").first()
        assert activity is not None
        assert "Moisturizing Cream" in activity.details

        # Verify physical file existence
        full_file_path = os.path.join(app.config["UPLOAD_FOLDER"], ref_img.image_path)
        assert os.path.exists(full_file_path)


def test_invalid_image_upload_rejected(client, admin_and_user, app):
    """Test that corrupted image uploads are rejected."""
    client.post(
        "/auth/login",
        data={"email": "adminlead@example.com", "password": "AdminSecure2026!"},
        follow_redirects=True,
    )

    # Fake corrupted image (plain text content)
    corrupted_data = io.BytesIO(b"Not an actual image payload at all!")

    response = client.post(
        "/admin/products/new",
        data={
            "product_name": "Corrupt Product",
            "brand": "TestBrand",
            "category": "Electronics",
            "angle_or_view": "front",
            "images": (corrupted_data, "fake.jpg"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Corrupted image file" in response.data.decode("utf-8")


def test_upload_additional_angle_image(client, admin_and_user, app):
    """Test attaching an additional multi-angle image to an existing product."""
    client.post(
        "/auth/login",
        data={"email": "adminlead@example.com", "password": "AdminSecure2026!"},
        follow_redirects=True,
    )

    with app.app_context():
        prod = Product(
            product_name="Wireless Mouse",
            brand="Logitech",
            category="Electronics",
            sku_or_upc="LOGI-M720",
        )
        db.session.add(prod)
        db.session.commit()
        prod_id = prod.id

    back_img = create_test_image(format="PNG")

    upload_res = client.post(
        f"/admin/products/{prod_id}/images/upload",
        data={
            "angle_or_view": "back",
            "image": (back_img, "logitech_back.png"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert upload_res.status_code == 200
    assert "Reference image uploaded" in upload_res.data.decode("utf-8")

    with app.app_context():
        updated_prod = db.session.get(Product, prod_id)
        assert len(updated_prod.reference_images) == 1
        assert updated_prod.reference_images[0].angle_or_view == "back"


def test_edit_product_metadata(client, admin_and_user, app):
    """Test modifying existing product information."""
    client.post(
        "/auth/login",
        data={"email": "adminlead@example.com", "password": "AdminSecure2026!"},
        follow_redirects=True,
    )

    with app.app_context():
        prod = Product(
            product_name="Original Name",
            brand="OldBrand",
            category="Clothing",
        )
        db.session.add(prod)
        db.session.commit()
        prod_id = prod.id

    edit_res = client.post(
        f"/admin/products/{prod_id}/edit",
        data={
            "product_name": "Updated Name",
            "brand": "NewBrand",
            "category": "Clothing",
            "description": "Updated packaging description",
            "sku_or_upc": "UPDATED-SKU",
        },
        follow_redirects=True,
    )
    assert edit_res.status_code == 200
    assert "Updated Name" in edit_res.data.decode("utf-8")

    with app.app_context():
        updated_prod = db.session.get(Product, prod_id)
        assert updated_prod.product_name == "Updated Name"
        assert updated_prod.brand == "NewBrand"
        assert updated_prod.sku_or_upc == "UPDATED-SKU"


def test_delete_reference_image(client, admin_and_user, app):
    """Test deleting an individual reference image and its disk file."""
    client.post(
        "/auth/login",
        data={"email": "adminlead@example.com", "password": "AdminSecure2026!"},
        follow_redirects=True,
    )

    with app.app_context():
        prod = Product(
            product_name="Test Deletion",
            brand="BrandX",
            category="Personal Care",
        )
        db.session.add(prod)
        db.session.flush()

        # Create dummy file on disk
        ref_filename = "delete_me.jpg"
        full_path = os.path.join(app.config["REFERENCE_UPLOAD_DIR"], ref_filename)
        with open(full_path, "wb") as f:
            f.write(b"dummy")

        ref_img = ReferenceImage(
            product_id=prod.id,
            image_path=f"references/{ref_filename}",
            angle_or_view="side",
        )
        db.session.add(ref_img)
        db.session.commit()

        img_id = ref_img.id
        prod_id = prod.id

    # Verify file exists before deletion
    assert os.path.exists(full_path)

    del_res = client.post(f"/admin/reference-images/{img_id}/delete", follow_redirects=True)
    assert del_res.status_code == 200
    assert "Reference image removed" in del_res.data.decode("utf-8")

    # Verify DB and physical file deleted
    with app.app_context():
        assert db.session.get(ReferenceImage, img_id) is None
    assert not os.path.exists(full_path)


def test_delete_product_cascades(client, admin_and_user, app):
    """Test deleting product removes all associated images from DB and disk."""
    client.post(
        "/auth/login",
        data={"email": "adminlead@example.com", "password": "AdminSecure2026!"},
        follow_redirects=True,
    )

    with app.app_context():
        prod = Product(
            product_name="Product To Kill",
            brand="DeadBrand",
            category="Packaged Goods",
        )
        db.session.add(prod)
        db.session.flush()

        filename = "cascade_test.jpg"
        filepath = os.path.join(app.config["REFERENCE_UPLOAD_DIR"], filename)
        with open(filepath, "wb") as f:
            f.write(b"dummy image data")

        ref = ReferenceImage(
            product_id=prod.id,
            image_path=f"references/{filename}",
            angle_or_view="box",
        )
        db.session.add(ref)
        db.session.commit()

        prod_id = prod.id
        ref_id = ref.id

    assert os.path.exists(filepath)

    del_res = client.post(f"/admin/products/{prod_id}/delete", follow_redirects=True)
    assert del_res.status_code == 200
    assert "deleted" in del_res.data.decode("utf-8")

    with app.app_context():
        assert db.session.get(Product, prod_id) is None
        assert db.session.get(ReferenceImage, ref_id) is None
    assert not os.path.exists(filepath)


def test_admin_rest_api_crud(client, admin_and_user, app):
    """Test REST API endpoints for product management."""
    # 1. Login as admin
    client.post(
        "/auth/login",
        data={"email": "adminlead@example.com", "password": "AdminSecure2026!"},
        follow_redirects=True,
    )

    # 2. Create product via API
    create_res = client.post(
        "/admin/api/products",
        json={
            "product_name": "API Shampoo",
            "brand": "Pantene",
            "category": "Personal Care",
            "sku_or_upc": "PAN-SH-400",
            "description": "Smooth & Sleek packaging",
        },
    )
    assert create_res.status_code == 201
    prod_data = create_res.json["product"]
    assert prod_data["product_name"] == "API Shampoo"
    prod_id = prod_data["id"]

    # 3. Get product
    get_res = client.get(f"/admin/api/products/{prod_id}")
    assert get_res.status_code == 200
    assert get_res.json["product"]["brand"] == "Pantene"

    # 4. Update product
    put_res = client.put(
        f"/admin/api/products/{prod_id}",
        json={"product_name": "API Shampoo Updated"},
    )
    assert put_res.status_code == 200
    assert put_res.json["product"]["product_name"] == "API Shampoo Updated"

    # 5. List products
    list_res = client.get("/admin/api/products")
    assert list_res.status_code == 200
    assert len(list_res.json["products"]) >= 1

    # 6. Delete product
    del_res = client.delete(f"/admin/api/products/{prod_id}")
    assert del_res.status_code == 200
    assert del_res.json["status"] == "success"
