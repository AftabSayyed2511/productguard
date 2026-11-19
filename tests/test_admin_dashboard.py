"""
Tests for Phase 9: Admin Dashboard, User Management & System Analytics
Validates:
- RBAC protection on all admin routes
- System KPI telemetry and status distribution aggregation
- User management (activation toggle, role changes, self-modification prevention)
- Admin audit log entries
- REST APIs for admin metrics and user status
"""

import pytest
from app import db
from app.models.user import User
from app.models.product import Product, ReferenceImage
from app.models.scan import Scan
from app.models.audit import AdminActivity


@pytest.fixture
def admin_user(app):
    with app.app_context():
        admin = User(
            full_name="Lead Admin",
            username="lead_admin",
            email="lead_admin@example.com",
            role="admin",
            is_active=True,
        )
        admin.set_password("AdminPass123!")
        db.session.add(admin)
        db.session.commit()
        return admin.id


@pytest.fixture
def normal_user(app):
    with app.app_context():
        user = User(
            full_name="Standard User",
            username="std_user",
            email="std_user@example.com",
            role="user",
            is_active=True,
        )
        user.set_password("UserPass123!")
        db.session.add(user)
        db.session.commit()
        return user.id


def test_admin_dashboard_requires_admin_role(client, normal_user):
    """Test that regular authenticated users are denied access to admin views."""
    with client:
        client.post(
            "/auth/login",
            data={"email": "std_user@example.com", "password": "UserPass123!"},
            follow_redirects=True,
        )
        # Should be forbidden or redirected
        res_dash = client.get("/admin/dashboard")
        assert res_dash.status_code in [302, 403]

        res_users = client.get("/admin/users")
        assert res_users.status_code in [302, 403]

        res_analytics = client.get("/admin/analytics")
        assert res_analytics.status_code in [302, 403]


def test_admin_dashboard_renders_for_admin(client, app, admin_user):
    """Test that administrators can view the dashboard and see system telemetry."""
    with client:
        client.post(
            "/auth/login",
            data={"email": "lead_admin@example.com", "password": "AdminPass123!"},
            follow_redirects=True,
        )

        response = client.get("/admin/dashboard")
        assert response.status_code == 200
        assert b"Administrative Control Center" in response.data
        assert b"Registered Users" in response.data
        assert b"MobileNetV2" in response.data


def test_admin_users_list_and_search(client, app, admin_user, normal_user):
    """Test user management list view and search filter."""
    with client:
        client.post(
            "/auth/login",
            data={"email": "lead_admin@example.com", "password": "AdminPass123!"},
            follow_redirects=True,
        )

        response = client.get("/admin/users")
        assert response.status_code == 200
        assert b"std_user" in response.data
        assert b"lead_admin" in response.data

        # Search filter
        search_res = client.get("/admin/users?q=std_user")
        assert search_res.status_code == 200
        assert b"std_user" in search_res.data


def test_admin_cannot_deactivate_or_demote_self(client, app, admin_user):
    """Test security constraint: Admin cannot suspend or demote their own account."""
    with client:
        client.post(
            "/auth/login",
            data={"email": "lead_admin@example.com", "password": "AdminPass123!"},
            follow_redirects=True,
        )

        # Attempt to toggle own status
        res_toggle = client.post(
            f"/admin/users/{admin_user}/toggle-status",
            follow_redirects=True,
        )
        assert b"cannot suspend your own" in res_toggle.data

        # Verify admin is still active
        with app.app_context():
            admin = db.session.get(User, admin_user)
            assert admin.is_active is True

        # Attempt to demote own role
        res_role = client.post(
            f"/admin/users/{admin_user}/change-role",
            data={"role": "user"},
            follow_redirects=True,
        )
        assert b"cannot modify your own" in res_role.data

        with app.app_context():
            admin = db.session.get(User, admin_user)
            assert admin.role == "admin"


def test_admin_toggle_other_user_status_and_audit(client, app, admin_user, normal_user):
    """Test deactivating and reactivating a user account and verifying the audit trail."""
    with client:
        client.post(
            "/auth/login",
            data={"email": "lead_admin@example.com", "password": "AdminPass123!"},
            follow_redirects=True,
        )

        # Deactivate normal user
        res = client.post(
            f"/admin/users/{normal_user}/toggle-status",
            follow_redirects=True,
        )
        assert res.status_code == 200

        with app.app_context():
            target = db.session.get(User, normal_user)
            assert target.is_active is False

            # Verify audit activity was logged
            audit = (
                AdminActivity.query.filter_by(admin_id=admin_user)
                .order_by(AdminActivity.created_at.desc())
                .first()
            )
            assert audit is not None
            assert "DEACTIVATE_USER" in audit.action

        # Reactivate normal user
        client.post(f"/admin/users/{normal_user}/toggle-status", follow_redirects=True)
        with app.app_context():
            target = db.session.get(User, normal_user)
            assert target.is_active is True


def test_admin_change_user_role(client, app, admin_user, normal_user):
    """Test promoting standard user to admin and demoting back."""
    with client:
        client.post(
            "/auth/login",
            data={"email": "lead_admin@example.com", "password": "AdminPass123!"},
            follow_redirects=True,
        )

        # Promote
        client.post(
            f"/admin/users/{normal_user}/change-role",
            data={"role": "admin"},
            follow_redirects=True,
        )
        with app.app_context():
            user = db.session.get(User, normal_user)
            assert user.role == "admin"

        # Demote back
        client.post(
            f"/admin/users/{normal_user}/change-role",
            data={"role": "user"},
            follow_redirects=True,
        )
        with app.app_context():
            user = db.session.get(User, normal_user)
            assert user.role == "user"


def test_admin_analytics_and_audit_log_view(client, app, admin_user):
    """Test that the analytics view displays charts and audit logs."""
    with client:
        client.post(
            "/auth/login",
            data={"email": "lead_admin@example.com", "password": "AdminPass123!"},
            follow_redirects=True,
        )

        response = client.get("/admin/analytics")
        assert response.status_code == 200
        assert b"Platform Telemetry" in response.data
        assert b"Administrative Audit Trail" in response.data
        assert b"MobileNetV2" in response.data


def test_admin_rest_api_stats_and_user_toggle(client, app, admin_user, normal_user):
    """Test the JSON REST APIs for stats and user management."""
    with client:
        client.post(
            "/auth/login",
            data={"email": "lead_admin@example.com", "password": "AdminPass123!"},
            follow_redirects=True,
        )

        # GET /admin/api/stats
        res_stats = client.get("/admin/api/stats")
        assert res_stats.status_code == 200
        data = res_stats.get_json()
        assert data["status"] == "success"
        stats = data["data"]
        assert "total_users" in stats
        assert "total_products" in stats
        assert "total_scans" in stats
        assert "status_map" in stats

        # POST /admin/api/users/<id>/toggle-status
        res_toggle = client.post(f"/admin/api/users/{normal_user}/toggle-status")
        assert res_toggle.status_code == 200
        toggle_data = res_toggle.get_json()
        assert toggle_data["status"] == "success"
        assert toggle_data["is_active"] is False
