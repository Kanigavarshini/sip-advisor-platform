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
import sqlite3
from flask import Blueprint, request, jsonify
from services.ingestion import run_ingestion, add_manual_client, DatasetValidationError, DATA_DIR, DB_FILE

dataset_bp = Blueprint("dataset", __name__)

ALLOWED_EXTENSIONS = {".xlsx", ".xls"}
UPLOAD_TARGET_BASE = os.path.join(DATA_DIR, "RupeeVyze_SIP_Mock_Dataset")


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

    # Keep the file's real extension (.xls vs .xlsx) so it's always read with
    # the correct Excel engine -- saving an .xls file under a .xlsx name (or
    # vice versa) can trip up the reader depending on the pandas/engine version.
    upload_target = UPLOAD_TARGET_BASE + ext
    backup_path = upload_target + ".backup"
    if os.path.exists(upload_target):
        os.replace(upload_target, backup_path)

    try:
        file.save(upload_target)
        summary = run_ingestion(upload_target)
        # Success -- remove the backup, no longer needed
        if os.path.exists(backup_path):
            os.remove(backup_path)
        added = summary["records_loaded"]
        total = summary["total_records"]
        already_there = total - added
        note = (
            f" ({already_there} record(s) were already in the dataset before this upload.)"
            if already_there > 0 else ""
        )
        return jsonify({
            "message": f"Dataset uploaded and dashboard refreshed successfully.{note}",
            "summary": summary,
        })
    except DatasetValidationError as e:
        # Restore the previous working file so the dashboard doesn't break
        if os.path.exists(backup_path):
            os.replace(backup_path, upload_target)
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        if os.path.exists(backup_path):
            os.replace(backup_path, upload_target)
        return jsonify({"error": f"Could not process file: {str(e)}"}), 500


@dataset_bp.route("/api/dataset/clear", methods=["DELETE"])
def clear_dataset():
    """
    Wipes ALL SIP/client records -- used to clear out demo/sample data (or
    any earlier test uploads) before loading real client data for a clean
    review. Does NOT touch leads, proposals, or client notes/activities,
    since those are separate tables.
    """
    conn = sqlite3.connect(DB_FILE)
    conn.execute("DELETE FROM sips")
    conn.commit()
    conn.close()
    return jsonify({"message": "All client/SIP data has been cleared. Upload a new dataset to get started."})


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
