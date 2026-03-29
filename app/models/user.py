from flask_login import UserMixin


class User(UserMixin):
    def __init__(self, data):
        self.data = data
        self.id = data.get("user_id")
        self.email = data.get("email", "")
        self.name = data.get("name", "")
        self.is_admin = data.get("is_admin", False)
        self.created_at = data.get("created_at")
