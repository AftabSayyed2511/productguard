"""
Tests for Phase 8: User Dashboard & History Analytics
Validates:
- Access control for /dashboard and /api/dashboard/stats
- Correct aggregation of scan counts by assessment status
- Category distribution aggregation
- User privacy and isolation in dashboard statistics
"""

import pytest
from app import db
from app.models.user import User
from app.models.product import Product
from app.models.scan import Scan


@pytest.fixture
def auth_user(app):
    with app.app_context():
        user = User(
            full_name="Dashboard User",
            username="dash_user",
            email="dash_user@example.com",
            role="user",
            is_active=True,
        )
        user.set_password("Password123!")
        db.session.add(user)
        db.session.commit()
        return user.id


@pytest.fixture
def second_user(app):
    with app.app_context():
        user = User(
            full_name="Second User",
            username="second_user",
            email="second@example.com",
            role="user",
            is_active=True,
        )
        user.set_password("Password123!")
        db.session.add(user)
        db.session.commit()
        return user.id


def test_dashboard_requires_login(client):
    """Test that /dashboard redirects unauthenticated users to login."""
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_dashboard_api_requires_login(client):
    """Test that /api/dashboard/stats redirects or blocks unauthenticated users."""
    response = client.get("/api/dashboard/stats", follow_redirects=False)
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_dashboard_renders_for_authenticated_user(client, app, auth_user):
    """Test that logged-in users can load their dashboard view."""
    with client:
        # Log in
        client.post(
            "/auth/login",
            data={"email": "dash_user@example.com", "password": "Password123!"},
            follow_redirects=True,
        )
        response = client.get("/dashboard")
        assert response.status_code == 200
        assert b"Welcome back" in response.data
        assert b"My Dashboard" in response.data
        assert b"Total Scans" in response.data


def test_dashboard_stats_aggregation_and_privacy(client, app, auth_user, second_user):
    """Test accurate KPI counts, status groupings, and user isolation."""
    with app.app_context():
        # Create a test product
        prod1 = Product(
            product_name="Verified Phone",
            brand="BrandX",
            category="Electronics",
            description="Test product",
        )
        prod2 = Product(
            product_name="Face Cream",
            brand="GlowSkin",
            category="Cosmetics",
            description="Skincare product",
        )
        db.session.add_all([prod1, prod2])
        db.session.commit()

        # Add scans for auth_user
        scan1 = Scan(
            user_id=auth_user,
            matched_product_id=prod1.id,
            uploaded_image_path="scans/dummy1.jpg",
            similarity_score=0.92,
            assessment_status="HIGH_SIMILARITY",
            processing_time_ms=120,
        )
        scan2 = Scan(
            user_id=auth_user,
            matched_product_id=prod2.id,
            uploaded_image_path="scans/dummy2.jpg",
            similarity_score=0.71,
            assessment_status="MODERATE_SIMILARITY",
            processing_time_ms=115,
        )
        scan3 = Scan(
            user_id=auth_user,
            matched_product_id=prod1.id,
            uploaded_image_path="scans/dummy3.jpg",
            similarity_score=0.20,
            assessment_status="LOW_SIMILARITY",
            processing_time_ms=110,
        )

        # Add scan for second_user (must NOT appear in auth_user's stats)
        scan_other = Scan(
            user_id=second_user,
            matched_product_id=prod1.id,
            uploaded_image_path="scans/other.jpg",
            similarity_score=0.95,
            assessment_status="HIGH_SIMILARITY",
            processing_time_ms=100,
        )
        db.session.add_all([scan1, scan2, scan3, scan_other])
        db.session.commit()

    with client:
        # Log in as auth_user
        client.post(
            "/auth/login",
            data={"email": "dash_user@example.com", "password": "Password123!"},
            follow_redirects=True,
        )

        response = client.get("/api/dashboard/stats")
        assert response.status_code == 200
        data = response.get_json()

        assert data["status"] == "success"
        stats = data["data"]

        # auth_user has exactly 3 scans
        assert stats["total_scans"] == 3
        assert stats["high_similarity"] == 1
        assert stats["moderate_similarity"] == 1
        assert stats["low_similarity"] == 1
        assert stats["insufficient_data"] == 0

        # Check category distribution
        assert stats["category_distribution"].get("Electronics") == 2
        assert stats["category_distribution"].get("Cosmetics") == 1

        # Check recent scans list length
        assert len(stats["recent_scans"]) == 3
