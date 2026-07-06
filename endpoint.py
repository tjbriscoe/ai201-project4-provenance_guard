"""
POST /appeal endpoint -- implements Stage 2 (submission) and Stage 3
(triage) of the appeals workflow diagram.

Assumes:
  - CASES: dict mapping content_id -> case record (from /submit),
    including at least {"confidence_band": str, "status": str}
  - append_log_entry(entry: dict): appends to the audit log

Per diagram:
  Stage 2 requires: statement of dispute + supporting evidence
  Stage 3 routes by ORIGINAL confidence: strong_* -> full_review,
                                          everything else -> fast_track
"""

from flask import Flask, request, jsonify
from datetime import datetime, timezone
from pipeline import ConfidenceBand, triage_appeal

app = Flask(__name__)

# Placeholder stores -- replace with real DB / log store.
CASES = {}


def append_log_entry(entry: dict):
    # Placeholder -- replace with real audit log persistence.
    print("[audit log]", entry)


@app.route("/appeal", methods=["POST"])
def appeal():
    data = request.get_json(silent=True) or {}
    content_id = data.get("content_id")
    statement = data.get("statement")
    evidence = data.get("evidence", [])

    # --- Stage 2 validation: statement + evidence required ---
    if not content_id:
        return jsonify({"error": "content_id is required"}), 400
    if not statement or not statement.strip():
        return jsonify({"error": "statement is required"}), 400
    if not evidence:
        return jsonify({"error": "supporting evidence is required"}), 400

    case = CASES.get(content_id)
    if case is None:
        return jsonify({"error": "content_id not found"}), 404
    if case.get("status") == "appeal_pending":
        return jsonify({"error": "an appeal is already pending for this case"}), 409

    # --- Stage 3 triage: route by ORIGINAL confidence band ---
    original_band = ConfidenceBand(case["confidence_band"])
    review_track = triage_appeal(original_band)  # "fast_track" or "full_review"

    # --- Update status ---
    case["status"] = "appeal_pending"
    case["review_track"] = review_track
    case["appeal_statement"] = statement
    case["appeal_evidence"] = evidence

    # --- Log the appeal submission + triage decision ---
    append_log_entry({
        "caseId": content_id,
        "action": "appeal_submitted",
        "confidenceBand": original_band.value,
        "reviewTrack": review_track,
        "evidenceCount": len(evidence),
        "actor": data.get("creator_id", "unknown"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "notes": statement,
    })

    return jsonify({
        "content_id": content_id,
        "status": "appeal_pending",
        "review_track": review_track,
        "message": (
            "Your appeal was received and is under review."
            if review_track == "fast_track"
            else "Your appeal was received. Given the original confidence level, "
                 "this case will undergo full review with a second reviewer."
        ),
    }), 201


if __name__ == "__main__":
    app.run(port=5000, debug=True)