import re
import time
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "https://jobboard.fastwork.co"
JOBS_URL = f"{BASE_URL}/jobs"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "th,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": BASE_URL,
}

# ---------------------------------------------------------------------------
# Keyword definitions
# ---------------------------------------------------------------------------

# Each entry: (keyword, weight)  — weight 2 = high relevance, 1 = moderate
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
    # Related software / tools
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


@dataclass
class JobListing:
    title: str
    description: str
    budget: str
    posted_time: str
    job_url: str
    match_score: int = 0
    match_percentage: float = 0.0
    matched_keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["match_percentage"] = round(d["match_percentage"], 1)
        return d


# ---------------------------------------------------------------------------
# Keyword matching
# ---------------------------------------------------------------------------

def compute_match(title: str, description: str) -> tuple[int, float, list[str]]:
    """Return (raw_score, percentage, list_of_matched_keywords)."""
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
# HTML parsing helpers  (handles multiple possible page layouts)
# ---------------------------------------------------------------------------

def _safe_text(tag, default: str = "") -> str:
    return tag.get_text(strip=True) if tag else default


def _parse_job_cards(soup: BeautifulSoup) -> list[JobListing]:
    """
    Try several known Fastwork card selectors.
    Returns a list of JobListing objects (unfiltered).
    """
    jobs: list[JobListing] = []

    # Attempt 1: data-testid or class patterns seen on Fastwork job board
    card_selectors = [
        "div[data-testid='job-card']",
        "div.job-card",
        "div.JobCard",
        "article.job-item",
        "li.job-item",
        "div[class*='JobList'] div[class*='Card']",
        "a[href*='/jobs/']",          # fallback: anchor links
    ]

    cards = []
    for sel in card_selectors:
        cards = soup.select(sel)
        if cards:
            logger.info("Found %d cards with selector: %s", len(cards), sel)
            break

    if not cards:
        logger.warning("No job cards found with known selectors.")
        return jobs

    for card in cards:
        # --- Title ---
        title_tag = (
            card.select_one("h2")
            or card.select_one("h3")
            or card.select_one("[class*='title' i]")
            or card.select_one("[class*='Title' ]")
            or card.select_one("strong")
        )
        title = _safe_text(title_tag, "Unknown")

        # --- Description ---
        desc_tag = (
            card.select_one("[class*='description' i]")
            or card.select_one("[class*='desc' i]")
            or card.select_one("p")
        )
        description = _safe_text(desc_tag)

        # --- Budget ---
        budget_tag = (
            card.select_one("[class*='budget' i]")
            or card.select_one("[class*='price' i]")
            or card.select_one("[class*='salary' i]")
            or card.select_one("[class*='rate' i]")
        )
        budget = _safe_text(budget_tag, "ไม่ระบุ")

        # --- Posted time ---
        time_tag = (
            card.select_one("time")
            or card.select_one("[class*='time' i]")
            or card.select_one("[class*='date' i]")
            or card.select_one("[datetime]")
        )
        posted_time = (
            time_tag.get("datetime") or _safe_text(time_tag)
            if time_tag else "ไม่ระบุ"
        )

        # --- URL ---
        link_tag = card.select_one("a[href]") if card.name != "a" else card
        href = link_tag.get("href", "") if link_tag else ""
        job_url = href if href.startswith("http") else f"{BASE_URL}{href}"

        score, pct, matched = compute_match(title, description)

        jobs.append(
            JobListing(
                title=title,
                description=description,
                budget=budget,
                posted_time=posted_time,
                job_url=job_url,
                match_score=score,
                match_percentage=pct,
                matched_keywords=matched,
            )
        )

    return jobs


# ---------------------------------------------------------------------------
# API endpoint probing  (Fastwork may expose a JSON API)
# ---------------------------------------------------------------------------

API_ENDPOINTS = [
    f"{BASE_URL}/api/v1/jobs",
    f"{BASE_URL}/api/v2/jobs",
    "https://api.fastwork.co/jobs",
    "https://jobboard.fastwork.co/api/jobs",
]


def _try_api_fetch(session: requests.Session, params: dict) -> Optional[list[dict]]:
    """Probe known API patterns; return raw job list if found, else None."""
    for url in API_ENDPOINTS:
        try:
            r = session.get(url, params=params, timeout=10)
            if r.status_code == 200:
                data = r.json()
                # Common shapes: {"data": [...]} or {"jobs": [...]} or [...]
                if isinstance(data, list):
                    logger.info("API hit (list) at %s", url)
                    return data
                if isinstance(data, dict):
                    for key in ("data", "jobs", "items", "results"):
                        if key in data and isinstance(data[key], list):
                            logger.info("API hit (dict.%s) at %s", key, url)
                            return data[key]
        except Exception:
            continue
    return None


def _map_api_job(raw: dict) -> JobListing:
    """Convert a raw API job dict to a JobListing."""
    title = raw.get("title") or raw.get("name") or raw.get("job_title") or "Unknown"
    description = (
        raw.get("description")
        or raw.get("detail")
        or raw.get("body")
        or raw.get("excerpt")
        or ""
    )
    budget = str(
        raw.get("budget")
        or raw.get("price")
        or raw.get("salary")
        or raw.get("rate")
        or "ไม่ระบุ"
    )
    posted_time = str(
        raw.get("created_at")
        or raw.get("posted_at")
        or raw.get("published_at")
        or raw.get("date")
        or "ไม่ระบุ"
    )
    slug = raw.get("slug") or raw.get("id") or ""
    job_url = (
        raw.get("url")
        or raw.get("link")
        or (f"{BASE_URL}/jobs/{slug}" if slug else "")
    )

    score, pct, matched = compute_match(title, description)

    return JobListing(
        title=title,
        description=description,
        budget=budget,
        posted_time=posted_time,
        job_url=job_url,
        match_score=score,
        match_percentage=pct,
        matched_keywords=matched,
    )


# ---------------------------------------------------------------------------
# Public scrape function
# ---------------------------------------------------------------------------

def scrape_jobs(
    min_match_pct: float = 0.0,
    page: int = 1,
    per_page: int = 50,
    category: str = "",
) -> dict:
    """
    Scrape Fastwork job listings.

    Returns:
        {
            "jobs": [ {...}, ... ],
            "total": int,
            "source": "api" | "html",
            "page": int,
            "per_page": int,
        }
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    params = {"page": page, "per_page": per_page}
    if category:
        params["category"] = category

    # --- Try JSON API first ---
    raw_jobs = _try_api_fetch(session, params)
    source = "api"

    if raw_jobs is not None:
        all_jobs = [_map_api_job(j) for j in raw_jobs]
    else:
        # --- Fallback: HTML scraping ---
        source = "html"
        logger.info("API not found; falling back to HTML scraping: %s", JOBS_URL)
        try:
            resp = session.get(JOBS_URL, params=params, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error("HTTP request failed: %s", e)
            raise

        soup = BeautifulSoup(resp.text, "html.parser")
        all_jobs = _parse_job_cards(soup)

        if not all_jobs:
            # Last resort: dump raw text for debugging
            logger.warning("HTML parse found no jobs. Page title: %s", soup.title)

    # Filter by match percentage
    if min_match_pct > 0:
        all_jobs = [j for j in all_jobs if j.match_percentage >= min_match_pct]

    # Sort by match percentage descending
    all_jobs.sort(key=lambda j: j.match_percentage, reverse=True)

    return {
        "jobs": [j.to_dict() for j in all_jobs],
        "total": len(all_jobs),
        "source": source,
        "page": page,
        "per_page": per_page,
    }
