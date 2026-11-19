import pytest
from app import create_app, db
from app.models.user import User
from app.models.product import Product, ReferenceImage
from app.models.scan import Scan
from app.models.audit import AdminActivity
from app.utils.decorators import admin_required
from flask import jsonify


@pytest.fixture
def app():
    """Create test application context with in-memory database."""
    app = create_app("testing")

    # Add a dummy admin-only test route to test the @admin_required decorator
    @app.route("/test-admin-gate")
    @admin_required
    def test_admin_gate():
        return jsonify({"message": "Admin area reached"})

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_database_tables_created(app):
    """Verify that all normalized tables are properly initialized in the schema."""
    with app.app_context():
        # Verify table models can be queried without error
        assert User.query.count() == 0
        assert Product.query.count() == 0
        assert ReferenceImage.query.count() == 0
        assert Scan.query.count() == 0
        assert AdminActivity.query.count() == 0


def test_user_password_hashing(app):
    """Verify password is never saved in plain text and hashes verify correctly."""
    with app.app_context():
        user = User(
            full_name="Alice Security",
            username="alicesec",
            email="alice@example.com",
            role="user",
        )
        user.set_password("SuperSecret123!")

        assert user.password_hash != "SuperSecret123!"
        assert user.password_hash.startswith("scrypt:") or user.password_hash.startswith("pbkdf2:")
        assert user.check_password("SuperSecret123!") is True
        assert user.check_password("WrongPassword") is False


