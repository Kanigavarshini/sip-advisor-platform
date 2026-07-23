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
from routes.dataset import dataset_bp
from routes.proposals import proposals_bp
from routes.leads import leads_bp
from routes.client_profile import client_profile_bp
from models.db import init_proposal_tables, init_leads_tables, init_client_extension_tables

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)

app.register_blueprint(clients_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(reminders_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(assistant_bp)
app.register_blueprint(dataset_bp)
app.register_blueprint(proposals_bp)
app.register_blueprint(leads_bp)
app.register_blueprint(client_profile_bp)

init_proposal_tables()
init_leads_tables()
init_client_extension_tables()


@app.route("/")
def serve_dashboard():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(debug=True, port=5000)
