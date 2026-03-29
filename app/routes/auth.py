from datetime import datetime
from bson.objectid import ObjectId
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from .. import mongo
from ..models.user import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not email or not password or not confirm_password:
            flash("Complete all fields to continue.", "warning")
        elif password != confirm_password:
            flash("Passwords do not match.", "warning")
        elif mongo.db.users.find_one({"email": email}):
            flash("That email is already registered.", "warning")
        else:
            user_id = str(ObjectId())
            user_payload = {
                "user_id": user_id,
                "email": email,
                "name": name or email.split("@")[0],
                "password": generate_password_hash(password),
                "is_admin": False,
                "created_at": datetime.utcnow(),
            }
            mongo.db.users.insert_one(user_payload)
            login_user(User(user_payload))
            flash("Welcome! Your account has been created.", "success")
            return redirect(url_for("main.dashboard"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user_doc = mongo.db.users.find_one({"email": email})
        if not user_doc or not check_password_hash(user_doc.get("password", ""), password):
            flash("Invalid email or password.", "danger")
        else:
            login_user(User(user_doc))
            flash("Signed in successfully.", "success")
            return redirect(url_for("main.dashboard"))

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()

        if not email:
            flash("Email cannot be blank.", "warning")
        elif email != current_user.email and mongo.db.users.find_one({"email": email}):
            flash("That email is already in use.", "warning")
        else:
            mongo.db.users.update_one(
                {"user_id": current_user.id},
                {"$set": {"name": name or current_user.name, "email": email}},
            )
            updated_user = mongo.db.users.find_one({"user_id": current_user.id})
            login_user(User(updated_user))
            flash("Profile updated successfully.", "success")
            return redirect(url_for("auth.profile"))

    return render_template("profile.html")
