from flask import Flask, jsonify, request
from flask_cors import CORS

from scraper import scrape_jobs, CIVIL_KEYWORDS, MAX_PAGES

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
        min_match  float  Minimum match % to include (default 0)
        pages      int    Number of pages to fetch, 1–80 (default 5 = 250 jobs)
    """
    try:
        min_match = float(request.args.get("min_match", 0))
        pages     = max(1, min(int(request.args.get("pages", 5)), MAX_PAGES))
    except (ValueError, TypeError) as e:
        return jsonify({"error": f"Invalid query parameter: {e}"}), 400

    try:
        result = scrape_jobs(min_match_pct=min_match, pages=pages)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/jobs/civil", methods=["GET"])
def get_civil_jobs():
    """
    Convenience endpoint — only returns jobs with at least one keyword match,
    sorted by relevance.
    """
    try:
        pages = max(1, min(int(request.args.get("pages", 5)), MAX_PAGES))
    except (ValueError, TypeError) as e:
        return jsonify({"error": f"Invalid query parameter: {e}"}), 400

    try:
        result = scrape_jobs(min_match_pct=1.0, pages=pages)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
