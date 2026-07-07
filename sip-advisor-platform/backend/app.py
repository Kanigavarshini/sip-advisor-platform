"""
app.py
------
Main entrypoint. Wires up all route blueprints and serves the frontend
dashboard as static files so the whole platform runs from one command:

    python app.py

Then open http://localhost:5000 in your browser.
"""

import os
from flask import Flask, send_from_directory
from flask_cors import CORS

from routes.clients import clients_bp
from routes.reports import reports_bp
from routes.reminders import reminders_bp
from routes.analytics import analytics_bp
from routes.assistant import assistant_bp

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)

app.register_blueprint(clients_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(reminders_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(assistant_bp)


@app.route("/")
def serve_dashboard():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(debug=True, port=5000)
