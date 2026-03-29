from flask import Blueprint, render_template, redirect, url_for, flash, session
from flask_login import login_required, current_user, login_user
from .. import mongo
from ..models.user import User

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
@login_required
def dashboard():
    impersonated = session.get("impersonated_by")
    return render_template("index.html", impersonated=impersonated)


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
