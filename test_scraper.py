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
    CIVIL_TAGS,
    CATCHALL_TAG_ID,
    MAX_POSSIBLE_SCORE,
    JobListing,
    compute_match,
    scrape_jobs,
    _map_api_job,
    _format_budget,
    _is_civil_tag,
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
# Unit tests — tag pre-filter
# ---------------------------------------------------------------------------

class TestIsCivilTag(unittest.TestCase):

    ARCH_ID   = "d19619b6-a04a-4c26-b74b-dbfe28494a9b"
    TRADES_ID = "883a6909-c772-48fa-91e9-b8162e599aba"
    UNRELATED = "cedd5edf-03fa-40d4-9266-39af6992dc7b"  # การตลาด

    def test_architecture_tag_is_civil(self):
        self.assertTrue(_is_civil_tag(self.ARCH_ID))

    def test_trades_tag_is_civil(self):
        self.assertTrue(_is_civil_tag(self.TRADES_ID))

    def test_unrelated_tag_not_civil(self):
        self.assertFalse(_is_civil_tag(self.UNRELATED))

    def test_catchall_excluded_by_default(self):
        self.assertFalse(_is_civil_tag(CATCHALL_TAG_ID, include_catchall=False))

    def test_catchall_included_when_requested(self):
        self.assertTrue(_is_civil_tag(CATCHALL_TAG_ID, include_catchall=True))

    def test_civil_tags_dict_has_two_entries(self):
        self.assertEqual(len(CIVIL_TAGS), 2)

    def test_civil_tag_ids_present_in_dict(self):
        self.assertIn(self.ARCH_ID, CIVIL_TAGS)
        self.assertIn(self.TRADES_ID, CIVIL_TAGS)


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

ARCH_TAG_ID   = "d19619b6-a04a-4c26-b74b-dbfe28494a9b"
TRADES_TAG_ID = "883a6909-c772-48fa-91e9-b8162e599aba"

SAMPLE_CIVIL_JOB = {
    "id": "f8eaef64-17f1-47cb-9e78-f23a397e513f",
    "status": "open",
    "title": "ต้องการวิศวกรโยธา ออกแบบโครงสร้างบ้าน",
    "description": "ต้องการวิศวกรที่ใช้ AutoCAD และทำ BOQ ได้",
    "budget": "25000",
    "inserted_at": "2026-04-12T10:00:00Z",
    "tag": {"id": ARCH_TAG_ID, "name": "สถาปัตยกรรมและการตกแต่งภายใน", "sort": 14},
    "type": "freelance",
}


class TestMapApiJob(unittest.TestCase):

    def test_title_and_description(self):
        job = _map_api_job(SAMPLE_CIVIL_JOB)
        self.assertEqual(job.title, "ต้องการวิศวกรโยธา ออกแบบโครงสร้างบ้าน")

    def test_budget_formatted(self):
        self.assertEqual(_map_api_job(SAMPLE_CIVIL_JOB).budget, "฿25,000")

    def test_job_url_contains_id(self):
        job = _map_api_job(SAMPLE_CIVIL_JOB)
        self.assertIn("f8eaef64-17f1-47cb-9e78-f23a397e513f", job.job_url)
        self.assertTrue(job.job_url.startswith("https://jobboard.fastwork.co/jobs/"))

    def test_category_from_tag(self):
        self.assertEqual(
            _map_api_job(SAMPLE_CIVIL_JOB).category,
            "สถาปัตยกรรมและการตกแต่งภายใน",
        )

    def test_keywords_matched(self):
        job = _map_api_job(SAMPLE_CIVIL_JOB)
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
        d = _map_api_job(SAMPLE_CIVIL_JOB).to_dict()
        for key in ("title", "description", "budget", "posted_time", "job_url",
                    "category", "job_type", "match_percentage",
                    "match_score", "matched_keywords"):
            self.assertIn(key, d)


# ---------------------------------------------------------------------------
# Integration-style tests — scrape_jobs with mocked HTTP
# ---------------------------------------------------------------------------

def _make_api_response(jobs: list[dict]) -> dict:
    return {
        "data": jobs,
        "meta": {
            "page_size": 50, "current_page": 1,
            "total_count": len(jobs), "total_pages": 1,
        },
    }


CIVIL_JOB_RAW = {
    "id": "aaa-111",
    "title": "วิศวกรโยธา ออกแบบโครงสร้างบ้าน",
    "description": "ต้องการวิศวกรที่ใช้ AutoCAD และทำ BOQ ได้",
    "budget": "25000", "inserted_at": "2026-04-12T10:00:00Z",
    "tag": {"id": ARCH_TAG_ID, "name": "สถาปัตยกรรมและการตกแต่งภายใน", "sort": 14},
    "type": "freelance",
}

UNRELATED_JOB_RAW = {
    "id": "bbb-222",
    "title": "Web Developer",
    "description": "React and Node.js project",
    "budget": "15000", "inserted_at": "2026-04-12T11:00:00Z",
    "tag": {"id": "cedd5edf-03fa-40d4-9266-39af6992dc7b", "name": "IT", "sort": 2},
    "type": "freelance",
}

MOCK_MIXED_RESPONSE = _make_api_response([CIVIL_JOB_RAW, UNRELATED_JOB_RAW])


def _mock_session(response_data: dict) -> MagicMock:
    session = MagicMock()
    resp = MagicMock()
    resp.json.return_value = response_data
    session.get.return_value = resp
    return session


