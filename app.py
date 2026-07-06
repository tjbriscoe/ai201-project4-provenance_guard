"""
Provenance Guard -- final integrated app.

Combines:
  - POST /submit  -- runs the pipeline, returns transparency label + score
  - POST /appeal  -- accepts content_id + creator_reasoning, updates status,
                     logs the appeal alongside the original classification
  - GET  /log     -- returns structured audit log entries
  - Rate limiting on /submit via Flask-Limiter

Storage: in-memory dicts/lists for this stage. Replace with a real DB
before production use -- everything resets on restart.
"""

import uuid
from datetime import datetime, timezone
from flask import Flask, request, jsonify

from pipeline import run_pipeline, get_transparency_label, ConfidenceBand

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Rate limiting -- real Flask-Limiter setup. Falls back to a no-op decorator
# ONLY if flask_limiter isn't installed, so this file can still be read/run
# in environments without it (e.g. this sandbox, which has no network
# access to pip install). Your real environment should use the top branch.
# ---------------------------------------------------------------------------
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=[],
        storage_uri="memory://",
    )
    RATE_LIMIT_DECORATOR = limiter.limit("10 per minute;100 per day")
except ImportError:
    print("WARNING: flask_limiter not installed -- rate limiting is DISABLED. "
          "Install with: pip install flask-limiter")

    def RATE_LIMIT_DECORATOR(f):
        return f

# ---------------------------------------------------------------------------
# In-memory storage
# ---------------------------------------------------------------------------
CASES = {}       # content_id -> case record
AUDIT_LOG = []   # list of structured log entries, append-only


def append_log_entry(entry: dict):
    AUDIT_LOG.append(entry)


# ---------------------------------------------------------------------------
# POST /submit
# ---------------------------------------------------------------------------
@app.route("/submit", methods=["POST"])
@RATE_LIMIT_DECORATOR
def submit():
    data = request.get_json(silent=True) or {}
    text = data.get("text")
    creator_id = data.get("creator_id")

    if not text or not text.strip():
        return jsonify({"error": "text is required"}), 400
    if not creator_id:
        return jsonify({"error": "creator_id is required"}), 400

    content_id = str(uuid.uuid4())
    result = run_pipeline(text, domain="general")
    transparency = get_transparency_label(result.confidence_band)

    # Store case for later lookup (by /appeal, /log)
    CASES[content_id] = {
        "text": text,
        "creator_id": creator_id,
        "confidence_band": result.confidence_band.value,
        "status": "classified",
        "appeal_reasoning": None,
    }

    log_entry = result.to_log_entry(case_id=content_id, actor="system")
    log_entry["transparencyLabel"] = transparency["label"]
    log_entry["transparencyKey"] = transparency["key"]
    append_log_entry(log_entry)

    return jsonify({
        "content_id": content_id,
        "confidence_band": result.confidence_band.value,
        "combined_score": result.net_score,
        "transparency_label": transparency["label"],
        "transparency_key": transparency["key"],
        "patterns": transparency["patterns"],
        "signals": [
            {"name": s.name, "direction": s.direction.value, "weight": s.weight.name, "score": s.score()}
            for s in result.signals
        ],
    }), 200


# ---------------------------------------------------------------------------
# POST /appeal
# ---------------------------------------------------------------------------
@app.route("/appeal-form", methods=["GET"])
def appeal_form():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>File an Appeal — Provenance Guard</title>
        <style>
            body { font-family: sans-serif; max-width: 600px; margin: 40px auto; padding: 0 20px; }
            label { display: block; margin-top: 16px; font-weight: bold; }
            input, textarea { width: 100%; padding: 8px; margin-top: 4px; box-sizing: border-box; }
            textarea { height: 120px; }
            button { margin-top: 20px; padding: 10px 20px; cursor: pointer; }
            #result { margin-top: 20px; padding: 12px; border-radius: 4px; display: none; white-space: pre-wrap; }
            #result.success { background: #d4edda; color: #155724; display: block; }
            #result.error { background: #f8d7da; color: #721c24; display: block; }
        </style>
    </head>
    <body>
        <h1>File an Appeal</h1>
        <p>Use the <code>content_id</code> from a previous <code>/submit</code> response.</p>

        <form id="appealForm">
            <label for="content_id">Content ID</label>
            <input type="text" id="content_id" name="content_id" required
                   placeholder="e.g. f95f9001-87af-46f6-bb82-3d55cbac2d45">

            <label for="creator_reasoning">Your Reasoning</label>
            <textarea id="creator_reasoning" name="creator_reasoning" required
                      placeholder="Explain why you believe this classification is incorrect..."></textarea>

            <button type="submit">Submit Appeal</button>
        </form>

        <div id="result"></div>

        <script>
            document.getElementById('appealForm').addEventListener('submit', async function(e) {
                e.preventDefault();
                const contentId = document.getElementById('content_id').value;
                const reasoning = document.getElementById('creator_reasoning').value;
                const resultDiv = document.getElementById('result');

                try {
                    const response = await fetch('/appeal', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            content_id: contentId,
                            creator_reasoning: reasoning
                        })
                    });
                    const data = await response.json();

                    if (response.ok) {
                        resultDiv.className = 'success';
                        resultDiv.textContent = JSON.stringify(data, null, 2);
                    } else {
                        resultDiv.className = 'error';
                        resultDiv.textContent = 'Error: ' + JSON.stringify(data, null, 2);
                    }
                } catch (err) {
                    resultDiv.className = 'error';
                    resultDiv.textContent = 'Request failed: ' + err.message;
                }
            });
        </script>
    </body>
    </html>
    """, 200


@app.route("/appeal", methods=["POST"])
def appeal():
    data = request.get_json(silent=True) or {}
    content_id = data.get("content_id")
    creator_reasoning = data.get("creator_reasoning")

    if not content_id:
        return jsonify({"error": "content_id is required"}), 400
    if not creator_reasoning or not creator_reasoning.strip():
        return jsonify({"error": "creator_reasoning is required"}), 400

    case = CASES.get(content_id)
    if case is None:
        return jsonify({"error": "content_id not found"}), 404

    case["status"] = "under_review"
    case["appeal_reasoning"] = creator_reasoning

    append_log_entry({
        "caseId": content_id,
        "action": "appeal_submitted",
        "status": "under_review",
        "appeal_reasoning": creator_reasoning,
        "originalConfidenceBand": case["confidence_band"],
        "actor": data.get("creator_id", case.get("creator_id", "unknown")),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return jsonify({
        "content_id": content_id,
        "status": "under_review",
        "message": "Your appeal was received and is under review.",
    }), 201


# ---------------------------------------------------------------------------
# GET /log
# ---------------------------------------------------------------------------
@app.route("/log", methods=["GET"])
def get_log():
    content_id = request.args.get("content_id")

    appealed_case_ids = {e["caseId"] for e in AUDIT_LOG if e.get("action") == "appeal_submitted"}

    entries = []
    for e in AUDIT_LOG:
        entry = dict(e)  # shallow copy so we don't mutate AUDIT_LOG itself
        if entry.get("action") == "classification":
            entry["appealFiled"] = entry["caseId"] in appealed_case_ids
        entries.append(entry)

    if content_id:
        entries = [e for e in entries if e.get("caseId") == content_id]

    return jsonify({"entries": entries}), 200


if __name__ == "__main__":
    app.run(port=5000, debug=True)