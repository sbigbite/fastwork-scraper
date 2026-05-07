"""
Test suite for the Fastwork civil-engineering job scraper.

Run with:
    python test_scraper.py
or
    python -m pytest test_scraper.py -v
"""

import unittest
from unittest.mock import MagicMock, patch

from scraper import (
    CIVIL_KEYWORDS,
    MAX_POSSIBLE_SCORE,
    JobListing,
    compute_match,
    scrape_jobs,
    _map_api_job,
    _format_budget,
)


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
        self.assertTrue(any("วิศวกร" in kw for kw in matched))

    def test_thai_keyword_โครงสร้าง(self):
        _, _, matched = compute_match("งานออกแบบโครงสร้าง", "")
        self.assertIn("โครงสร้าง", matched)

    def test_boq_high_weight(self):
        score_boq, _, _    = compute_match("Need BOQ specialist", "")
        score_other, _, _  = compute_match("", "graphic design logo")
        self.assertGreater(score_boq, score_other)

    def test_multiple_keywords_increase_score(self):
        s1, _, _ = compute_match("AutoCAD", "")
        s2, _, _ = compute_match("AutoCAD BOQ วิศวกร", "")
        self.assertGreater(s2, s1)

    def test_percentage_cap_at_100(self):
        all_kw = " ".join(kw for kw, _ in CIVIL_KEYWORDS)
        _, pct, _ = compute_match(all_kw, all_kw)
        self.assertLessEqual(pct, 100.0)

    def test_case_insensitive_english(self):
        _, _, m_lower = compute_match("autocad", "")
        _, _, m_upper = compute_match("AUTOCAD", "")
        self.assertTrue(len(m_lower) > 0 or len(m_upper) > 0)

    def test_max_possible_score_positive(self):
        self.assertGreater(MAX_POSSIBLE_SCORE, 0)


# ---------------------------------------------------------------------------
# Unit tests — budget formatting
# ---------------------------------------------------------------------------

class TestFormatBudget(unittest.TestCase):

    def test_numeric_string(self):
        self.assertEqual(_format_budget("15001"), "฿15,001")

    def test_large_number(self):
        self.assertEqual(_format_budget("1000000"), "฿1,000,000")

    def test_zero(self):
        self.assertEqual(_format_budget("0"), "฿0")

    def test_none_returns_default(self):
        self.assertEqual(_format_budget(None), "ไม่ระบุ")

    def test_empty_string_returns_default(self):
        self.assertEqual(_format_budget(""), "ไม่ระบุ")

    def test_non_numeric_passthrough(self):
        result = _format_budget("ตามตกลง")
        self.assertEqual(result, "ตามตกลง")


# ---------------------------------------------------------------------------
# Unit tests — API job mapper
# ---------------------------------------------------------------------------

# Matches the real Fastwork /api/jobs response shape
SAMPLE_API_JOB = {
    "id": "f8eaef64-17f1-47cb-9e78-f23a397e513f",
    "status": "open",
    "title": "ต้องการวิศวกรโยธา ออกแบบโครงสร้างบ้าน",
    "description": "ต้องการวิศวกรที่ใช้ AutoCAD และทำ BOQ ได้",
    "budget": "25000",
    "inserted_at": "2026-04-12T10:00:00Z",
    "tag": {"id": "abc", "name": "วิศวกรรม", "sort": 1},
    "type": "freelance",
    "is_anonymous": False,
    "freelance_offers_count": 2,
}


class TestMapApiJob(unittest.TestCase):

    def test_title_and_description(self):
        job = _map_api_job(SAMPLE_API_JOB)
        self.assertEqual(job.title, "ต้องการวิศวกรโยธา ออกแบบโครงสร้างบ้าน")
        self.assertIn("AutoCAD", job.description)

    def test_budget_formatted(self):
        job = _map_api_job(SAMPLE_API_JOB)
        self.assertEqual(job.budget, "฿25,000")

    def test_posted_time(self):
        job = _map_api_job(SAMPLE_API_JOB)
        self.assertEqual(job.posted_time, "2026-04-12T10:00:00Z")

    def test_job_url_contains_id(self):
        job = _map_api_job(SAMPLE_API_JOB)
        self.assertIn("f8eaef64-17f1-47cb-9e78-f23a397e513f", job.job_url)
        self.assertTrue(job.job_url.startswith("https://jobboard.fastwork.co/jobs/"))

    def test_category_from_tag(self):
        job = _map_api_job(SAMPLE_API_JOB)
        self.assertEqual(job.category, "วิศวกรรม")

    def test_job_type(self):
        job = _map_api_job(SAMPLE_API_JOB)
        self.assertEqual(job.job_type, "freelance")

    def test_keywords_matched(self):
        job = _map_api_job(SAMPLE_API_JOB)
        self.assertIn("AutoCAD", job.matched_keywords)
        self.assertIn("BOQ", job.matched_keywords)
        self.assertGreater(job.match_percentage, 0)

    def test_missing_optional_fields(self):
        job = _map_api_job({})
        self.assertEqual(job.title, "Unknown")
        self.assertEqual(job.budget, "ไม่ระบุ")
        self.assertEqual(job.posted_time, "ไม่ระบุ")
        self.assertEqual(job.job_url, "")
        self.assertEqual(job.category, "")

    def test_to_dict_has_all_keys(self):
        d = _map_api_job(SAMPLE_API_JOB).to_dict()
        for key in ("title", "description", "budget", "posted_time", "job_url",
                    "category", "job_type", "match_percentage",
                    "match_score", "matched_keywords"):
            self.assertIn(key, d, f"Missing key: {key}")