class TestScrapeJobsWithMock(unittest.TestCase):

    @patch("scraper.requests.Session")
    def test_returns_required_keys(self, mock_cls):
        mock_cls.return_value = _mock_session(MOCK_MIXED_RESPONSE)
        result = scrape_jobs(filter_by_tags=False)
        for key in ("jobs", "total", "total_available", "total_pages",
                    "current_page", "source", "filter_by_tags", "civil_tags"):
            self.assertIn(key, result)

    @patch("scraper.requests.Session")
    def test_tag_filter_removes_unrelated(self, mock_cls):
        mock_cls.return_value = _mock_session(MOCK_MIXED_RESPONSE)
        result = scrape_jobs(filter_by_tags=True)
        titles = [j["title"] for j in result["jobs"]]
        # Civil job (สถาปัตยกรรม tag) should be kept
        self.assertTrue(any("วิศวกร" in t for t in titles))
        # Web Developer (IT tag) should be discarded
        self.assertNotIn("Web Developer", titles)

    @patch("scraper.requests.Session")
    def test_tag_filter_off_keeps_all(self, mock_cls):
        mock_cls.return_value = _mock_session(MOCK_MIXED_RESPONSE)
        result = scrape_jobs(filter_by_tags=False, min_match_pct=0)
        self.assertEqual(result["total"], 2)

    @patch("scraper.requests.Session")
    def test_filter_by_tags_true_in_response(self, mock_cls):
        mock_cls.return_value = _mock_session(MOCK_MIXED_RESPONSE)
        result = scrape_jobs(filter_by_tags=True)
        self.assertTrue(result["filter_by_tags"])

    @patch("scraper.requests.Session")
    def test_civil_tags_in_response(self, mock_cls):
        mock_cls.return_value = _mock_session(MOCK_MIXED_RESPONSE)
        result = scrape_jobs(filter_by_tags=True)
        self.assertIn(ARCH_TAG_ID, result["civil_tags"])
        self.assertIn(TRADES_TAG_ID, result["civil_tags"])

    @patch("scraper.requests.Session")
    def test_min_match_filter(self, mock_cls):
        mock_cls.return_value = _mock_session(MOCK_MIXED_RESPONSE)
        result = scrape_jobs(filter_by_tags=False, min_match_pct=1.0)
        for job in result["jobs"]:
            self.assertGreaterEqual(job["match_percentage"], 1.0)

    @patch("scraper.requests.Session")
    def test_sorted_by_match_desc(self, mock_cls):
        mock_cls.return_value = _mock_session(MOCK_MIXED_RESPONSE)
        result = scrape_jobs(filter_by_tags=False, min_match_pct=0)
        pcts = [j["match_percentage"] for j in result["jobs"]]
        self.assertEqual(pcts, sorted(pcts, reverse=True))

    @patch("scraper.requests.Session")
    def test_budget_formatted(self, mock_cls):
        mock_cls.return_value = _mock_session(MOCK_MIXED_RESPONSE)
        result = scrape_jobs(filter_by_tags=True)
        civil = next(j for j in result["jobs"] if "วิศวกร" in j["title"])
        self.assertEqual(civil["budget"], "฿25,000")

    @patch("scraper.requests.Session")
    def test_job_url_uses_id(self, mock_cls):
        mock_cls.return_value = _mock_session(MOCK_MIXED_RESPONSE)
        result = scrape_jobs(filter_by_tags=True)
        civil = next(j for j in result["jobs"] if "วิศวกร" in j["title"])
        self.assertIn("aaa-111", civil["job_url"])

    @patch("scraper.requests.Session")
    def test_catchall_expands_results(self, mock_cls):
        catchall_job = {
            "id": "ccc-333", "title": "งานอื่นๆ", "description": "misc",
            "budget": "5000", "inserted_at": "2026-04-12T12:00:00Z",
            "tag": {"id": CATCHALL_TAG_ID, "name": "อื่นๆ", "sort": 99},
            "type": "freelance",
        }
        mock_cls.return_value = _mock_session(
            _make_api_response([CIVIL_JOB_RAW, catchall_job])
        )
        result_without = scrape_jobs(filter_by_tags=True, include_catchall=False)
        result_with    = scrape_jobs(filter_by_tags=True, include_catchall=True)
        self.assertGreater(result_with["total"], result_without["total"])


# ---------------------------------------------------------------------------
# Live smoke test
# ---------------------------------------------------------------------------

class TestLiveScrape(unittest.TestCase):

    def test_live_single_page_with_tag_filter(self):
        try:
            result = scrape_jobs(min_match_pct=0, page=1, filter_by_tags=True)
        except Exception as e:
            self.skipTest(f"Network unavailable: {e}")

        self.assertEqual(result["source"], "api")
        self.assertTrue(result["filter_by_tags"])
        self.assertGreater(result["total_available"], 0)

        # Every returned job must be in a civil category
        for job in result["jobs"]:
            self.assertIn(
                job["category"],
                list(CIVIL_TAGS.values()),
                f"Non-civil category slipped through: {job['category']}",
            )

        print(f"\n[LIVE] total_available={result['total_available']}  "
              f"civil_kept={result['total']}  pages={result['total_pages']}")
        for job in result["jobs"][:5]:
            print(f"  [{job['match_percentage']:5.1f}%]  {job['title'][:55]}"
                  f"  cat={job['category']}  kw={job['matched_keywords']}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
