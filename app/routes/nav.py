from datetime import datetime
import json
from uuid import uuid4
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from .. import mongo

nav_bp = Blueprint("nav", __name__, url_prefix="/nav")

ASSET_TYPE_CHOICES = [
    ("liquid", "Liquid Asset"),
    ("illiquid", "Illiquid Asset"),
    ("investment", "Investment"),
    ("liability", "Liability"),
]

ASSET_TYPE_LABELS = {
    "liquid": "Liquid Assets",
    "illiquid": "Illiquid Assets",
    "investment": "Investments",
    "liability": "Liabilities",
}

CURRENCY_CHOICES = [
    ("USD", "USD"),
    ("INR", "INR"),
    ("GOLD", "Gold (g)"),
]

CURRENCY_RATES = {
    "USD": 1.0,
    "INR": 0.012,
    "GOLD": 80.0,
}

EXCHANGE_RATE_API_URLS = [
    "https://open.er-api.com/v6/latest/USD",
    "https://api.exchangerate-api.com/v4/latest/USD",
]

GOLD_PRICE_API_URLS = [
    "https://api.metals.live/v1/spot/gold",
    "https://api.coingecko.com/api/v3/simple/price?ids=tether-gold&vs_currencies=usd",
]

DEFAULT_GOLD_USD_PER_GRAM = CURRENCY_RATES["GOLD"]

REQUEST_USER_AGENT = "NavBoard/1.0 (+https://example.com)"

CACHE_TTL_SECONDS = 600

_rate_cache = {
    "rates": None,
    "fetched_at": 0,
}

_gold_cache = {
    "price_usd_per_gram": None,
    "fetched_at": 0,
}


def parse_amount(value):
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0


