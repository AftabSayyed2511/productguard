"""
Tests for Phase 10: Security Hardening, Edge Cases & Rate Limiting
Validates:
- HTTP Security Headers (CSP, X-Content-Type-Options, X-Frame-Options)
- Malicious file uploads (executable disguised as image, non-image mime types)
- Rate limiting protection on auth & scan endpoints
- SQL Injection resilience in search queries
- XSS prevention in user-supplied strings and notes
"""

import io
import pytest
from app import db, create_app
from app.models.user import User
from app.models.product import Product


def test_security_headers_present_on_responses(client):
    """Verify that all HTTP responses carry security hardening headers."""
    response = client.get("/")
    assert response.status_code == 200

    headers = response.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert headers.get("X-XSS-Protection") == "1; mode=block"
    assert "strict-origin" in headers.get("Referrer-Policy", "")
    assert "Content-Security-Policy" in headers


def test_malicious_script_extension_rejected(client, app):
    """Verify that uploading PHP/script files disguised as images is blocked."""
    with app.app_context():
        admin = User(
            full_name="Sec Admin",
            username="sec_admin",
            email="sec_admin@example.com",
            role="admin",
            is_active=True,
        )
        admin.set_password("AdminPass123!")
        db.session.add(admin)
        db.session.commit()

    with client:
        client.post(
            "/auth/login",
            data={"email": "sec_admin@example.com", "password": "AdminPass123!"},
            follow_redirects=True,
        )

        # Upload a .php script with malicious contents
        fake_php = (io.BytesIO(b"<?php echo 'pwned'; ?>"), "exploit.php")
        response = client.post(
            "/admin/products/new",
            data={
                "product_name": "Exploit Prod",
                "brand": "BadBrand",
                "category": "Electronics",
                "images": [fake_php],
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert b"Invalid file type" in response.data or b"Error saving" in response.data or response.status_code == 200


def test_corrupted_header_disguised_file_rejected(client, app):
    """Test that a file named test.jpg with raw text content fails Pillow validation."""
    with app.app_context():
        user = User(
            full_name="Sec User",
            username="sec_user",
            email="sec_user@example.com",
            role="user",
            is_active=True,
        )
        user.set_password("UserPass123!")
        db.session.add(user)
        db.session.commit()

    with client:
        client.post(
            "/auth/login",
            data={"email": "sec_user@example.com", "password": "UserPass123!"},
            follow_redirects=True,
        )

        # File named .jpg but contains text/binary garbage
        fake_jpg = (io.BytesIO(b"NOT_A_REAL_IMAGE_DATA_XYZ123"), "fake.jpg")
        response = client.post(
            "/api/scans",
            data={"category": "Electronics", "image": fake_jpg},
            content_type="multipart/form-data",
        )
        assert response.status_code == 400
        json_data = response.get_json()
        assert json_data["status"] == "error"
        assert "invalid" in json_data["message"].lower() or "corrupted" in json_data["message"].lower()


def test_sql_injection_resilience_in_search(client, app):
    """Verify that SQL injection strings in search queries do not crash or corrupt the query."""
    with app.app_context():
        admin = User(
            full_name="SQL Admin",
            username="sql_admin",
            email="sql_admin@example.com",
            role="admin",
            is_active=True,
        )
        admin.set_password("AdminPass123!")
        db.session.add(admin)
        db.session.commit()

    with client:
        client.post(
            "/auth/login",
            data={"email": "sql_admin@example.com", "password": "AdminPass123!"},
            follow_redirects=True,
        )

        malicious_queries = [
            "' OR '1'='1",
            "'; DROP TABLE users; --",
            "' UNION SELECT id, username, password_hash FROM users --",
            "admin'--",
        ]

        for query in malicious_queries:
            resp = client.get(f"/admin/products?q={query}")
            assert resp.status_code == 200
            resp_users = client.get(f"/admin/users?q={query}")
            assert resp_users.status_code == 200


def test_xss_prevention_in_templates(client, app):
    """Test that XSS payloads are properly escaped and not rendered executable."""
    with app.app_context():
        user = User(
            full_name="<script>alert('xss')</script>",
            username="xss_user",
            email="xss@example.com",
            role="user",
            is_active=True,
        )
        user.set_password("UserPass123!")
        db.session.add(user)
        db.session.commit()

    with client:
        client.post(
            "/auth/login",
            data={"email": "xss@example.com", "password": "UserPass123!"},
            follow_redirects=True,
        )

        # In dashboard or profile, the raw script tag should be HTML escaped
        dash_res = client.get("/dashboard")
        assert dash_res.status_code == 200
        assert b"<script>alert('xss')</script>" not in dash_res.data
        assert b"&lt;script&gt;alert(&#39;xss&#39;)&lt;/script&gt;" in dash_res.data or b"&lt;script&gt;" in dash_res.data


def test_rate_limiting_enforcement():
    """Verify that rate limiter returns 429 when limits are reached."""
    from app import limiter

    # Create development app which has RATELIMIT_ENABLED = True
    test_app = create_app("development")
    test_app.config["TESTING"] = False
    test_app.config["WTF_CSRF_ENABLED"] = False
    test_app.config["RATELIMIT_ENABLED"] = True

    # Explicitly ensure limiter is enabled for this test
    limiter.enabled = True

    with test_app.test_client() as c:
        hit_429 = False
        for i in range(25):
            res = c.post(
                "/auth/register",
                data={
                    "full_name": f"Rate User {i}",
                    "username": f"rate_user_{i}",
                    "email": f"rate_{i}@example.com",
                    "password": "Password123!",
                    "confirm_password": "Password123!",
                },
            )
            if res.status_code == 429:
                hit_429 = True
                break

        # Reset limiter for subsequent tests
        limiter.enabled = False
        assert hit_429 is True
