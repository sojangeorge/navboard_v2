from datetime import datetime
from uuid import uuid4

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from .. import mongo

expenses_bp = Blueprint("expenses", __name__, url_prefix="/expenses")

DEFAULT_EXPENSE_CATEGORIES = [
    "Housing",
    "Food",
    "Utilities",
    "Transportation",
    "Health",
    "Entertainment",
    "Savings",
    "Miscellaneous",
]

MONTH_LABELS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def get_user_categories(user_id):
    doc = mongo.db.expense_categories.find_one({"user_id": user_id})
    if not doc or not isinstance(doc.get("categories"), list):
        categories = DEFAULT_EXPENSE_CATEGORIES.copy()
        mongo.db.expense_categories.update_one(
            {"user_id": user_id},
            {"$set": {"categories": categories}},
            upsert=True,
        )
        return categories
    return doc["categories"]


def get_budget_map(user_id):
    budget_map = {}
    for doc in mongo.db.expense_budgets.find({"user_id": user_id}):
        budget_map[doc["category"]] = doc.get("monthly_budget", 0.0)
    return budget_map


def load_expense_grid(user_id, year, categories):
    grid = {
        category: {month: 0.0 for month in range(1, 13)}
        for category in categories
    }

    expenses = mongo.db.expenses.find({
        "user_id": user_id,
        "year_month": {"$regex": f"^{year}-"},
    })

    for record in expenses:
        category = record.get("category")
        if category not in grid:
            continue
        month = int(record.get("year_month", "0000-00")[5:7])
        grid[category][month] = record.get("amount", 0.0)

    return grid


def parse_amount(value):
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0


def build_expense_summaries(grid, budgets):
    totals = {}
    for category, months in grid.items():
        totals[category] = round(sum(months.values()), 2)
    overall_actual = round(sum(totals.values()), 2)
    overall_budget = round(sum(budgets.get(category, 0.0) for category in grid.keys()), 2)
    return totals, overall_actual, overall_budget


def upsert_expense(user_id, category, year_month, amount):
    if amount <= 0:
        mongo.db.expenses.delete_one({
            "user_id": user_id,
            "category": category,
            "year_month": year_month,
        })
        return

    mongo.db.expenses.update_one(
        {
            "user_id": user_id,
            "category": category,
            "year_month": year_month,
        },
        {
            "$set": {
                "amount": amount,
                "updated_at": datetime.utcnow(),
                "entry_id": uuid4().hex,
            }
        },
        upsert=True,
    )


@expenses_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    user_id = current_user.id
    categories = get_user_categories(user_id)

    if request.method == "POST":
        if request.form.get("action") == "add_category":
            new_category = request.form.get("new_category", "").strip()
            if new_category and new_category not in categories:
                categories.append(new_category)
                mongo.db.expense_categories.update_one(
                    {"user_id": user_id},
                    {"$set": {"categories": categories}},
                    upsert=True,
                )
                flash("New expense category added.", "success")
            else:
                flash("Enter a unique category name.", "warning")
            return redirect(url_for("expenses.index"))

        budget_map = get_budget_map(user_id)
        year = int(request.form.get("year", datetime.utcnow().year))

        for index, category in enumerate(categories):
            budget_amount = parse_amount(request.form.get(f"budget_{index}", 0))
            mongo.db.expense_budgets.update_one(
                {"user_id": user_id, "category": category},
                {"$set": {
                    "monthly_budget": budget_amount,
                    "updated_at": datetime.utcnow(),
                }},
                upsert=True,
            )
            for month in range(1, 13):
                amount = parse_amount(request.form.get(f"expense_{index}_{month}", 0))
                year_month = f"{year}-{month:02d}"
                upsert_expense(user_id, category, year_month, amount)

        flash("Expense grid saved successfully.", "success")
        return redirect(url_for("expenses.index"))

    year = datetime.utcnow().year
    category_grid = load_expense_grid(user_id, year, categories)
    budget_map = get_budget_map(user_id)
    category_totals, overall_actual, overall_budget = build_expense_summaries(category_grid, budget_map)

    bar_labels = categories
    bar_actuals = [category_totals.get(category, 0.0) for category in categories]
    bar_budgets = [budget_map.get(category, 0.0) for category in categories]
    donut_values = [category_totals.get(category, 0.0) for category in categories]

    return render_template(
        "expenses.html",
        categories=categories,
        month_labels=MONTH_LABELS,
        year=year,
        category_grid=category_grid,
        budget_map=budget_map,
        category_totals=category_totals,
        overall_actual=overall_actual,
        overall_budget=overall_budget,
        bar_labels=bar_labels,
        bar_actuals=bar_actuals,
        bar_budgets=bar_budgets,
        donut_values=donut_values,
    )
