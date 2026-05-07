import time
import logging
from dataclasses import dataclass, field, asdict

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

JOBS_PAGE_URL = "https://jobboard.fastwork.co/jobs"
API_URL       = "https://jobboard-api.fastwork.co/api/jobs"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "th,en;q=0.9",
    "Referer": JOBS_PAGE_URL,
    "Origin": "https://jobboard.fastwork.co",
}

# ---------------------------------------------------------------------------
# Keyword definitions
# ---------------------------------------------------------------------------

# Each entry: (keyword, weight) — weight 2 = high relevance, 1 = moderate
CIVIL_KEYWORDS: list[tuple[str, int]] = [
    # Core job-spec terms
    ("BOQ", 2),
    ("bill of quantities", 2),
    ("BoQ", 2),
    ("AutoCAD", 2),
    ("autocad", 2),
    ("drawing", 2),
    ("shop drawing", 2),
    # Thai core
    ("ออกแบบบ้าน", 2),
    ("โครงสร้าง", 2),
    ("วิศวกร", 2),
    ("โยธา", 2),
    ("วิศวกรโยธา", 2),
    ("เขียนแบบ", 2),
    # Related Thai terms
    ("สถาปนิก", 1),
    ("สถาปัตย์", 1),
    ("ก่อสร้าง", 1),
    ("ผังเมือง", 1),
    ("สำรวจ", 1),
    ("ประมาณราคา", 1),
    ("ประมาณการ", 1),
    ("รีโนเวท", 1),
    ("ปรับปรุง", 1),
    ("เสาเข็ม", 2),
    ("ฐานราก", 2),
    ("คาน", 1),
    ("เสา", 1),
    ("แบบก่อสร้าง", 2),
    ("permit", 1),
    ("ขออนุญาต", 1),
    # Software / tools
    ("Revit", 2),
    ("SketchUp", 1),
    ("ArchiCAD", 1),
    ("3ds Max", 1),
    ("Lumion", 1),
    ("SAP2000", 2),
    ("ETABS", 2),
    ("structural", 2),
    ("civil", 2),
    ("architect", 1),
    ("architecture", 1),
    ("renovation", 1),
    ("foundation", 2),
    ("steel", 1),
    ("concrete", 1),
    ("site plan", 1),
]

MAX_POSSIBLE_SCORE = sum(w for _, w in CIVIL_KEYWORDS)

# API returns a fixed 50 results per page; we cap all-pages scrapes here
# to avoid hammering the server on free-tier deploys.
MAX_PAGES = 80


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class JobListing:
    title: str
    description: str
    budget: str
    posted_time: str
    job_url: str
    category: str = ""
    job_type: str = ""
    match_score: int = 0
    match_percentage: float = 0.0
    matched_keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["match_percentage"] = round(d["match_percentage"], 1)
        return d


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_budget(raw) -> str:
    """Convert raw budget value (e.g. '15001') to '฿15,001'."""
    if not raw:
        return "ไม่ระบุ"
    try:
        return f"฿{int(raw):,}"
    except (ValueError, TypeError):
        return str(raw)


def compute_match(title: str, description: str) -> tuple[int, float, list[str]]:
    """Return (raw_score, percentage, matched_keyword_list)."""
    text = f"{title} {description}".lower()
    score = 0
    matched: list[str] = []
    for kw, weight in CIVIL_KEYWORDS:
        if kw.lower() in text:
            score += weight
            matched.append(kw)
    pct = min((score / MAX_POSSIBLE_SCORE) * 100, 100.0)
    return score, pct, matched


# ---------------------------------------------------------------------------
# API mapping
# ---------------------------------------------------------------------------

def _map_api_job(raw: dict) -> JobListing:
    """Map one item from the Fastwork /api/jobs response to a JobListing."""
    job_id    = raw.get("id", "")
    title     = raw.get("title") or "Unknown"
    description = raw.get("description") or ""
    budget    = _format_budget(raw.get("budget"))
    posted_time = raw.get("inserted_at") or raw.get("updated_at") or "ไม่ระบุ"
    job_url   = f"{JOBS_PAGE_URL}/{job_id}" if job_id else ""
    category  = (raw.get("tag") or {}).get("name", "")
    job_type  = raw.get("type", "")

    score, pct, matched = compute_match(title, description)

    return JobListing(
        title=title,
        description=description,
        budget=budget,
        posted_time=posted_time,
        job_url=job_url,
        category=category,
        job_type=job_type,
        match_score=score,
        match_percentage=pct,
        matched_keywords=matched,
    )


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------

def _fetch_page(session: requests.Session, page: int, tag_id: str = "") -> tuple[list[JobListing], dict]:
    """Fetch a single page from the API. Returns (jobs, meta)."""
    params: dict = {"page": page}
    if tag_id:
        params["tag_id"] = tag_id

    resp = session.get(API_URL, params=params, timeout=15)
    resp.raise_for_status()

    data = resp.json()
    jobs = [_map_api_job(j) for j in data.get("data", [])]
    meta = data.get("meta", {})
    return jobs, meta


def _fetch_all_pages(
    session: requests.Session,
    tag_id: str = "",
    request_delay: float = 0.5,
) -> tuple[list[JobListing], dict]:
    """Fetch every page and return combined job list plus the last meta."""
    all_jobs: list[JobListing] = []
    meta: dict = {}
    page = 1

    while True:
        logger.info("Fetching page %d …", page)
        jobs, meta = _fetch_page(session, page, tag_id)
        all_jobs.extend(jobs)

        total_pages = meta.get("total_pages", 1)
        logger.info("  page %d/%d — %d jobs so far", page, total_pages, len(all_jobs))

        if page >= total_pages or page >= MAX_PAGES:
            break

        page += 1
        time.sleep(request_delay)

    return all_jobs, meta


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scrape_jobs(
    min_match_pct: float = 0.0,
    page: int = 1,
    all_pages: bool = False,
    tag_id: str = "",
) -> dict:
    """
    Fetch Fastwork job listings from the official API.

    Args:
        min_match_pct: Only return jobs at or above this match %.
        page:          Which page to fetch (ignored when all_pages=True).
        all_pages:     Fetch every page (up to MAX_PAGES). Slow — use wisely.
        tag_id:        Optional Fastwork category UUID to filter by.

    Returns a dict:
        {
            "jobs":            [{...}, ...],
            "total":           <filtered count>,
            "total_available": <total on Fastwork>,
            "total_pages":     <pages on Fastwork>,
            "current_page":    <page fetched>,
            "source":          "api",
        }
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        if all_pages:
            all_jobs, meta = _fetch_all_pages(session, tag_id)
        else:
            all_jobs, meta = _fetch_page(session, page, tag_id)
    except requests.RequestException as e:
        logger.error("API request failed: %s", e)
        raise

    if min_match_pct > 0:
        all_jobs = [j for j in all_jobs if j.match_percentage >= min_match_pct]

    all_jobs.sort(key=lambda j: j.match_percentage, reverse=True)

    return {
        "jobs":            [j.to_dict() for j in all_jobs],
        "total":           len(all_jobs),
        "total_available": meta.get("total_count", 0),
        "total_pages":     meta.get("total_pages", 1),
        "current_page":    meta.get("current_page", page),
        "source":          "api",
    }
