"""
routes/dataset.py
-------------------
Solution 10: lets a non-technical user (RM, manager, admin) replace the
dataset by uploading a new Excel file straight from the dashboard --
no command line, no API calls, no code. This is the "Upload Excel ->
Dashboard Updates" flow from the original problem statement.

The uploaded file is saved to disk and immediately re-ingested (same
logic as services/ingestion.py's CLI entrypoint), so the whole dashboard
reflects the new data right after upload.
"""

import os
from flask import Blueprint, request, jsonify
from services.ingestion import run_ingestion, add_manual_client, DatasetValidationError, DATA_DIR

dataset_bp = Blueprint("dataset", __name__)

ALLOWED_EXTENSIONS = {".xlsx", ".xls"}
UPLOAD_TARGET = os.path.join(DATA_DIR, "RupeeVyze_SIP_Mock_Dataset.xlsx")


@dataset_bp.route("/api/dataset/upload", methods=["POST"])
def upload_dataset():
    if "file" not in request.files:
        return jsonify({"error": "No file was sent"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": "Please upload an Excel file (.xlsx or .xls)"}), 400

    # Save a backup of the previous file in case the new one fails validation
    backup_path = UPLOAD_TARGET + ".backup"
    if os.path.exists(UPLOAD_TARGET):
        os.replace(UPLOAD_TARGET, backup_path)

    try:
        file.save(UPLOAD_TARGET)
        summary = run_ingestion(UPLOAD_TARGET)
        # Success -- remove the backup, no longer needed
        if os.path.exists(backup_path):
            os.remove(backup_path)
        return jsonify({
            "message": "Dataset uploaded and dashboard refreshed successfully",
            "summary": summary,
        })
    except DatasetValidationError as e:
        # Restore the previous working file so the dashboard doesn't break
        if os.path.exists(backup_path):
            os.replace(backup_path, UPLOAD_TARGET)
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        if os.path.exists(backup_path):
            os.replace(backup_path, UPLOAD_TARGET)
        return jsonify({"error": f"Could not process file: {str(e)}"}), 500


@dataset_bp.route("/api/dataset/add-client", methods=["POST"])
def add_client():
    """
    Adds one client/SIP record directly from a dashboard form -- an
    alternative to re-uploading the whole Excel sheet just to register a
    single new client. Appends to the existing dataset instead of
    replacing it.
    """
    data = request.get_json(force=True, silent=True) or {}
    try:
        record = add_manual_client(data)
        return jsonify({"message": "Client added successfully", "client": record}), 201
    except DatasetValidationError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Could not add client: {str(e)}"}), 500
