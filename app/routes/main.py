from flask import Blueprint, render_template, redirect, url_for, flash, session
from flask_login import login_required, current_user, login_user
from .. import mongo
from ..models.user import User
from .nav import refresh_nav_snapshot, get_nav_history, calculate_cmgr

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
@login_required
def dashboard():
    impersonated = session.get("impersonated_by")
    refresh_nav_snapshot(current_user.id)
    history = get_nav_history(current_user.id)
    chart_labels = [doc["period"] for doc in history]
    chart_values = [doc["nav_value"] for doc in history]
    cmgr = calculate_cmgr(history)
    growth_year_1 = round(((1 + cmgr / 100) ** 12 - 1) * 100, 2) if cmgr else 0.0
    growth_year_3 = round(((1 + cmgr / 100) ** 36 - 1) * 100, 2) if cmgr else 0.0
    growth_year_5 = round(((1 + cmgr / 100) ** 60 - 1) * 100, 2) if cmgr else 0.0
    return render_template(
        "index.html",
        impersonated=impersonated,
        chart_labels=chart_labels,
        chart_values=chart_values,
        cmgr=cmgr,
        growth_year_1=growth_year_1,
        growth_year_3=growth_year_3,
        growth_year_5=growth_year_5,
    )


@main_bp.route("/stop-impersonation")
@login_required
def stop_impersonation():
    original_admin_id = session.pop("impersonated_by", None)
    if original_admin_id:
        admin_doc = mongo.db.users.find_one({"user_id": original_admin_id})
        if admin_doc:
            login_user(User(admin_doc))
            flash("Returned to admin view.", "success")
            return redirect(url_for("admin.users"))

    flash("No impersonation session is currently active.", "warning")
    return redirect(url_for("main.dashboard"))