def test_user_registration_form(client, app):
    """Test user registration through the web form."""
    response = client.post(
        "/auth/register",
        data={
            "full_name": "Bob Builder",
            "username": "bobbuilder",
            "email": "bob@example.com",
            "password": "Password123!",
            "confirm_password": "Password123!",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Account created successfully" in html

    # Verify database insertion
    with app.app_context():
        user = User.query.filter_by(email="bob@example.com").first()
        assert user is not None
        assert user.username == "bobbuilder"
        assert user.role == "user"
        assert user.check_password("Password123!") is True


def test_duplicate_registration_rejected(client, app):
    """Ensure duplicate email or username registration is blocked."""
    with app.app_context():
        user = User(
            full_name="Existing User",
            username="existinguser",
            email="existing@example.com",
        )
        user.set_password("Existing123!")
        db.session.add(user)
        db.session.commit()

    # Attempt same email with different username
    res1 = client.post(
        "/auth/register",
        data={
            "full_name": "Clone User",
            "username": "cloneuser",
            "email": "existing@example.com",
            "password": "Password123!",
            "confirm_password": "Password123!",
        },
    )
    assert res1.status_code == 200
    assert "This email address is already registered" in res1.data.decode("utf-8")

    # Attempt same username with different email
    res2 = client.post(
        "/auth/register",
        data={
            "full_name": "Clone User",
            "username": "existinguser",
            "email": "other@example.com",
            "password": "Password123!",
            "confirm_password": "Password123!",
        },
    )
    assert res2.status_code == 200
    assert "This username is already taken" in res2.data.decode("utf-8")


def test_user_login_and_logout(client, app):
    """Test standard login and logout lifecycle."""
    with app.app_context():
        user = User(
            full_name="Charlie Tester",
            username="charliet",
            email="charlie@example.com",
        )
        user.set_password("ValidPassword99#")
        db.session.add(user)
        db.session.commit()

    # Login with wrong password
    bad_login = client.post(
        "/auth/login",
        data={"email": "charlie@example.com", "password": "WrongPassword!"},
        follow_redirects=True,
    )
    assert bad_login.status_code == 401
    assert "Invalid email or password" in bad_login.data.decode("utf-8")

    # Login with correct password
    good_login = client.post(
        "/auth/login",
        data={"email": "charlie@example.com", "password": "ValidPassword99#"},
        follow_redirects=True,
    )
    assert good_login.status_code == 200
    assert "Welcome back, Charlie Tester!" in good_login.data.decode("utf-8")

    # Verify user profile route accessible when logged in
    prof = client.get("/auth/profile")
    assert prof.status_code == 200
    assert "Charlie Tester" in prof.data.decode("utf-8")

    # Logout
    logout_res = client.get("/auth/logout", follow_redirects=True)
    assert logout_res.status_code == 200
    assert "You have been signed out successfully" in logout_res.data.decode("utf-8")

    # Verify profile redirects to login after logout
    prof_after = client.get("/auth/profile", follow_redirects=True)
    assert "Please sign in to access this page" in prof_after.data.decode("utf-8")


def test_deactivated_account_blocked(client, app):
    """Ensure inactive users cannot log in."""
    with app.app_context():
        user = User(
            full_name="Deactivated Person",
            username="deact",
            email="deact@example.com",
            is_active=False,
        )
        user.set_password("Password123!")
        db.session.add(user)
        db.session.commit()

    res = client.post(
        "/auth/login",
        data={"email": "deact@example.com", "password": "Password123!"},
        follow_redirects=True,
    )
    assert res.status_code == 403
    assert "Your account has been deactivated" in res.data.decode("utf-8")


def test_admin_access_control(client, app):
    """Test role-based access control protecting administrative routes."""
    with app.app_context():
        standard_user = User(
            full_name="Standard User",
            username="stduser",
            email="std@example.com",
            role="user",
        )
        standard_user.set_password("Pass12345!")

        admin_user = User(
            full_name="Admin Boss",
            username="adminboss",
            email="admin@example.com",
            role="admin",
        )
        admin_user.set_password("AdminPass12345!")

        db.session.add_all([standard_user, admin_user])
        db.session.commit()

    # Anonymous user -> redirected to login
    anon_res = client.get("/test-admin-gate", follow_redirects=True)
    assert "Please sign in with administrator credentials" in anon_res.data.decode("utf-8")

    # Standard user logs in -> access prohibited with 403
    client.post(
        "/auth/login",
        data={"email": "std@example.com", "password": "Pass12345!"},
        follow_redirects=True,
    )
    std_gate = client.get("/test-admin-gate")
    assert std_gate.status_code == 403
    assert "403" in std_gate.data.decode("utf-8")
    assert "Access Prohibited" in std_gate.data.decode("utf-8")

    # Admin user logs in -> access granted with 200
    client.get("/auth/logout")
    client.post(
        "/auth/login",
        data={"email": "admin@example.com", "password": "AdminPass12345!"},
        follow_redirects=True,
    )
    admin_gate = client.get("/test-admin-gate")
    assert admin_gate.status_code == 200
    assert "Admin area reached" in admin_gate.data.decode("utf-8")


def test_rest_api_auth(client, app):
    """Test REST API registration, login, session inspection, and logout."""
    # API Registration
    reg_res = client.post(
        "/api/auth/register",
        json={
            "full_name": "API User",
            "username": "apiuser",
            "email": "api@example.com",
            "password": "SecurePassword123!",
        },
    )
    assert reg_res.status_code == 201
    assert reg_res.json["status"] == "success"
    assert reg_res.json["user"]["username"] == "apiuser"

    # API Duplicate Email Rejection
    dup_res = client.post(
        "/api/auth/register",
        json={
            "full_name": "API User 2",
            "username": "apiuser2",
            "email": "api@example.com",
            "password": "SecurePassword123!",
        },
    )
    assert dup_res.status_code == 400
    assert "Email already registered" in dup_res.json["errors"]["email"]

    # API Login
    login_res = client.post(
        "/api/auth/login",
        json={"email": "api@example.com", "password": "SecurePassword123!"},
    )
    assert login_res.status_code == 200
    assert login_res.json["status"] == "success"

    # API Me (Inspect current session)
    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 200
    assert me_res.json["authenticated"] is True
    assert me_res.json["user"]["email"] == "api@example.com"

    # API Logout
    logout_res = client.post("/api/auth/logout")
    assert logout_res.status_code == 200

    # API Me after logout
    me_after = client.get("/api/auth/me")
    assert me_after.status_code == 200
    assert me_after.json["authenticated"] is False
