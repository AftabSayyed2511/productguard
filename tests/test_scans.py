import io
import os
import pytest
from PIL import Image
from app import create_app, db
from app.models.user import User
from app.models.product import Product, ReferenceImage
from app.models.scan import Scan


def make_test_image(color=(30, 144, 255), size=(224, 224)):
    """Generate in-memory RGB JPEG image."""
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf


@pytest.fixture
def app():
    """Create test application context with temporary upload directories."""
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
def test_user_and_reference(app):
    """Seed regular user, genuine product, and reference image."""
    with app.app_context():
        user = User(
            full_name="Scan Tester",
            username="scantester",
            email="scanner@example.com",
            role="user",
        )
        user.set_password("ScanPass123!")

        user2 = User(
            full_name="Second Scanner",
            username="scanner2",
            email="scanner2@example.com",
            role="user",
        )
        user2.set_password("ScanPass123!")

        # Create genuine product
        product = Product(
            product_name="Power Bank 20000",
            brand="Anker",
            category="Electronics",
            sku_or_upc="ANK-PB-20K",
            description="Genuine fast-charging portable charger packaging",
        )
        db.session.add_all([user, user2, product])
        db.session.flush()

        # Save reference image file in test uploads
        ref_dir = app.config["REFERENCE_UPLOAD_DIR"]
        os.makedirs(ref_dir, exist_ok=True)
        ref_filename = "anker_powerbank_genuine.jpg"
        ref_filepath = os.path.join(ref_dir, ref_filename)

        Image.new("RGB", (224, 224), color=(30, 144, 255)).save(ref_filepath, format="JPEG")

        ref_image = ReferenceImage(
            product_id=product.id,
            image_path=f"references/{ref_filename}",
            angle_or_view="front",
            verification_status="verified",
        )
        db.session.add(ref_image)
        db.session.commit()

        return {
            "user_id": user.id,
            "user2_id": user2.id,
            "product_id": product.id,
            "ref_image_id": ref_image.id,
        }


