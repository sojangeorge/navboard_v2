from functools import wraps
from flask import abort
from flask_login import current_user
from . import mongo

DEFAULT_GOAL_SUBCATEGORIES = ["Kids", "Financials", "Learning", "Home Improvement"]


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(current_user, "is_admin", False):
            abort(403)
        return view(*args, **kwargs)

    return wrapped_view

def get_goal_subcategories():
    doc = mongo.db.goal_subcategories.find_one({"_id": "goal_subcategories"})
    if not doc or not isinstance(doc.get("subcategories"), list):
        defaults = DEFAULT_GOAL_SUBCATEGORIES.copy()
        mongo.db.goal_subcategories.update_one(
            {"_id": "goal_subcategories"},
            {"$setOnInsert": {"subcategories": defaults}},
            upsert=True,
        )
        return defaults
    return doc["subcategories"]


def save_goal_subcategories(subcategories):
    mongo.db.goal_subcategories.update_one(
        {"_id": "goal_subcategories"},
        {"$set": {"subcategories": subcategories}},
        upsert=True,
    )