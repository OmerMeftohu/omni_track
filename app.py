import os
from flask import Flask
from config import Config
from models import init_db
from routes import app
from scheduler import start_scheduler

if __name__ == "__main__":
    init_db()
    app.config.from_object(Config)
    app.secret_key = Config.SECRET_KEY

    # Avoid running the scheduler twice when Flask's reloader forks the process
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not Config.DEBUG:
        start_scheduler()

    app.run(debug=Config.DEBUG)