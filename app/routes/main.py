from flask import Blueprint, render_template

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """Landing page introducing ProductGuard."""
    return render_template("index.html")


@main_bp.route("/about")
def about():
    """About page explaining computer vision verification and project scope."""
    return render_template("about.html")
