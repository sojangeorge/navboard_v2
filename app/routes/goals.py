from datetime import datetime, timedelta
from bson.objectid import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from .. import mongo
from ..utils import get_goal_subcategories

goals_bp = Blueprint("goals", __name__, url_prefix="/goals")


def _admin_access_forbidden():
    if current_user.is_authenticated and getattr(current_user, "is_admin", False):
        abort(403)


goals_bp.before_request(_admin_access_forbidden)

CATEGORY_YEAR = "year-specific"
CATEGORY_RECURRING = "recurring"
QUARTERS = ["Q1", "Q2", "Q3", "Q4"]
PRIORITIES = ["High", "Medium", "Low"]


def json_safe(value):
    if isinstance(value, dict):
        safe = {}
        for key, item in value.items():
            if key == "_id":
                safe[key] = str(item)
            else:
                safe[key] = json_safe(item)
        return safe
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def calculate_progress(goal):
    key_results = goal.get("key_results", [])
    if not key_results:
        return 0
    completed = sum(1 for item in key_results if item.get("completed"))
    return int((completed / len(key_results)) * 100)


def calculate_due_status(goal):
    due_date = goal.get("due_date")
    if isinstance(due_date, datetime):
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        if due_date < today:
            return "past_due"
        if due_date <= today + timedelta(days=7):
            return "due_soon"
    return "on_track"


def build_goal_payload(form, existing_results=None):
    category = form.get("category") or CATEGORY_YEAR
    title = form.get("title", "").strip()
    description = form.get("description", "").strip()
    priority = form.get("priority", "Medium")
    year = int(form.get("year", datetime.utcnow().year)) if category == CATEGORY_YEAR else datetime.utcnow().year
    subcategory = form.get("subcategory", "") if category == CATEGORY_YEAR else ""
    quarter = form.get("quarter", "Q1") if category == CATEGORY_RECURRING else ""
    due_date_raw = form.get("due_date", "").strip()
    due_date = None
    if due_date_raw:
        try:
            due_date = datetime.fromisoformat(due_date_raw)
        except ValueError:
            due_date = None
    raw_results = form.get("key_results", "").splitlines()
    key_results = []
    for line in raw_results:
        text = line.strip()
        if not text:
            continue
        completed = False
        if existing_results is not None:
            completed = existing_results.get(text, False)
        key_results.append({
            "id": str(ObjectId()),
            "title": text,
            "completed": completed,
        })

    completed_flag = bool(key_results) and all(item["completed"] for item in key_results)
    goal = {
        "title": title,
        "description": description,
        "category": category,
        "priority": priority,
        "year": year,
        "subcategory": subcategory,
        "quarter": quarter,
        "due_date": due_date,
        "key_results": key_results,
        "completed": completed_flag,
        "updated_at": datetime.utcnow(),
    }
    return goal


@goals_bp.route("/")
@login_required
def index():
    selected_tab = request.args.get("tab", "year")
    selected_subcategory = request.args.get("subcategory", "")
    selected_due_filter = request.args.get("due_filter", "all")
    current_year = datetime.utcnow().year

    year_query = {
        "user_id": current_user.id,
        "category": CATEGORY_YEAR,
        "year": current_year,
    }
    if selected_subcategory:
        year_query["subcategory"] = selected_subcategory
    if selected_due_filter == "past_due":
        year_query["due_date"] = {"$lt": datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)}
    elif selected_due_filter == "due_soon":
        year_query["due_date"] = {
            "$gte": datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0),
            "$lte": datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=7),
        }

    year_goals = list(
        mongo.db.goals.find(year_query).sort("created_at", -1)
    )

    recurring_query = {
        "user_id": current_user.id,
        "category": CATEGORY_RECURRING,
    }
    if selected_subcategory:
        recurring_query["subcategory"] = selected_subcategory
    if selected_due_filter == "past_due":
        recurring_query["due_date"] = {"$lt": datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)}
    elif selected_due_filter == "due_soon":
        recurring_query["due_date"] = {
            "$gte": datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0),
            "$lte": datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=7),
        }

    recurring_goals = list(
        mongo.db.goals.find(recurring_query).sort("created_at", -1)
    )

    for goal in year_goals + recurring_goals:
        goal["progress_percent"] = calculate_progress(goal)
        goal["completed_count"] = sum(1 for item in goal.get("key_results", []) if item.get("completed"))
        goal["total_count"] = len(goal.get("key_results", []))
        goal["due_status"] = calculate_due_status(goal)

    year_goals = [json_safe(goal) for goal in year_goals]
    recurring_goals = [json_safe(goal) for goal in recurring_goals]

    return render_template(
        "goals.html",
        year_goals=year_goals,
        recurring_goals=recurring_goals,
        selected_tab=selected_tab,
        selected_subcategory=selected_subcategory,
        selected_due_filter=selected_due_filter,
        current_year=current_year,
        subcategories=get_goal_subcategories(),
        quarters=QUARTERS,
        priorities=PRIORITIES,
    )