def fetch_json(url, timeout=10):
    request = Request(url, headers={"User-Agent": REQUEST_USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, ValueError):
        return None


def fetch_live_exchange_rates():
    for url in EXCHANGE_RATE_API_URLS:
        data = fetch_json(url)
        if not isinstance(data, dict):
            continue
        rates = data.get("rates") or data.get("conversion_rates")
        if rates and isinstance(rates, dict):
            return rates
    return {}


def fetch_live_gold_price_usd_per_gram():
    for url in GOLD_PRICE_API_URLS:
        data = fetch_json(url)
        if not data:
            continue

        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                if item.get("currency") == "USD" and item.get("metal", "").lower() == "gold":
                    price_per_ounce = item.get("price")
                    if price_per_ounce:
                        return round(float(price_per_ounce) / 31.1034768, 2)

        if isinstance(data, dict):
            if "tether-gold" in data:
                price_usd = data["tether-gold"].get("usd")
                if price_usd:
                    return round(float(price_usd) / 31.1034768, 2)
            if "gold" in data and isinstance(data["gold"], dict):
                price_usd = data["gold"].get("usd")
                if price_usd:
                    return round(float(price_usd) / 31.1034768, 2)
            if data.get("currency") == "USD" and data.get("metal", "").lower() == "gold":
                price_per_ounce = data.get("price")
                if price_per_ounce:
                    return round(float(price_per_ounce) / 31.1034768, 2)

    return DEFAULT_GOLD_USD_PER_GRAM


def get_exchange_rate_to_usd(currency):
    if currency == "USD":
        return 1.0

    if currency == "GOLD":
        now = datetime.utcnow().timestamp()
        if _gold_cache["price_usd_per_gram"] is None or now - _gold_cache["fetched_at"] > CACHE_TTL_SECONDS:
            _gold_cache["price_usd_per_gram"] = fetch_live_gold_price_usd_per_gram()
            _gold_cache["fetched_at"] = now
        return _gold_cache["price_usd_per_gram"]

    now = datetime.utcnow().timestamp()
    if _rate_cache["rates"] is None or now - _rate_cache["fetched_at"] > CACHE_TTL_SECONDS:
        _rate_cache["rates"] = fetch_live_exchange_rates()
        _rate_cache["fetched_at"] = now

    rate_data = _rate_cache["rates"] or {}
    if currency in rate_data:
        try:
            return 1.0 / float(rate_data[currency])
        except (TypeError, ValueError, ZeroDivisionError):
            pass

    return CURRENCY_RATES.get(currency, 1.0)


def convert_to_usd(amount, currency):
    return round(amount * get_exchange_rate_to_usd(currency), 2)


def build_nav_metrics(items):
    liquid_assets = [item for item in items if item["asset_type"] == "liquid"]
    illiquid_assets = [item for item in items if item["asset_type"] == "illiquid"]
    investments = [item for item in items if item["asset_type"] == "investment"]
    liabilities = [item for item in items if item["asset_type"] == "liability"]

    total_liquid = sum(item["amount"] for item in liquid_assets)
    total_illiquid = sum(item["amount"] for item in illiquid_assets)
    total_investments = sum(item["amount"] for item in investments)
    total_assets = total_liquid + total_illiquid + total_investments
    total_liabilities = sum(item["amount"] for item in liabilities)
    total_nav = total_assets - total_liabilities
    debt_to_asset = (total_liabilities / total_assets * 100) if total_assets > 0 else 0.0

    return {
        "liquid_assets": liquid_assets,
        "illiquid_assets": illiquid_assets,
        "investments": investments,
        "liabilities": liabilities,
        "total_liquid": total_liquid,
        "total_illiquid": total_illiquid,
        "total_investments": total_investments,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_nav": total_nav,
        "debt_to_asset": debt_to_asset,
    }


def get_nav_history(user_id):
    history = list(
        mongo.db.nav_history.find({"user_id": user_id}).sort("period", 1)
    )
    return history


def calculate_cmgr(history):
    if len(history) < 2:
        return 0.0

    first = history[0].get("nav_value", 0.0)
    last = history[-1].get("nav_value", 0.0)
    if first <= 0 or last <= 0:
        return 0.0

    months = len(history) - 1
    try:
        rate = (last / first) ** (1 / months) - 1
    except ZeroDivisionError:
        return 0.0

    return round(rate * 100, 2)


def refresh_nav_snapshot(user_id):
    items = list(
        mongo.db.nav_items.find(
            {"user_id": user_id},
            {"_id": 0, "created_at": 0, "updated_at": 0},
        )
    )
    metrics = build_nav_metrics(items)
    period = datetime.utcnow().strftime("%Y-%m")
    mongo.db.nav_history.update_one(
        {"user_id": user_id, "period": period},
        {
            "$set": {
                "nav_value": round(metrics["total_nav"], 2),
                "updated_at": datetime.utcnow(),
            }
        },
        upsert=True,
    )
    return metrics


@nav_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        item_id = request.form.get("item_id")
        item_name = request.form.get("item_name", "").strip()
        asset_type = request.form.get("asset_type", "liquid")
        category = request.form.get("category", "General").strip() or "General"
        input_amount = parse_amount(request.form.get("amount"))
        currency = request.form.get("asset_currency", "USD")
        if currency not in CURRENCY_RATES:
            currency = "USD"
        amount = convert_to_usd(input_amount, currency)

        if currency == "GOLD":
            asset_type = "illiquid"

        if not item_name:
            flash("Enter a name for the asset or liability.", "warning")
            return redirect(url_for("nav.index"))

        payload = {
            "user_id": current_user.id,
            "item_name": item_name,
            "asset_type": asset_type,
            "category": category,
            "amount": amount,
            "currency": currency,
            "original_amount": input_amount,
            "updated_at": datetime.utcnow(),
        }

        if item_id:
            mongo.db.nav_items.update_one(
                {"user_id": current_user.id, "item_id": item_id},
                {"$set": payload},
            )
            flash("NAV item updated successfully.", "success")
        else:
            payload.update({
                "item_id": uuid4().hex,
                "created_at": datetime.utcnow(),
            })
            mongo.db.nav_items.insert_one(payload)
            flash("NAV item added successfully.", "success")

        refresh_nav_snapshot(current_user.id)
        return redirect(url_for("nav.index"))

    metrics = refresh_nav_snapshot(current_user.id)
    history = get_nav_history(current_user.id)
    cmgr = calculate_cmgr(history)
    chart_labels = [doc["period"] for doc in history]
    chart_values = [doc["nav_value"] for doc in history]

    return render_template(
        "nav.html",
        asset_type_choices=ASSET_TYPE_CHOICES,
        asset_type_labels=ASSET_TYPE_LABELS,
        currency_choices=CURRENCY_CHOICES,
        liquid_assets=metrics["liquid_assets"],
        illiquid_assets=metrics["illiquid_assets"],
        liabilities=metrics["liabilities"],
        total_liquid=metrics["total_liquid"],
        total_illiquid=metrics["total_illiquid"],
        total_assets=metrics["total_assets"],
        total_investments=metrics["total_investments"],
        investments=metrics["investments"],
        total_liabilities=metrics["total_liabilities"],
        total_nav=metrics["total_nav"],
        debt_to_asset=metrics["debt_to_asset"],
        cmgr=cmgr,
        chart_labels=chart_labels,
        chart_values=chart_values,
    )


@nav_bp.route("/delete/<string:item_id>", methods=["POST"])
@login_required
def delete_item(item_id):
    mongo.db.nav_items.delete_one({"user_id": current_user.id, "item_id": item_id})
    refresh_nav_snapshot(current_user.id)
    flash("NAV item removed.", "success")
    return redirect(url_for("nav.index"))
