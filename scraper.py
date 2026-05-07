import time
import logging
from dataclasses import dataclass, field, asdict

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

JOBS_PAGE_URL = "https://jobboard.fastwork.co/jobs"
API_URL       = "https://jobboard-api.fastwork.co/api/jobs"
TAGS_URL      = "https://jobboard-api.fastwork.co/api/tags"

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
# Civil-engineering categories (from GET /api/tags)
#
# The Fastwork API does NOT honour tag_id as a server-side filter —
# every variant we probed (tag_id, tag_ids, tag_ids[], tag, category_id,
# category, comma-separated) returned all 3 976 jobs unchanged.
# We therefore apply tag filtering client-side immediately after each page
# is fetched, discarding ~94 % of irrelevant jobs before keyword matching.
# ---------------------------------------------------------------------------

CIVIL_TAGS: dict[str, str] = {
    # id -> Thai name
    "883a6909-c772-48fa-91e9-b8162e599aba": "ช่าง",                              # trades / construction
    "d19619b6-a04a-4c26-b74b-dbfe28494a9b": "สถาปัตยกรรมและการตกแต่งภายใน",    # architecture & interior
}

# Catch-all tag — include when the caller wants broader coverage
CATCHALL_TAG_ID = "b561a88b-03e5-4f03-8a6d-ba169671797d"  # อื่นๆ

MAX_PAGES = 80  # API has ~80 pages; cap to avoid runaway requests on free tier


# ---------------------------------------------------------------------------
# Keyword definitions
# ---------------------------------------------------------------------------

CIVIL_KEYWORDS: list[tuple[str, int]] = [
    ("BOQ", 2), ("bill of quantities", 2), ("BoQ", 2),
    ("AutoCAD", 2), ("autocad", 2),
    ("drawing", 2), ("shop drawing", 2),
    ("ออกแบบบ้าน", 2), ("โครงสร้าง", 2), ("วิศวกร", 2),
    ("โยธา", 2), ("วิศวกรโยธา", 2), ("เขียนแบบ", 2),
    ("สถาปนิก", 1), ("สถาปัตย์", 1),
    ("ก่อสร้าง", 1), ("ผังเมือง", 1), ("สำรวจ", 1),
    ("ประมาณราคา", 1), ("ประมาณการ", 1),
    ("รีโนเวท", 1), ("ปรับปรุง", 1),
    ("เสาเข็ม", 2), ("ฐานราก", 2), ("คาน", 1), ("เสา", 1),
    ("แบบก่อสร้าง", 2), ("permit", 1), ("ขออนุญาต", 1),
    ("Revit", 2), ("SketchUp", 1), ("ArchiCAD", 1),
    ("3ds Max", 1), ("Lumion", 1), ("SAP2000", 2), ("ETABS", 2),
    ("structural", 2), ("civil", 2), ("architect", 1), ("architecture", 1),
    ("renovation", 1), ("foundation", 2), ("steel", 1), ("concrete", 1),
    ("site plan", 1),
]

MAX_POSSIBLE_SCORE = sum(w for _, w in CIVIL_KEYWORDS)


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
    if not raw:
        return "ไม่ระบุ"
    try:
        return f"฿{int(raw):,}"
    except (ValueError, TypeError):
        return str(raw)


def compute_match(title: str, description: str) -> tuple[int, float, list[str]]:
    text = f"{title} {description}".lower()
    score = 0
    matched: list[str] = []
    for kw, weight in CIVIL_KEYWORDS:
        if kw.lower() in text:
            score += weight
            matched.append(kw)
    pct = min((score / MAX_POSSIBLE_SCORE) * 100, 100.0)
    return score, pct, matched


def _is_civil_tag(tag_id: str, include_catchall: bool = False) -> bool:
    if tag_id in CIVIL_TAGS:
        return True
    if include_catchall and tag_id == CATCHALL_TAG_ID:
        return True
    return False


# ---------------------------------------------------------------------------
# API mapping
# ---------------------------------------------------------------------------

def _map_api_job(raw: dict) -> JobListing:
    job_id      = raw.get("id", "")
    title       = raw.get("title") or "Unknown"
    description = raw.get("description") or ""
    budget      = _format_budget(raw.get("budget"))
    posted_time = raw.get("inserted_at") or raw.get("updated_at") or "ไม่ระบุ"
    job_url     = f"{JOBS_PAGE_URL}/{job_id}" if job_id else ""
    category    = (raw.get("tag") or {}).get("name", "")
    job_type    = raw.get("type", "")

    score, pct, matched = compute_match(title, description)

    return JobListing(
        title=title, description=description, budget=budget,
        posted_time=posted_time, job_url=job_url,
        category=category, job_type=job_type,
        match_score=score, match_percentage=pct, matched_keywords=matched,
    )


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------