@goals_bp.route("/create", methods=["POST"])
@login_required
def create_goal():
    title = request.form.get("title", "").strip()
    if not title:
        flash("Goal title cannot be blank.", "warning")
        return redirect(url_for("goals.index", tab=request.form.get("tab", "year")))

    goal_payload = build_goal_payload(request.form)
    goal_payload.update(
        {
            "goal_id": str(ObjectId()),
            "user_id": current_user.id,
            "created_at": datetime.utcnow(),
        }
    )
    mongo.db.goals.insert_one(goal_payload)
    flash("Goal added successfully.", "success")
    return redirect(url_for("goals.index", tab=request.form.get("tab", "year")))


@goals_bp.route("/update/<string:goal_id>", methods=["POST"])
@login_required
def update_goal(goal_id):
    goal_doc = mongo.db.goals.find_one({"goal_id": goal_id, "user_id": current_user.id})
    if not goal_doc:
        flash("Goal not found.", "warning")
        return redirect(url_for("goals.index"))

    existing_results = {item["title"]: item.get("completed", False) for item in goal_doc.get("key_results", [])}
    updated_payload = build_goal_payload(request.form, existing_results=existing_results)
    mongo.db.goals.update_one(
        {"goal_id": goal_id, "user_id": current_user.id},
        {"$set": updated_payload},
    )
    flash("Goal updated successfully.", "success")
    return redirect(url_for("goals.index", tab=request.form.get("tab", "year")))


@goals_bp.route("/delete/<string:goal_id>", methods=["POST"])
@login_required
def delete_goal(goal_id):
    result = mongo.db.goals.delete_one({"goal_id": goal_id, "user_id": current_user.id})
    if result.deleted_count:
        flash("Goal removed successfully.", "success")
    else:
        flash("Could not delete the requested goal.", "warning")
    return redirect(url_for("goals.index", tab=request.form.get("tab", "year")))


@goals_bp.route("/toggle/<string:goal_id>/<string:key_result_id>", methods=["POST"])
@login_required
def toggle_key_result(goal_id, key_result_id):
    goal_doc = mongo.db.goals.find_one({"goal_id": goal_id, "user_id": current_user.id})
    if not goal_doc:
        flash("Goal not found.", "warning")
        return redirect(url_for("goals.index"))

    key_results = goal_doc.get("key_results", [])
    for item in key_results:
        if item["id"] == key_result_id:
            item["completed"] = not item.get("completed", False)
            break

    completed_flag = bool(key_results) and all(item.get("completed", False) for item in key_results)
    mongo.db.goals.update_one(
        {"goal_id": goal_id, "user_id": current_user.id},
        {"$set": {"key_results": key_results, "completed": completed_flag, "updated_at": datetime.utcnow()}},
    )
    return redirect(url_for("goals.index", tab=request.args.get("tab", "year")))


@goals_bp.route("/rollover", methods=["POST"])
@login_required
def rollover_goals():
    current_year = datetime.utcnow().year
    previous_year = current_year - 1
    candidates = list(
        mongo.db.goals.find(
            {
                "user_id": current_user.id,
                "category": CATEGORY_YEAR,
                "year": previous_year,
            }
        )
    )

    incomplete = []
    for goal in candidates:
        if any(not item.get("completed", False) for item in goal.get("key_results", [])):
            new_goal = {
                "goal_id": str(ObjectId()),
                "user_id": current_user.id,
                "title": goal.get("title", ""),
                "description": goal.get("description", ""),
                "category": CATEGORY_YEAR,
                "subcategory": goal.get("subcategory", ""),
                "priority": goal.get("priority", "Medium"),
                "year": current_year,
                "quarter": "",
                "key_results": [
                    {"id": str(ObjectId()), "title": item.get("title", ""), "completed": False}
                    for item in goal.get("key_results", [])
                ],
                "completed": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "rolled_over_from_year": previous_year,
            }
            incomplete.append(new_goal)

    if incomplete:
        mongo.db.goals.insert_many(incomplete)
    flash(f"Rollover completed: {len(incomplete)} incomplete goal(s) copied into {current_year}.", "success")
    return redirect(url_for("goals.index", tab="year"))
