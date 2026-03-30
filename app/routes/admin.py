from flask import Blueprint, render_template, redirect, url_for, flash, session, request
from flask_login import login_required, current_user, login_user
from .. import mongo
from ..models.user import User
from ..utils import admin_required, get_goal_subcategories, save_goal_subcategories
from ..utils import admin_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/users")
@login_required
@admin_required
def users():
    users = list(mongo.db.users.find({}, {"password": 0}).sort("created_at", -1))
    return render_template("admin_users.html", users=users)


@admin_bp.route("/goal-subcategories", methods=["GET", "POST"])
@login_required
@admin_required
def goal_subcategories():
    if request.method == "POST":
        raw = request.form.get("subcategories_raw", "")
        cleaned = []
        for line in raw.splitlines():
            value = line.strip()
            if value and value not in cleaned:
                cleaned.append(value)

        if not cleaned:
            flash("Enter at least one valid subcategory.", "warning")
        else:
            save_goal_subcategories(cleaned)
            flash("Goal subcategories saved successfully.", "success")
        return redirect(url_for("admin.goal_subcategories"))

    subcategories = get_goal_subcategories()
    return render_template("admin_goal_subcategories.html", subcategories=subcategories)


@admin_bp.route("/users/<string:user_id>")
@login_required
@admin_required
def view_user(user_id):
    user_doc = mongo.db.users.find_one({"user_id": user_id}, {"password": 0})
    if not user_doc:
        flash("User not found.", "warning")
        return redirect(url_for("admin.users"))
    return render_template("admin_view_user.html", user=user_doc)


@admin_bp.route("/impersonate/<string:user_id>")
@login_required
@admin_required
def impersonate(user_id):
    target_user = mongo.db.users.find_one({"user_id": user_id})
    if not target_user:
        flash("User not found.", "warning")
        return redirect(url_for("admin.users"))

    session_data = current_user.id
    login_user(User(target_user))
    from flask import session

    session["impersonated_by"] = session_data
    flash(f"Impersonating {target_user.get('email')}.", "info")
    return redirect(url_for("main.dashboard"))
