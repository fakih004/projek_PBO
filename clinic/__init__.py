import os
import secrets
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv
from flask import Flask, render_template
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3

db = SQLAlchemy()
login = LoginManager()
csrf = CSRFProtect()


@event.listens_for(Engine, 'connect')
def sqlite_setup(connection, _):
    if isinstance(connection, sqlite3.Connection):
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA busy_timeout=15000')
        connection.execute('PRAGMA journal_mode=WAL')


def create_app(config=None):
    load_dotenv()
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(exist_ok=True)
    key_file = Path(app.instance_path) / '.secret'
    if not key_file.exists():
        key_file.write_text(secrets.token_hex(32), encoding='utf8')
    app.config.update(
        SECRET_KEY=os.getenv('SECRET_KEY') or key_file.read_text(encoding='utf8'),
        SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', 'sqlite:///medika.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8), MAX_CONTENT_LENGTH=1024*1024,
    )
    if config:
        app.config.update(config)
    db.init_app(app)
    login.init_app(app)
    csrf.init_app(app)
    login.login_view = 'web.login_page'
    from .models import User
    @login.user_loader
    def load_user(user_id):
        user = db.session.get(User, int(user_id))
        return user if user and user.active else None
    from .routes import web
    app.register_blueprint(web)
    from .services import LABELS
    app.jinja_env.globals.update(labels=LABELS)
    app.jinja_env.filters['rupiah'] = lambda v: 'Rp' + f'{int(v or 0):,}'.replace(',', '.')
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(400)
    def error(error):
        return render_template('error.html', error=error), error.code
    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'same-origin'
        if response.mimetype in ('text/html', 'application/json'):
            response.headers['Cache-Control'] = 'no-store'
        return response
    with app.app_context():
        db.create_all()
    return app
