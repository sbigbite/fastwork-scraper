from flask import Flask, jsonify, request
from flask_cors import CORS

from scraper import scrape_jobs, CIVIL_KEYWORDS

app = Flask(__name__)
CORS(app)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/keywords", methods=["GET"])
def get_keywords():
    """Return the full keyword list with weights."""
    return jsonify(
        {
            "keywords": [
                {"keyword": kw, "weight": w} for kw, w in CIVIL_KEYWORDS
            ]
        }
    )


@app.route("/api/jobs", methods=["GET"])
def get_jobs():
    """
    GET /api/jobs

    Query params:
        min_match  float  Minimum match % to include (default 0)
        page       int    Page number (default 1)
        per_page   int    Results per page (default 50, max 100)
        category   str    Optional category filter passed to Fastwork
    """
    try:
        min_match = float(request.args.get("min_match", 0))
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", 50))))
        category = request.args.get("category", "")
    except (ValueError, TypeError) as e:
        return jsonify({"error": f"Invalid query parameter: {e}"}), 400

    try:
        result = scrape_jobs(
            min_match_pct=min_match,
            page=page,
            per_page=per_page,
            category=category,
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/jobs/civil", methods=["GET"])
def get_civil_jobs():
    """
    Convenience endpoint — returns only jobs with match_percentage > 0,
    sorted by relevance.
    """
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", 50))))
    except (ValueError, TypeError) as e:
        return jsonify({"error": f"Invalid query parameter: {e}"}), 400

    try:
        result = scrape_jobs(min_match_pct=1.0, page=page, per_page=per_page)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
