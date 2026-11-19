"""
User Dashboard Blueprint — ProductGuard Phase 8
Routes: /dashboard, /api/dashboard/stats
"""

from collections import defaultdict
from datetime import datetime, timedelta
from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from app import db
from app.models.scan import Scan
from app.models.product import Product

user_bp = Blueprint("user", __name__)

# Assessment status constants
STATUS_HIGH = "HIGH_SIMILARITY"
STATUS_MODERATE = "MODERATE_SIMILARITY"
STATUS_LOW = "LOW_SIMILARITY"
STATUS_INSUFFICIENT = "INSUFFICIENT_DATA"

ALL_STATUSES = [STATUS_HIGH, STATUS_MODERATE, STATUS_LOW, STATUS_INSUFFICIENT]


# ---------------------------------------------------------------------------
# Helper: Aggregate dashboard statistics from real DB queries
# ---------------------------------------------------------------------------

def _build_dashboard_stats(user_id: str) -> dict:
    """
    Query the database and build a complete statistics payload for the
    authenticated user. All numbers come from real DB rows — nothing is
    hardcoded or estimated.
    """
    # Total scan count
    total_scans = Scan.query.filter_by(user_id=user_id).count()

    # Per-status counts (single aggregation query)
    status_counts_raw = (
        db.session.query(Scan.assessment_status, func.count(Scan.id))
        .filter(Scan.user_id == user_id)
        .group_by(Scan.assessment_status)
        .all()
    )
    status_map = {status: 0 for status in ALL_STATUSES}
    for status, count in status_counts_raw:
        if status in status_map:
            status_map[status] = count

    # Category distribution (only scans with matched products)
    category_counts_raw = (
        db.session.query(Product.category, func.count(Scan.id))
        .join(Scan, Scan.matched_product_id == Product.id)
        .filter(Scan.user_id == user_id)
        .group_by(Product.category)
        .all()
    )
    category_map = {cat: cnt for cat, cnt in category_counts_raw}

    # Scans in the last 30 days (day-by-day for sparkline chart)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_counts_raw = (
        db.session.query(
            func.date(Scan.scanned_at).label("day"),
            func.count(Scan.id).label("cnt"),
        )
        .filter(Scan.user_id == user_id, Scan.scanned_at >= thirty_days_ago)
        .group_by(func.date(Scan.scanned_at))
        .order_by(func.date(Scan.scanned_at))
        .all()
    )
    daily_activity = {str(row.day): row.cnt for row in recent_counts_raw}

    # 5 most recent scans for the activity feed
    recent_scans = (
        Scan.query.filter_by(user_id=user_id)
        .order_by(Scan.scanned_at.desc())
        .limit(5)
        .all()
    )

    return {
        "total_scans": total_scans,
        "high_similarity": status_map[STATUS_HIGH],
        "moderate_similarity": status_map[STATUS_MODERATE],
        "low_similarity": status_map[STATUS_LOW],
        "insufficient_data": status_map[STATUS_INSUFFICIENT],
        "category_distribution": category_map,
        "daily_activity_30d": daily_activity,
        "recent_scans": [s.to_dict() for s in recent_scans],
    }


# ---------------------------------------------------------------------------
# HTML Controllers
# ---------------------------------------------------------------------------

@user_bp.route("/dashboard")
@login_required
def dashboard():
    """Render the authenticated user's personal dashboard."""
    stats = _build_dashboard_stats(current_user.id)

    # Recent scan objects with relationships for Jinja template
    recent_scans = (
        Scan.query.filter_by(user_id=current_user.id)
        .order_by(Scan.scanned_at.desc())
        .limit(8)
        .all()
    )

    return render_template(
        "user/dashboard.html",
        stats=stats,
        recent_scans=recent_scans,
        page_title="My Dashboard",
    )


# ---------------------------------------------------------------------------
# REST API — Dashboard Statistics (JSON)
# ---------------------------------------------------------------------------

@user_bp.route("/api/dashboard/stats")
@login_required
def api_dashboard_stats():
    """
    REST endpoint: Returns all dashboard KPIs for the authenticated user.
    Used by Chart.js renderers in dashboard.js.
    """
    try:
        stats = _build_dashboard_stats(current_user.id)
        return jsonify({"status": "success", "data": stats})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500
