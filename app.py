from flask import Flask
from config import Config
from models import init_db
from routes import app

if __name__ == "__main__":
    init_db()
    app.config.from_object(Config)
    app.secret_key = Config.SECRET_KEY
    app.run(debug=Config.DEBUG)