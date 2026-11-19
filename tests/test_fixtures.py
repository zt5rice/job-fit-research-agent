import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JOBS = ROOT / "examples" / "fixtures" / "jobs"


class FixtureTests(unittest.TestCase):
    def test_profile_fixture_is_synthetic(self):
        profile = json.loads(
            (ROOT / "profile.example.json").read_text(encoding="utf-8")
        )
        self.assertEqual(profile["candidate_id"], "synthetic-candidate")
        self.assertIn("Fictional profile data", profile["work_authorization"]["notes"])

    def test_three_synthetic_jobs_are_available(self):
        jobs = sorted(JOBS.glob("*.md"))
        self.assertEqual(len(jobs), 3)
        self.assertTrue(any("strong" in path.name for path in jobs))
        self.assertTrue(any("investigate" in path.name for path in jobs))
        self.assertTrue(any("blocked" in path.name for path in jobs))

    def test_example_profile_matches_root_profile(self):
        root_profile = json.loads(
            (ROOT / "profile.example.json").read_text(encoding="utf-8")
        )
        example_profile = json.loads(
            (ROOT / "examples" / "profile.example.json").read_text(encoding="utf-8")
        )
        self.assertEqual(root_profile, example_profile)

    def test_no_csv_fixture_is_committed(self):
        self.assertEqual(list((ROOT / "examples").rglob("*.csv")), [])

    def test_public_fixtures_contain_no_original_identifiers(self):
        forbidden = (
            "Northstar Labs",
            "Harbor Data",
            "Meridian Defense Systems",
            "San Diego",
            "northstar-ai-platform",
            "harbor-applied-ai",
            "meridian-embedded",
        )
        public_text = "\n".join(
            [
                (ROOT / "profile.example.json").read_text(encoding="utf-8"),
                *[
                    path.read_text(encoding="utf-8")
                    for path in sorted((ROOT / "examples").rglob("*"))
                    if path.is_file()
                ],
            ]
        )
        for value in forbidden:
            self.assertNotIn(value, public_text)
        for path in sorted(JOBS.glob("*.md")):
            self.assertIn(
                "Company: Synthetic Employer", path.read_text(encoding="utf-8")
            )
