from functools import wraps
from flask import abort, flash, redirect, url_for, request, jsonify
from flask_login import current_user


def admin_required(f):
    """Decorator to restrict access to administrator users only."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json or request.path.startswith("/api/"):
                return (
                    jsonify({"error": "Authentication required", "status": "unauthorized"}),
                    401,
                )
            flash("Please sign in with administrator credentials.", "warning")
            return redirect(url_for("auth.login", next=request.url))

        if not current_user.is_admin():
            if request.is_json or request.path.startswith("/api/"):
                return (
                    jsonify(
                        {
                            "error": "Forbidden. Administrator privileges required.",
                            "status": "forbidden",
                        }
                    ),
                    403,
                )
            abort(403)

        return f(*args, **kwargs)

    return decorated_function


def active_user_required(f):
    """Decorator to ensure user account is not suspended."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("auth.login", next=request.url))

        if not current_user.is_active:
            flash("Your account has been deactivated. Contact an administrator.", "danger")
            return redirect(url_for("main.index"))

        return f(*args, **kwargs)

    return decorated_function
