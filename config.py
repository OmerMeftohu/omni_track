import os
import secrets

def _get_secret_key():
    key = os.environ.get('SECRET_KEY')
    if key:
        return key
    # Persist a generated key in a local file so it survives restarts
    key_file = os.path.join(os.path.dirname(__file__), '.secret_key')
    if os.path.exists(key_file):
        with open(key_file, 'r') as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    with open(key_file, 'w') as f:
        f.write(key)
    return key

class Config:
    SECRET_KEY = _get_secret_key()
    DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
    DB_PATH = os.environ.get('DB_PATH', 'omni.db')
    WTF_CSRF_ENABLED = True
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour session timeout
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'localhost')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_EMAIL = os.environ.get('MAIL_EMAIL')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')