def _fetch_page(
    session: requests.Session,
    page: int,
    filter_by_tags: bool = True,
    include_catchall: bool = False,
) -> tuple[list[JobListing], dict, int]:
    """
    Fetch one page from the API.

    Returns (jobs, meta, raw_count) where raw_count is the number of jobs
    returned by the API before any tag filtering.
    """
    resp = session.get(API_URL, params={"page": page}, timeout=15)
    resp.raise_for_status()

    data     = resp.json()
    raw_data = data.get("data", [])
    meta     = data.get("meta", {})
    raw_count = len(raw_data)

    if filter_by_tags:
        raw_data = [
            j for j in raw_data
            if _is_civil_tag((j.get("tag") or {}).get("id", ""), include_catchall)
        ]
        logger.debug(
            "page %d: %d → %d after tag filter",
            page, raw_count, len(raw_data),
        )

    jobs = [_map_api_job(j) for j in raw_data]
    return jobs, meta, raw_count


def _fetch_all_pages(
    session: requests.Session,
    filter_by_tags: bool = True,
    include_catchall: bool = False,
    request_delay: float = 0.5,
) -> tuple[list[JobListing], dict, int]:
    """
    Iterate every page and return (combined_jobs, last_meta, total_fetched).
    total_fetched counts API jobs before tag filtering.
    """
    all_jobs: list[JobListing] = []
    meta: dict = {}
    total_fetched = 0
    page = 1

    while True:
        jobs, meta, raw_count = _fetch_page(
            session, page, filter_by_tags, include_catchall
        )
        all_jobs.extend(jobs)
        total_fetched += raw_count

        total_pages = meta.get("total_pages", 1)
        logger.info(
            "page %d/%d — %d civil jobs kept (fetched %d total so far)",
            page, total_pages, len(all_jobs), total_fetched,
        )

        if page >= total_pages or page >= MAX_PAGES:
            break

        page += 1
        time.sleep(request_delay)

    return all_jobs, meta, total_fetched


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scrape_jobs(
    min_match_pct: float = 0.0,
    page: int = 1,
    all_pages: bool = False,
    filter_by_tags: bool = True,
    include_catchall: bool = False,
) -> dict:
    """
    Fetch Fastwork job listings, pre-filtered to civil engineering categories.

    The Fastwork API does not support server-side tag filtering, so we apply
    it client-side after each page fetch:
      1. Fetch page from API (50 jobs)
      2. Discard jobs whose tag is not in CIVIL_TAGS  [~94 % discarded]
      3. Run keyword matching on the remaining jobs

    Args:
        min_match_pct:    Only return jobs at or above this match %.
        page:             Page to fetch (ignored when all_pages=True).
        all_pages:        Fetch and filter every page (up to MAX_PAGES).
        filter_by_tags:   Apply civil category pre-filter (default True).
        include_catchall: Also keep jobs tagged อื่นๆ (broader, noisier).

    Returns:
        {
            "jobs":              [{...}, ...],
            "total":             <count after all filters>,
            "total_available":   <total jobs on Fastwork before any filter>,
            "total_pages":       <total pages on Fastwork>,
            "current_page":      <page fetched>,
            "source":            "api",
            "civil_tags":        {id: name, ...},
            "filter_by_tags":    bool,
        }
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        if all_pages:
            all_jobs, meta, fetched = _fetch_all_pages(
                session, filter_by_tags, include_catchall
            )
        else:
            all_jobs, meta, fetched = _fetch_page(
                session, page, filter_by_tags, include_catchall
            )
    except requests.RequestException as e:
        logger.error("API request failed: %s", e)
        raise

    if min_match_pct > 0:
        all_jobs = [j for j in all_jobs if j.match_percentage >= min_match_pct]

    all_jobs.sort(key=lambda j: j.match_percentage, reverse=True)

    active_tags = dict(CIVIL_TAGS)
    if include_catchall:
        active_tags[CATCHALL_TAG_ID] = "อื่นๆ"

    return {
        "jobs":            [j.to_dict() for j in all_jobs],
        "total":           len(all_jobs),
        "total_available": meta.get("total_count", 0),
        "total_pages":     meta.get("total_pages", 1),
        "current_page":    meta.get("current_page", page),
        "source":          "api",
        "filter_by_tags":  filter_by_tags,
        "civil_tags":      active_tags,
    }
