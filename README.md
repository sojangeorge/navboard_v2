# NavBoard

A production-ready Flask app scaffold for a personal productivity and financial management suite.

## Features
- Flask application factory with modular structure
- MongoDB Atlas integration via `pymongo`
- User authentication with `Flask-Login`
- Admin dashboard with user management and impersonation
- Tailwind CSS UI with a collapsible sidebar and dark mode toggle

## Setup
1. Install dependencies:
   ```bash
   python3 -m pip install -r requirements.txt
   ```
2. Copy environment variables:
   ```bash
   cp .env.example .env
   ```
3. Update `.env` with a secure `SECRET_KEY` and a valid `MONGO_URI`.
4. Start with Gunicorn:
   ```bash
   gunicorn wsgi:application
   ```

## Folder structure
- `app/`
  - `templates/` — Jinja2 templates and layout
  - `routes/` — blueprints for auth, dashboard, and admin
  - `models/` — Flask-Login user adapter
  - `utils.py` — shared decorators and helpers
- `wsgi.py` — production entrypoint
- `requirements.txt` — Python dependencies