def test_anonymous_scan_attempt_rejected(client):
    """Verify unauthenticated scan requests receive 401 Unauthorized."""
    img = make_test_image()
    res = client.post(
        "/api/scans",
        data={"category": "Electronics", "image": (img, "test.jpg")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 401
    assert "Authentication required" in res.json["message"]


def test_missing_category_or_image_rejected(client, test_user_and_reference):
    """Verify validation catches missing category or missing image file."""
    client.post(
        "/auth/login",
        data={"email": "scanner@example.com", "password": "ScanPass123!"},
        follow_redirects=True,
    )

    # 1. Missing category
    img = make_test_image()
    res1 = client.post(
        "/api/scans",
        data={"image": (img, "test.jpg")},
        content_type="multipart/form-data",
    )
    assert res1.status_code == 400
    assert "category" in res1.json["message"].lower()

    # 2. Missing image
    res2 = client.post(
        "/api/scans",
        data={"category": "Electronics"},
        content_type="multipart/form-data",
    )
    assert res2.status_code == 400
    assert "image" in res2.json["message"].lower()


def test_corrupted_image_scan_rejected(client, test_user_and_reference):
    """Verify corrupted non-image files are rejected before AI inference."""
    client.post(
        "/auth/login",
        data={"email": "scanner@example.com", "password": "ScanPass123!"},
        follow_redirects=True,
    )

    bad_file = io.BytesIO(b"Fake header pretending to be an image")
    res = client.post(
        "/api/scans",
        data={"category": "Electronics", "image": (bad_file, "corrupt.jpg")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 400
    assert "corrupted" in res.json["message"].lower() or "invalid" in res.json["message"].lower()


def test_successful_end_to_end_scan(client, test_user_and_reference, app):
    """
    Test complete real-time verification workflow:
    Upload query -> MobileNetV2 embedding -> Cosine similarity -> Database persistence -> JSON report.
    """
    client.post(
        "/auth/login",
        data={"email": "scanner@example.com", "password": "ScanPass123!"},
        follow_redirects=True,
    )

    # Query image matching the genuine reference (same color)
    query_img = make_test_image(color=(30, 144, 255), size=(224, 224))

    response = client.post(
        "/api/scans",
        data={
            "category": "Electronics",
            "notes": "Testing real-time verification pipeline",
            "image": (query_img, "query_anker.jpg"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    data = response.json
    assert data["status"] == "success"
    assert "scan_id" in data

    match = data["match"]
    assert match["matched_product"]["product_name"] == "Power Bank 20000"
    assert match["matched_product"]["brand"] == "Anker"
    assert match["similarity_score"] >= 0.82
    assert match["assessment_status"] == "HIGH_SIMILARITY"
    assert match["processing_time_ms"] >= 0

    scan_id = data["scan_id"]

    # Verify database persistence
    with app.app_context():
        scan = db.session.get(Scan, scan_id)
        assert scan is not None
        assert scan.user_id == test_user_and_reference["user_id"]
        assert scan.matched_product_id == test_user_and_reference["product_id"]
        assert scan.similarity_score >= 0.82
        assert scan.assessment_status == "HIGH_SIMILARITY"
        assert scan.notes == "Testing real-time verification pipeline"

        # Verify query file saved on disk
        full_query_path = os.path.join(app.config["UPLOAD_FOLDER"], scan.uploaded_image_path)
        assert os.path.exists(full_query_path)


def test_scan_with_empty_category_insufficient_data(client, test_user_and_reference, app):
    """Verify that scanning an unpopulated category returns INSUFFICIENT_DATA."""
    client.post(
        "/auth/login",
        data={"email": "scanner@example.com", "password": "ScanPass123!"},
        follow_redirects=True,
    )

    query_img = make_test_image(color=(200, 50, 100))

    response = client.post(
        "/api/scans",
        data={
            "category": "Clothing",  # No clothing items seeded in fixture
            "image": (query_img, "shirt.jpg"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    data = response.json
    assert data["status"] == "success"

    match = data["match"]
    assert match["assessment_status"] == "INSUFFICIENT_DATA"
    assert match["similarity_score"] == 0.0
    assert "Unable to assess this product" in match["assessment_description"]


def test_api_scan_history_and_privacy(client, test_user_and_reference, app):
    """Test REST API scan listing and privacy controls."""
    # User 1 logs in and performs a scan
    client.post(
        "/auth/login",
        data={"email": "scanner@example.com", "password": "ScanPass123!"},
        follow_redirects=True,
    )
    query_img = make_test_image()
    scan_res = client.post(
        "/api/scans",
        data={"category": "Electronics", "image": (query_img, "test.jpg")},
        content_type="multipart/form-data",
    )
    scan_id = scan_res.json["scan_id"]

    # User 1 lists scans via GET /api/scans
    list_res = client.get("/api/scans")
    assert list_res.status_code == 200
    assert list_res.json["total"] == 1
    assert list_res.json["scans"][0]["id"] == scan_id

    # User 1 inspects single scan via GET /api/scans/<id>
    get_res = client.get(f"/api/scans/{scan_id}")
    assert get_res.status_code == 200
    assert get_res.json["scan"]["id"] == scan_id

    # User 2 logs in and attempts to access User 1's scan -> 403 Forbidden
    client.get("/auth/logout")
    client.post(
        "/auth/login",
        data={"email": "scanner2@example.com", "password": "ScanPass123!"},
        follow_redirects=True,
    )
    forbidden_res = client.get(f"/api/scans/{scan_id}")
    assert forbidden_res.status_code == 403

    # User 1 logs back in and deletes the scan
    client.get("/auth/logout")
    client.post(
        "/auth/login",
        data={"email": "scanner@example.com", "password": "ScanPass123!"},
        follow_redirects=True,
    )
    del_res = client.delete(f"/api/scans/{scan_id}")
    assert del_res.status_code == 200
    assert del_res.json["status"] == "success"

    with app.app_context():
        assert db.session.get(Scan, scan_id) is None
