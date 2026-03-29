import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "super-secret-change-me")
    MONGO_URI = os.environ.get(
        "MONGO_URI",
        "mongodb+srv://<username>:<password>@cluster0.mongodb.net/navboard?retryWrites=true&w=majority",
    )
    MONGO_DB_NAME = os.environ.get(
        "MONGO_DB_NAME",
        "navboard",
    )
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
