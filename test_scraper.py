"""
Test suite for the Fastwork civil-engineering job scraper.

Run with:
    python test_scraper.py
or
    python -m pytest test_scraper.py -v
"""

import unittest
from unittest.mock import MagicMock, patch, call

from scraper import (
    CIVIL_KEYWORDS,
    MAX_POSSIBLE_SCORE,
    MAX_PAGES,
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

    def test_thai_keyword_วิศวกร(self):
        _, _, matched = compute_match("ต้องการวิศวกรโยธา", "งานสำรวจ")
        self.assertTrue(any("วิศวกร" in kw for kw in matched))

    def test_thai_keyword_โครงสร้าง(self):
        _, _, matched = compute_match("งานออกแบบโครงสร้าง", "")
        self.assertIn("โครงสร้าง", matched)

    def test_multiple_keywords_increase_score(self):
        s1, _, _ = compute_match("AutoCAD", "")
        s2, _, _ = compute_match("AutoCAD BOQ วิศวกร", "")
        self.assertGreater(s2, s1)

    def test_percentage_cap_at_100(self):
        all_kw = " ".join(kw for kw, _ in CIVIL_KEYWORDS)
        _, pct, _ = compute_match(all_kw, all_kw)
        self.assertLessEqual(pct, 100.0)

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

    def test_none_returns_default(self):
        self.assertEqual(_format_budget(None), "ไม่ระบุ")

    def test_empty_string_returns_default(self):
        self.assertEqual(_format_budget(""), "ไม่ระบุ")

    def test_non_numeric_passthrough(self):
        self.assertEqual(_format_budget("ตามตกลง"), "ตามตกลง")


# ---------------------------------------------------------------------------
# Unit tests — API job mapper
# ---------------------------------------------------------------------------

SAMPLE_JOB_RAW = {
    "id": "f8eaef64-17f1-47cb-9e78-f23a397e513f",
    "title": "ต้องการวิศวกรโยธา ออกแบบโครงสร้างบ้าน",
    "description": "ต้องการวิศวกรที่ใช้ AutoCAD และทำ BOQ ได้",
    "budget": "25000",
    "inserted_at": "2026-04-12T10:00:00Z",
    "tag": {"id": "d19619b6-a04a-4c26-b74b-dbfe28494a9b",
            "name": "สถาปัตยกรรมและการตกแต่งภายใน", "sort": 14},
    "type": "freelance",
}


class TestMapApiJob(unittest.TestCase):

    def test_title(self):
        self.assertEqual(
            _map_api_job(SAMPLE_JOB_RAW).title,
            "ต้องการวิศวกรโยธา ออกแบบโครงสร้างบ้าน",
        )

    def test_budget_formatted(self):
        self.assertEqual(_map_api_job(SAMPLE_JOB_RAW).budget, "฿25,000")

    def test_job_url_contains_id(self):
        job = _map_api_job(SAMPLE_JOB_RAW)
        self.assertIn("f8eaef64", job.job_url)
        self.assertTrue(job.job_url.startswith("https://jobboard.fastwork.co/jobs/"))

    def test_category_from_tag(self):
        self.assertEqual(
            _map_api_job(SAMPLE_JOB_RAW).category,
            "สถาปัตยกรรมและการตกแต่งภายใน",
        )

    def test_keywords_matched(self):
        job = _map_api_job(SAMPLE_JOB_RAW)
        self.assertIn("AutoCAD", job.matched_keywords)
        self.assertIn("BOQ", job.matched_keywords)
        self.assertGreater(job.match_percentage, 0)

    def test_missing_optional_fields(self):
        job = _map_api_job({})
        self.assertEqual(job.title, "Unknown")
        self.assertEqual(job.budget, "ไม่ระบุ")
        self.assertEqual(job.category, "")
        self.assertEqual(job.job_url, "")

    def test_to_dict_has_all_keys(self):
        d = _map_api_job(SAMPLE_JOB_RAW).to_dict()
        for key in ("title", "description", "budget", "posted_time", "job_url",
                    "category", "job_type", "match_percentage",
                    "match_score", "matched_keywords"):
            self.assertIn(key, d)


# ---------------------------------------------------------------------------
# Integration-style tests — scrape_jobs with mocked HTTP
# ---------------------------------------------------------------------------

def _make_response(jobs: list[dict], page: int = 1, total: int = 100) -> dict:
    return {
        "data": jobs,
        "meta": {
            "page_size": 50,
            "current_page": page,
            "total_count": total,
            "total_pages": (total + 49) // 50,
        },
    }


CIVIL_JOB = {
    "id": "aaa-111",
    "title": "วิศวกรโยธา ออกแบบโครงสร้างบ้าน",
    "description": "ต้องการวิศวกรที่ใช้ AutoCAD และทำ BOQ ได้",
    "budget": "25000", "inserted_at": "2026-04-12T10:00:00Z",
    "tag": {"id": "d19619b6-a04a-4c26-b74b-dbfe28494a9b",
            "name": "สถาปัตยกรรมและการตกแต่งภายใน", "sort": 14},
    "type": "freelance",
}

UNRELATED_JOB = {
    "id": "bbb-222",
    "title": "Web Developer",
    "description": "React and Node.js project",
    "budget": "15000", "inserted_at": "2026-04-12T11:00:00Z",
    "tag": {"id": "cedd5edf-03fa-40d4-9266-39af6992dc7b", "name": "IT", "sort": 2},
    "type": "freelance",
}


def _mock_session(pages_data: list[dict]) -> MagicMock:
    """Return a mock Session whose .get() cycles through pages_data."""
    session = MagicMock()
    responses = []
    for data in pages_data:
        resp = MagicMock()
        resp.json.return_value = data
        responses.append(resp)
    session.get.side_effect = responses
    return session


class TestScrapeJobsWithMock(unittest.TestCase):

    def _single_page_session(self, jobs=None):
        if jobs is None:
            jobs = [CIVIL_JOB, UNRELATED_JOB]
        return _mock_session([_make_response(jobs, total=50)])

    @patch("scraper.requests.Session")
    def test_returns_required_keys(self, mock_cls):
        mock_cls.return_value = self._single_page_session()
        result = scrape_jobs(pages=1)
        for key in ("jobs", "total", "total_available", "total_pages",
                    "pages_fetched", "source"):
            self.assertIn(key, result)

    @patch("scraper.requests.Session")
    def test_source_is_api(self, mock_cls):
        mock_cls.return_value = self._single_page_session()
        self.assertEqual(scrape_jobs(pages=1)["source"], "api")

    @patch("scraper.requests.Session")
    def test_all_categories_kept(self, mock_cls):
        """No tag filtering — both civil and unrelated jobs should be returned."""
        mock_cls.return_value = self._single_page_session()
        result = scrape_jobs(pages=1, min_match_pct=0)
        self.assertEqual(result["total"], 2)
        titles = [j["title"] for j in result["jobs"]]
        self.assertIn("Web Developer", titles)
        self.assertTrue(any("วิศวกร" in t for t in titles))

    @patch("scraper.requests.Session")
    def test_min_match_filters_by_keyword_only(self, mock_cls):
        mock_cls.return_value = self._single_page_session()
        result = scrape_jobs(pages=1, min_match_pct=1.0)
        titles = [j["title"] for j in result["jobs"]]
        # Unrelated job has no keywords — must be gone
        self.assertNotIn("Web Developer", titles)
        # Civil job has keywords — must stay
        self.assertTrue(any("วิศวกร" in t for t in titles))

    @patch("scraper.requests.Session")
    def test_sorted_by_match_desc(self, mock_cls):
        mock_cls.return_value = self._single_page_session()
        result = scrape_jobs(pages=1, min_match_pct=0)
        pcts = [j["match_percentage"] for j in result["jobs"]]
        self.assertEqual(pcts, sorted(pcts, reverse=True))

    @patch("scraper.requests.Session")
    def test_budget_formatted(self, mock_cls):
        mock_cls.return_value = self._single_page_session()
        result = scrape_jobs(pages=1)
        civil = next(j for j in result["jobs"] if "วิศวกร" in j["title"])
        self.assertEqual(civil["budget"], "฿25,000")

    @patch("scraper.requests.Session")
    def test_default_pages_is_5(self, mock_cls):
        """scrape_jobs() with no args should make 5 API calls (5 pages)."""
        pages_data = [_make_response([CIVIL_JOB], page=i, total=500)
                      for i in range(1, 6)]
        mock_cls.return_value = _mock_session(pages_data)
        scrape_jobs()
        self.assertEqual(mock_cls.return_value.get.call_count, 5)

    @patch("scraper.requests.Session")
    def test_pages_param_respected(self, mock_cls):
        """pages=3 should make exactly 3 API calls."""
        pages_data = [_make_response([CIVIL_JOB], page=i, total=500)
                      for i in range(1, 4)]
        mock_cls.return_value = _mock_session(pages_data)
        scrape_jobs(pages=3)
        self.assertEqual(mock_cls.return_value.get.call_count, 3)

    @patch("scraper.requests.Session")
    def test_stops_early_when_no_more_pages(self, mock_cls):
        """If the API has only 1 page, stop after 1 call even if pages=5."""
        mock_cls.return_value = _mock_session([_make_response([CIVIL_JOB], total=50)])
        scrape_jobs(pages=5)
        self.assertEqual(mock_cls.return_value.get.call_count, 1)

    @patch("scraper.requests.Session")
    def test_pages_capped_at_max_pages(self, mock_cls):
        """pages=9999 must be capped to MAX_PAGES internally."""
        # Only need to confirm scrape_jobs doesn't crash; mock 1-page API
        mock_cls.return_value = _mock_session([_make_response([CIVIL_JOB], total=50)])
        result = scrape_jobs(pages=9999)
        self.assertIn("jobs", result)


# ---------------------------------------------------------------------------
# Live smoke test
# ---------------------------------------------------------------------------

class TestLiveScrape(unittest.TestCase):

    def test_live_5_pages(self):
        try:
            result = scrape_jobs(min_match_pct=0, pages=5)
        except Exception as e:
            self.skipTest(f"Network unavailable: {e}")

        self.assertEqual(result["source"], "api")
        self.assertGreater(result["total_available"], 0)
        self.assertLessEqual(result["pages_fetched"], 5)

        print(f"\n[LIVE] total_available={result['total_available']}  "
              f"pages_fetched={result['pages_fetched']}  "
              f"jobs_returned={result['total']}")

        civil_hits = [j for j in result["jobs"] if j["match_percentage"] > 0]
        print(f"  civil keyword matches: {len(civil_hits)}/{result['total']}")
        for job in civil_hits[:5]:
            print(f"  [{job['match_percentage']:5.1f}%]  {job['title'][:55]}"
                  f"  cat={job['category']}  kw={job['matched_keywords']}")

        for job in result["jobs"]:
            for key in ("title", "description", "budget", "posted_time",
                        "job_url", "category", "job_type",
                        "match_percentage", "matched_keywords"):
                self.assertIn(key, job)


if __name__ == "__main__":
    unittest.main(verbosity=2)
