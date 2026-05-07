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
    return jsonify({
        "keywords": [{"keyword": kw, "weight": w} for kw, w in CIVIL_KEYWORDS]
    })


@app.route("/api/jobs", methods=["GET"])
def get_jobs():
    """
    GET /api/jobs

    Query params:
        min_match   float   Minimum match % to include (default 0)
        page        int     Page number (default 1, ignored if all_pages=true)
        all_pages   bool    Fetch all pages — slow, use sparingly (default false)
        tag_id      str     Optional Fastwork category UUID
    """
    try:
        min_match = float(request.args.get("min_match", 0))
        page      = max(1, int(request.args.get("page", 1)))
        all_pages = request.args.get("all_pages", "false").lower() == "true"
        tag_id    = request.args.get("tag_id", "")
    except (ValueError, TypeError) as e:
        return jsonify({"error": f"Invalid query parameter: {e}"}), 400

    try:
        result = scrape_jobs(
            min_match_pct=min_match,
            page=page,
            all_pages=all_pages,
            tag_id=tag_id,
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/jobs/civil", methods=["GET"])
def get_civil_jobs():
    """Convenience endpoint — returns only jobs with match_percentage > 0."""
    try:
        page      = max(1, int(request.args.get("page", 1)))
        all_pages = request.args.get("all_pages", "false").lower() == "true"
    except (ValueError, TypeError) as e:
        return jsonify({"error": f"Invalid query parameter: {e}"}), 400

    try:
        result = scrape_jobs(min_match_pct=1.0, page=page, all_pages=all_pages)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
