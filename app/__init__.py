import os
from dotenv import load_dotenv
from flask import Flask
from flask_login import LoginManager
from pymongo import MongoClient
from .config import Config

load_dotenv()

class Mongo:
    def __init__(self):
        self.client = None
        self.db = None

    def init_app(self, app):        
        self.client = MongoClient(app.config["MONGO_URI"])
        self.db = self.client.get_default_database()
        if self.db is None:
            default_db = app.config.get("MONGO_DB_NAME")
            self.db = self.client.get_database(default_db)

mongo = Mongo()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "info"

from .models.user import User
from .routes.auth import auth_bp
from .routes.main import main_bp
from .routes.admin import admin_bp
from .routes.goals import goals_bp
from .routes.nav import nav_bp


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)

    mongo.init_app(app)
    login_manager.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(goals_bp)
    app.register_blueprint(nav_bp)

    with app.app_context():
        create_indexes()

    return app


@login_manager.user_loader
def load_user(user_id):
    user_doc = mongo.db.users.find_one({"user_id": user_id})
    if not user_doc:
        return None
    return User(user_doc)


def create_indexes():
    mongo.db.users.create_index("user_id", unique=True)
    mongo.db.users.create_index("email", unique=True)
    mongo.db.goals.create_index("goal_id", unique=True)
    mongo.db.goals.create_index([("user_id", 1), ("year", 1)])
    mongo.db.goals.create_index("category")
    mongo.db.goals.create_index("priority")

    mongo.db.nav_items.create_index("item_id", unique=True)
    mongo.db.nav_items.create_index("user_id")
    mongo.db.nav_items.create_index("asset_type")
    mongo.db.nav_history.create_index([("user_id", 1), ("period", 1)], unique=True)