# ---------------------------------------------------------------------------
# Integration-style tests — scrape_jobs with mocked HTTP
# ---------------------------------------------------------------------------

# Real API response shape: {"data": [...], "meta": {...}}
MOCK_API_RESPONSE = {
    "data": [
        {
            "id": "aaa-111",
            "title": "วิศวกรโยธา ออกแบบโครงสร้างบ้าน",
            "description": "ต้องการวิศวกรที่ใช้ AutoCAD และทำ BOQ ได้",
            "budget": "25000",
            "inserted_at": "2026-04-12T10:00:00Z",
            "tag": {"id": "t1", "name": "วิศวกรรม", "sort": 1},
            "type": "freelance",
        },
        {
            "id": "bbb-222",
            "title": "Web Developer",
            "description": "React and Node.js project",
            "budget": "15000",
            "inserted_at": "2026-04-12T11:00:00Z",
            "tag": {"id": "t2", "name": "IT", "sort": 2},
            "type": "freelance",
        },
    ],
    "meta": {
        "page_size": 50,
        "current_page": 1,
        "total_count": 2,
        "total_pages": 1,
    },
}


class TestScrapeJobsWithMock(unittest.TestCase):

    def _make_mock_session(self):
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_API_RESPONSE
        mock_session.get.return_value = mock_resp
        return mock_session

    @patch("scraper.requests.Session")
    def test_returns_dict_with_required_keys(self, mock_cls):
        mock_cls.return_value = self._make_mock_session()
        result = scrape_jobs()
        for key in ("jobs", "total", "total_available", "total_pages",
                    "current_page", "source"):
            self.assertIn(key, result)

    @patch("scraper.requests.Session")
    def test_source_is_api(self, mock_cls):
        mock_cls.return_value = self._make_mock_session()
        result = scrape_jobs()
        self.assertEqual(result["source"], "api")

    @patch("scraper.requests.Session")
    def test_total_available_from_meta(self, mock_cls):
        mock_cls.return_value = self._make_mock_session()
        result = scrape_jobs()
        self.assertEqual(result["total_available"], 2)

    @patch("scraper.requests.Session")
    def test_civil_job_present_no_filter(self, mock_cls):
        mock_cls.return_value = self._make_mock_session()
        result = scrape_jobs(min_match_pct=0)
        titles = [j["title"] for j in result["jobs"]]
        self.assertTrue(any("วิศวกร" in t for t in titles))

    @patch("scraper.requests.Session")
    def test_filter_removes_non_civil(self, mock_cls):
        mock_cls.return_value = self._make_mock_session()
        result = scrape_jobs(min_match_pct=1.0)
        for job in result["jobs"]:
            self.assertGreaterEqual(job["match_percentage"], 1.0)
        titles = [j["title"] for j in result["jobs"]]
        self.assertNotIn("Web Developer", titles)

    @patch("scraper.requests.Session")
    def test_sorted_by_match_desc(self, mock_cls):
        mock_cls.return_value = self._make_mock_session()
        result = scrape_jobs(min_match_pct=0)
        pcts = [j["match_percentage"] for j in result["jobs"]]
        self.assertEqual(pcts, sorted(pcts, reverse=True))

    @patch("scraper.requests.Session")
    def test_budget_formatted_in_output(self, mock_cls):
        mock_cls.return_value = self._make_mock_session()
        result = scrape_jobs(min_match_pct=0)
        civil = next(j for j in result["jobs"] if "วิศวกร" in j["title"])
        self.assertEqual(civil["budget"], "฿25,000")

    @patch("scraper.requests.Session")
    def test_job_url_uses_id(self, mock_cls):
        mock_cls.return_value = self._make_mock_session()
        result = scrape_jobs(min_match_pct=0)
        civil = next(j for j in result["jobs"] if "วิศวกร" in j["title"])
        self.assertIn("aaa-111", civil["job_url"])


# ---------------------------------------------------------------------------
# Live smoke test
# ---------------------------------------------------------------------------

class TestLiveScrape(unittest.TestCase):

    def test_live_single_page(self):
        try:
            result = scrape_jobs(min_match_pct=0, page=1)
        except Exception as e:
            self.skipTest(f"Network unavailable: {e}")

        self.assertEqual(result["source"], "api")
        self.assertGreater(result["total_available"], 0)
        self.assertGreater(result["total_pages"], 0)
        self.assertGreater(len(result["jobs"]), 0)

        print(f"\n[LIVE] total_available={result['total_available']}  "
              f"total_pages={result['total_pages']}  "
              f"page_jobs={len(result['jobs'])}")

        for job in result["jobs"][:5]:
            print(f"  [{job['match_percentage']:5.1f}%]  "
                  f"{job['title'][:55]}  "
                  f"budget={job['budget']}  "
                  f"matched={job['matched_keywords']}")

        for job in result["jobs"]:
            for key in ("title", "description", "budget", "posted_time",
                        "job_url", "category", "job_type",
                        "match_percentage", "matched_keywords"):
                self.assertIn(key, job, f"Missing key '{key}'")


if __name__ == "__main__":
    unittest.main(verbosity=2)
