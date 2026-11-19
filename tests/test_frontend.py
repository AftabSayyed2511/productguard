import pytest
from app import create_app, db
from app.models.user import User
from app.models.product import Product, ReferenceImage
from app.models.scan import Scan


@pytest.fixture
def app():
    """Create testing application context."""
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
def user_and_admin(app):
    """Seed test user and administrator."""
    with app.app_context():
        user = User(
            full_name="Normal User",
            username="normaluser",
            email="normal@example.com",
            role="user",
        )
        user.set_password("NormalPass123!")

        admin = User(
            full_name="Admin User",
            username="adminuser",
            email="admin@example.com",
            role="admin",
        )
        admin.set_password("AdminPass123!")

        product = Product(
            product_name="Galaxy S25 Ultra",
            brand="Samsung",
            category="Electronics",
            description="Genuine smartphone packaging",
            sku_or_upc="SAM-S25-GEN",
        )

        db.session.add_all([user, admin, product])
        db.session.commit()

        ref_img = ReferenceImage(
            product_id=product.id,
            image_path="references/samsung_s25.jpg",
            embedding_path="embeddings/samsung_s25.npy",
            angle_or_view="front",
        )
        db.session.add(ref_img)
        db.session.commit()

        # Seed sample scan
        scan = Scan(
            user_id=user.id,
            matched_product_id=product.id,
            matched_reference_image_id=ref_img.id,
            uploaded_image_path="scans/query_s25.jpg",
            similarity_score=0.9124,
            assessment_status="HIGH_SIMILARITY",
            processing_time_ms=138,
        )
        db.session.add(scan)
        db.session.commit()

        return {
            "user_id": user.id,
            "admin_id": admin.id,
            "product_id": product.id,
            "scan_id": scan.id,
        }


def test_unauthenticated_scan_routes_redirect_to_login(client):
    """Ensure anonymous visitors cannot access scan or history pages."""
    res_scan = client.get("/scan", follow_redirects=True)
    assert res_scan.status_code == 200
    assert "Please sign in to access this page" in res_scan.data.decode("utf-8")

    res_hist = client.get("/scan/history", follow_redirects=True)
    assert res_hist.status_code == 200
    assert "Please sign in to access this page" in res_hist.data.decode("utf-8")


def test_authenticated_scanning_portal_renders(client, user_and_admin):
    """Verify scanning page loads with dropzone, category choices, and guidelines."""
    client.post(
        "/auth/login",
        data={"email": "normal@example.com", "password": "NormalPass123!"},
        follow_redirects=True,
    )

    res = client.get("/scan")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Scan Product Packaging" in html
    assert "dropzone" in html
    assert "fileInput" in html
    assert "Electronics" in html
    assert "Cosmetics" in html
    assert "Packaged Goods" in html
    assert "Guidelines for High-Accuracy Scanning" in html


def test_scan_history_rendering_and_filtering(client, user_and_admin):
    """Test personal scan history listing, search, and category filtering."""
    client.post(
        "/auth/login",
        data={"email": "normal@example.com", "password": "NormalPass123!"},
        follow_redirects=True,
    )

    # 1. View all scans
    res = client.get("/scan/history")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Personal Scan History" in html
    assert "Samsung" in html
    assert "Galaxy S25 Ultra" in html
    assert "91.2%" in html
    assert "High Similarity" in html

    # 2. Search match
    res_search = client.get("/scan/history?q=Galaxy")
    assert "Galaxy S25 Ultra" in res_search.data.decode("utf-8")

    # 3. Search non-match
    res_nomatch = client.get("/scan/history?q=Perfume")
    assert "No Scan Records Found" in res_nomatch.data.decode("utf-8")


def test_scan_result_privacy_and_access_control(client, user_and_admin, app):
    """Verify that private scans cannot be viewed by other regular users."""
    scan_id = user_and_admin["scan_id"]

    # Create a second regular user
    with app.app_context():
        user2 = User(
            full_name="Second User",
            username="seconduser",
            email="second@example.com",
            role="user",
        )
        user2.set_password("User2Pass123!")
        db.session.add(user2)
        db.session.commit()

    # User 2 logs in and tries to access User 1's scan
    client.post(
        "/auth/login",
        data={"email": "second@example.com", "password": "User2Pass123!"},
        follow_redirects=True,
    )
    unauth_res = client.get(f"/scan/{scan_id}")
    assert unauth_res.status_code == 403

    # User 1 logs in and accesses their own scan
    client.get("/auth/logout")
    client.post(
        "/auth/login",
        data={"email": "normal@example.com", "password": "NormalPass123!"},
        follow_redirects=True,
    )
    auth_res = client.get(f"/scan/{scan_id}")
    assert auth_res.status_code == 200
    html = auth_res.data.decode("utf-8")
    assert "Verification Assessment Report" in html
    assert "Samsung Galaxy S25" in html
    assert "Uploaded Query Image" in html
    assert "Closest Verified Reference" in html
    assert "Cosine Similarity" in html
    assert "91.2%" in html
    assert "Crucial Scientific Verification Notice" in html


def test_delete_personal_scan(client, user_and_admin, app):
    """Test removing a scan record from history."""
    scan_id = user_and_admin["scan_id"]

    client.post(
        "/auth/login",
        data={"email": "normal@example.com", "password": "NormalPass123!"},
        follow_redirects=True,
    )

    del_res = client.post(f"/scan/{scan_id}/delete", follow_redirects=True)
    assert del_res.status_code == 200
    assert "Scan record deleted from history" in del_res.data.decode("utf-8")

    with app.app_context():
        assert db.session.get(Scan, scan_id) is None
