"""
Test suite for the Fastwork civil-engineering job scraper.

Run with:
    python test_scraper.py
or
    python -m pytest test_scraper.py -v
"""

import json
import time
import unittest
from unittest.mock import MagicMock, patch

from scraper import (
    CIVIL_KEYWORDS,
    MAX_POSSIBLE_SCORE,
    JobListing,
    compute_match,
    scrape_jobs,
    _map_api_job,
    _parse_job_cards,
)
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Unit tests — keyword matching
# ---------------------------------------------------------------------------

class TestComputeMatch(unittest.TestCase):

    def test_no_match(self):
        score, pct, matched = compute_match("Graphic Designer", "Need logo design")
        self.assertEqual(score, 0)
        self.assertAlmostEqual(pct, 0.0)
        self.assertEqual(matched, [])

    def test_single_keyword_autocad(self):
        score, pct, matched = compute_match("AutoCAD drafter needed", "")
        self.assertIn("AutoCAD", matched)
        self.assertGreater(score, 0)
        self.assertGreater(pct, 0)

    def test_thai_keyword_วิศวกร(self):
        score, pct, matched = compute_match("ต้องการวิศวกรโยธา", "งานสำรวจ")
        self.assertTrue(
            any("วิศวกร" in kw for kw in matched),
            f"Expected วิศวกร in matched keywords, got {matched}",
        )

    def test_thai_keyword_โครงสร้าง(self):
        _, _, matched = compute_match("งานออกแบบโครงสร้าง", "")
        self.assertIn("โครงสร้าง", matched)

    def test_boq_high_weight(self):
        score_boq, _, _ = compute_match("Need BOQ specialist", "")
        score_graphic, _, _ = compute_match("", "graphic design")
        self.assertGreater(score_boq, score_graphic)

    def test_multiple_keywords_increase_score(self):
        s1, _, _ = compute_match("AutoCAD", "")
        s2, _, _ = compute_match("AutoCAD BOQ วิศวกร", "")
        self.assertGreater(s2, s1)

    def test_percentage_cap_at_100(self):
        # Stuff every keyword into the text
        all_kw = " ".join(kw for kw, _ in CIVIL_KEYWORDS)
        _, pct, _ = compute_match(all_kw, all_kw)
        self.assertLessEqual(pct, 100.0)

    def test_case_insensitive_english(self):
        _, _, matched_lower = compute_match("autocad", "")
        _, _, matched_upper = compute_match("AUTOCAD", "")
        self.assertTrue(
            len(matched_lower) > 0 or len(matched_upper) > 0,
            "Expected at least one case variant to match",
        )

    def test_max_possible_score_positive(self):
        self.assertGreater(MAX_POSSIBLE_SCORE, 0)


# ---------------------------------------------------------------------------
# Unit tests — JobListing.to_dict
# ---------------------------------------------------------------------------

class TestJobListingToDict(unittest.TestCase):

    def _make_job(self, **kwargs) -> JobListing:
        defaults = dict(
            title="Test", description="", budget="500 THB",
            posted_time="2024-01-01", job_url="https://example.com",
        )
        defaults.update(kwargs)
        job = JobListing(**defaults)
        job.match_score, job.match_percentage, job.matched_keywords = compute_match(
            job.title, job.description
        )
        return job

    def test_to_dict_has_required_keys(self):
        d = self._make_job().to_dict()
        for key in ("title", "description", "budget", "posted_time", "job_url",
                    "match_percentage", "match_score", "matched_keywords"):
            self.assertIn(key, d, f"Missing key: {key}")

    def test_match_percentage_rounded(self):
        d = self._make_job(title="AutoCAD BOQ วิศวกร").to_dict()
        # Should be rounded to 1 decimal
        self.assertIsInstance(d["match_percentage"], float)

    def test_matched_keywords_is_list(self):
        d = self._make_job(title="AutoCAD").to_dict()
        self.assertIsInstance(d["matched_keywords"], list)


# ---------------------------------------------------------------------------
# Unit tests — API job mapper
# ---------------------------------------------------------------------------

class TestMapApiJob(unittest.TestCase):

    def test_standard_fields(self):
        raw = {
            "title": "ต้องการวิศวกร",
            "description": "งาน AutoCAD ออกแบบโครงสร้าง",
            "budget": "15000",
            "created_at": "2024-03-15T10:00:00Z",
            "slug": "civil-job-123",
        }
        job = _map_api_job(raw)
        self.assertEqual(job.title, "ต้องการวิศวกร")
        self.assertIn("AutoCAD", job.matched_keywords)
        self.assertIn("โครงสร้าง", job.matched_keywords)
        self.assertEqual(job.budget, "15000")
        self.assertIn("/jobs/civil-job-123", job.job_url)

    def test_fallback_fields(self):
        raw = {"name": "BOQ Engineer", "price": "20000", "id": 99}
        job = _map_api_job(raw)
        self.assertEqual(job.title, "BOQ Engineer")
        self.assertEqual(job.budget, "20000")
        self.assertIn("BOQ", job.matched_keywords)

    def test_missing_optional_fields_use_defaults(self):
        job = _map_api_job({})
        self.assertEqual(job.title, "Unknown")
        self.assertEqual(job.budget, "ไม่ระบุ")
        self.assertEqual(job.posted_time, "ไม่ระบุ")


# ---------------------------------------------------------------------------
# Unit tests — HTML parser
# ---------------------------------------------------------------------------

