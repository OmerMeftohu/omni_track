import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
    DB_PATH = os.environ.get('DB_PATH', 'omni.db')
    WTF_CSRF_ENABLED = True
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour session timeout
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'localhost')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_EMAIL = os.environ.get('MAIL_EMAIL')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')