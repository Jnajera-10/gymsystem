import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-cambiame')
    WTF_CSRF_ENABLED = True

    # DATABASE_URL debe definirse como variable de entorno en Render.
    # Nunca hardcodear credenciales en el código.
    _db_url = os.environ.get('DATABASE_URL', '')
    if not _db_url:
        raise RuntimeError(
            'DATABASE_URL no está definida. '
            'Agrégala como variable de entorno en Render (o en tu .env local).'
        )
    # Render a veces entrega 'postgres://', SQLAlchemy necesita 'postgresql://'
    if _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Pool optimizado para Neon free tier (max 10 conexiones) + Render free (512MB)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 280,
        'pool_size': 3,
        'max_overflow': 2,
        'pool_timeout': 20,
        'connect_args': {
            'sslmode': 'require',
            'connect_timeout': 10,
            'options': '-c timezone=America/Bogota',
        }
    }

    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    TIMEZONE = 'America/Bogota'
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_MINUTES = 15
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024

    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    WHATSAPP_API_URL = os.environ.get('WHATSAPP_API_URL', '')
    WHATSAPP_TOKEN = os.environ.get('WHATSAPP_TOKEN', '')
