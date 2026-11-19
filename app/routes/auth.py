from urllib.parse import urlparse
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    jsonify,
)
from flask_login import login_user, logout_user, login_required, current_user
from app import db, csrf, limiter
from app.models.user import User
from app.forms.auth_forms import RegistrationForm, LoginForm, ProfileForm

auth_bp = Blueprint("auth", __name__)


def is_safe_url(target: str) -> bool:
    """Ensure redirect targets belong to the same host."""
    ref_url = urlparse(request.host_url)
    test_url = urlparse(target)
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


# ---------------------------------------------------------------------------
# HTML Form Views
# ---------------------------------------------------------------------------


@auth_bp.route("/auth/register", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def register():
    """Register a new user account."""
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            full_name=form.full_name.data.strip(),
            username=form.username.data.strip(),
            email=form.email.data.strip().lower(),
            role="user",
            is_active=True,
        )
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        flash("Account created successfully! You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/auth/login", methods=["GET", "POST"])
@limiter.limit("20 per minute")
def login():
    """Sign in an existing user."""
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()

        if user is None or not user.check_password(form.password.data):
            flash("Invalid email or password. Please verify your credentials.", "danger")
            return render_template("auth/login.html", form=form), 401

        if not user.is_active:
            flash("Your account has been deactivated. Please contact support.", "warning")
            return render_template("auth/login.html", form=form), 403

        login_user(user, remember=form.remember_me.data)
        flash(f"Welcome back, {user.full_name}!", "success")

        next_page = request.args.get("next")
        if next_page and is_safe_url(next_page):
            return redirect(next_page)
        return redirect(url_for("main.index"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/auth/logout")
@login_required
def logout():
    """Sign out the current user session."""
    logout_user()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for("main.index"))


@auth_bp.route("/auth/profile", methods=["GET", "POST"])
@login_required
def profile():
    """View and update current user profile."""
    form = ProfileForm(obj=current_user)

    if form.validate_on_submit():
        # Check email change collision
        new_email = form.email.data.strip().lower()
        if new_email != current_user.email:
            existing = User.query.filter_by(email=new_email).first()
            if existing:
                flash("That email is already registered to another account.", "danger")
                return render_template("auth/profile.html", form=form)
            current_user.email = new_email

        current_user.full_name = form.full_name.data.strip()

        # Update password if requested
        if form.new_password.data:
            if not form.current_password.data or not current_user.check_password(
                form.current_password.data
            ):
                flash("Current password incorrect. Password not changed.", "danger")
                return render_template("auth/profile.html", form=form)
            current_user.set_password(form.new_password.data)
            flash("Password updated successfully.", "success")

        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("auth.profile"))

    return render_template("auth/profile.html", form=form)


# ---------------------------------------------------------------------------
# REST API Endpoints
# ---------------------------------------------------------------------------


@auth_bp.route("/api/auth/register", methods=["POST"])
@csrf.exempt
def api_register():
    """REST API endpoint for user registration."""
    data = request.get_json() or {}
    full_name = data.get("full_name", "").strip()
    username = data.get("username", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    errors = {}
    if not full_name:
        errors["full_name"] = "Full name is required."
    if not username:
        errors["username"] = "Username is required."
    elif User.query.filter_by(username=username).first():
        errors["username"] = "Username already exists."
    if not email or "@" not in email:
        errors["email"] = "Valid email is required."
    elif User.query.filter_by(email=email).first():
        errors["email"] = "Email already registered."
    if not password or len(password) < 8:
        errors["password"] = "Password must be at least 8 characters long."

    if errors:
        return jsonify({"status": "error", "errors": errors}), 400

    user = User(
        full_name=full_name,
        username=username,
        email=email,
        role="user",
        is_active=True,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    return (
        jsonify(
            {
                "status": "success",
                "message": "User registered successfully.",
                "user": user.to_dict(),
            }
        ),
        201,
    )


@auth_bp.route("/api/auth/login", methods=["POST"])
@csrf.exempt
def api_login():
    """REST API endpoint for user authentication."""
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    remember = bool(data.get("remember_me", False))

    if not email or not password:
        return jsonify({"status": "error", "message": "Email and password required."}), 400

    user = User.query.filter_by(email=email).first()
    if user is None or not user.check_password(password):
        return jsonify({"status": "error", "message": "Invalid email or password."}), 401

    if not user.is_active:
        return jsonify({"status": "error", "message": "Account has been deactivated."}), 403

    login_user(user, remember=remember)
    return jsonify(
        {
            "status": "success",
            "message": "Authentication successful.",
            "user": user.to_dict(),
        }
    )


@auth_bp.route("/api/auth/logout", methods=["POST"])
@csrf.exempt
def api_logout():
    """REST API endpoint for signing out."""
    if current_user.is_authenticated:
        logout_user()
    return jsonify({"status": "success", "message": "Signed out successfully."})


@auth_bp.route("/api/auth/me", methods=["GET"])
def api_me():
    """REST API endpoint to inspect the current session."""
    if current_user.is_authenticated:
        return jsonify({"authenticated": True, "user": current_user.to_dict()})
    return jsonify({"authenticated": False, "user": None})