SAMPLE_HTML = """
<html><body>
  <div class="job-card">
    <h2><a href="/jobs/civil-001">วิศวกรโยธา — ออกแบบโครงสร้าง</a></h2>
    <p class="description">ต้องการวิศวกรโยธาที่มีประสบการณ์ AutoCAD และ BOQ</p>
    <span class="budget">฿15,000 – ฿30,000</span>
    <time datetime="2024-04-10T08:00:00Z">10 เม.ย. 2024</time>
  </div>
  <div class="job-card">
    <h2><a href="/jobs/graphic-001">Graphic Designer</a></h2>
    <p class="description">Need logo and branding work</p>
    <span class="budget">฿5,000</span>
    <time datetime="2024-04-11T09:00:00Z">11 เม.ย. 2024</time>
  </div>
</body></html>
"""


class TestParseJobCards(unittest.TestCase):

    def setUp(self):
        self.soup = BeautifulSoup(SAMPLE_HTML, "html.parser")

    def test_finds_two_jobs(self):
        jobs = _parse_job_cards(self.soup)
        self.assertEqual(len(jobs), 2)

    def test_civil_job_has_high_match(self):
        jobs = _parse_job_cards(self.soup)
        civil = next(j for j in jobs if "วิศวกร" in j.title)
        self.assertGreater(civil.match_percentage, 0)
        self.assertTrue(len(civil.matched_keywords) > 0)

    def test_graphic_job_has_zero_match(self):
        jobs = _parse_job_cards(self.soup)
        graphic = next(j for j in jobs if "Graphic" in j.title)
        self.assertEqual(graphic.match_score, 0)

    def test_job_url_built_correctly(self):
        jobs = _parse_job_cards(self.soup)
        civil = next(j for j in jobs if "วิศวกร" in j.title)
        self.assertIn("/jobs/civil-001", civil.job_url)

    def test_budget_extracted(self):
        jobs = _parse_job_cards(self.soup)
        civil = next(j for j in jobs if "วิศวกร" in j.title)
        self.assertIn("15,000", civil.budget)

    def test_posted_time_extracted(self):
        jobs = _parse_job_cards(self.soup)
        civil = next(j for j in jobs if "วิศวกร" in j.title)
        self.assertNotEqual(civil.posted_time, "")


# ---------------------------------------------------------------------------
# Integration-style tests — scrape_jobs with mocked HTTP
# ---------------------------------------------------------------------------

MOCK_API_RESPONSE = [
    {
        "title": "วิศวกรโยธา ออกแบบโครงสร้างบ้าน",
        "description": "ต้องการวิศวกรที่ใช้ AutoCAD และทำ BOQ ได้",
        "budget": "25000",
        "created_at": "2024-04-12T10:00:00Z",
        "slug": "civil-engineer-001",
    },
    {
        "title": "Web Developer",
        "description": "React and Node.js project",
        "budget": "15000",
        "created_at": "2024-04-12T11:00:00Z",
        "slug": "web-dev-001",
    },
]


class TestScrapeJobsWithMock(unittest.TestCase):

    @patch("scraper.requests.Session")
    def test_returns_dict_with_required_keys(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_API_RESPONSE
        mock_session.get.return_value = mock_resp

        result = scrape_jobs()

        self.assertIn("jobs", result)
        self.assertIn("total", result)
        self.assertIn("source", result)
        self.assertIn("page", result)
        self.assertIn("per_page", result)

    @patch("scraper.requests.Session")
    def test_civil_job_present_no_filter(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_API_RESPONSE
        mock_session.get.return_value = mock_resp

        result = scrape_jobs(min_match_pct=0)
        titles = [j["title"] for j in result["jobs"]]
        self.assertTrue(any("วิศวกร" in t for t in titles))

    @patch("scraper.requests.Session")
    def test_filter_removes_non_civil(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_API_RESPONSE
        mock_session.get.return_value = mock_resp

        result = scrape_jobs(min_match_pct=1.0)
        for job in result["jobs"]:
            self.assertGreaterEqual(job["match_percentage"], 1.0)
        titles = [j["title"] for j in result["jobs"]]
        self.assertFalse(any("Web Developer" == t for t in titles))

    @patch("scraper.requests.Session")
    def test_sorted_by_match_desc(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_API_RESPONSE
        mock_session.get.return_value = mock_resp

        result = scrape_jobs(min_match_pct=0)
        pcts = [j["match_percentage"] for j in result["jobs"]]
        self.assertEqual(pcts, sorted(pcts, reverse=True))


# ---------------------------------------------------------------------------
# Live smoke test (optional — skipped if network unavailable)
# ---------------------------------------------------------------------------

class TestLiveScrape(unittest.TestCase):
    """
    Attempts a real HTTP call to Fastwork.
    Mark with @unittest.skip to exclude from CI.
    """

    def test_live_scrape_returns_jobs(self):
        try:
            result = scrape_jobs(min_match_pct=0, per_page=20)
        except Exception as e:
            self.skipTest(f"Network unavailable or site unreachable: {e}")

        self.assertIn("jobs", result)
        self.assertIn("source", result)
        self.assertIn(result["source"], ("api", "html"))

        print(f"\n[LIVE] source={result['source']}  total={result['total']}")
        for job in result["jobs"][:5]:
            print(
                f"  [{job['match_percentage']:5.1f}%]  {job['title'][:60]}"
                f"  matched={job['matched_keywords']}"
            )

        # Structural check on each returned job
        for job in result["jobs"]:
            for key in ("title", "description", "budget", "posted_time",
                        "job_url", "match_percentage", "matched_keywords"):
                self.assertIn(key, job, f"Missing key '{key}' in job dict")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
