import os
import click
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import config_by_name

# Initialize Flask extensions
db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "60 per minute"],
    storage_uri="memory://",
)

# Configure Flask-Login defaults
login_manager.login_view = "auth.login"
login_manager.login_message = "Please sign in to access this page."
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id):
    from app.models.user import User

    return db.session.get(User, user_id)


def create_app(config_name="development"):
    """Application factory for ProductGuard."""
    app = Flask(__name__)

    # Load environment configuration
    config_class = config_by_name.get(config_name, config_by_name["development"])
    app.config.from_object(config_class)

    # Ensure upload directories exist
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["REFERENCE_UPLOAD_DIR"], exist_ok=True)
    os.makedirs(app.config["SCAN_UPLOAD_DIR"], exist_ok=True)
    os.makedirs(app.config["EMBEDDING_DIR"], exist_ok=True)

    # Initialize extensions with app context
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)

    # Security Headers Middleware
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Content Security Policy allowing required CDNs (Bootstrap, Bootstrap Icons, Chart.js, Google Fonts)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
            "img-src 'self' data: blob: https:; "
            "connect-src 'self';"
        )
        return response

    # Register blueprints
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.scan import scan_bp
    from app.routes.admin import admin_bp
    from app.routes.user import user_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(scan_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(user_bp)

    # Error handlers
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def request_entity_too_large(error):
        return render_template("errors/413.html"), 413

    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        if request.path.startswith("/api/"):
            return jsonify({
                "status": "error",
                "message": "Too many requests. Please slow down and try again later.",
            }), 429
        return render_template("errors/429.html"), 429

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    # Global context processors for Jinja templates
    @app.context_processor
    def inject_global_vars():
        return {
            "APP_NAME": "ProductGuard",
            "APP_TAGLINE": "Detect. Verify. Protect.",
            "CURRENT_YEAR": 2026,
        }

    # Register CLI commands
    @app.cli.command("init-db")
    def init_db_command():
        """Create database tables."""
        db.create_all()
        click.echo(" * Initialized database tables successfully.")

    @app.cli.command("create-admin")
    @click.option("--username", prompt=True, help="Admin username")
    @click.option("--email", prompt=True, help="Admin email address")
    @click.option("--fullname", prompt=True, default="System Administrator", help="Admin full name")
    @click.option(
        "--password",
        prompt=True,
        hide_input=True,
        confirmation_prompt=True,
        help="Admin password",
    )
    def create_admin_command(username, email, fullname, password):
        """Securely create the first or additional administrator account."""
        from app.models.user import User

        email = email.strip().lower()
        username = username.strip()

        if User.query.filter_by(email=email).first():
            click.echo(f"Error: Email {email} is already in use.")
            return

        if User.query.filter_by(username=username).first():
            click.echo(f"Error: Username {username} is already taken.")
            return

        admin = User(
            full_name=fullname.strip(),
            username=username,
            email=email,
            role="admin",
            is_active=True,
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo(f" * Administrator '{username}' ({email}) created successfully.")

    return app
