import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JOBS = ROOT / "examples" / "fixtures" / "jobs"


class PublicPrivacyTests(unittest.TestCase):
    def test_fixture_metadata_is_neutral(self):
        for path in sorted(JOBS.glob("*.md")):
            content = path.read_text(encoding="utf-8")
            self.assertIn("Company: Synthetic Employer", content)
            self.assertIn(
                "Source URL: https://example.com/jobs/synthetic-role-", content
            )

    def test_profile_locations_are_generic(self):
        for path in (
            ROOT / "profile.example.json",
            ROOT / "examples" / "profile.example.json",
        ):
            profile = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(
                all(
                    location.startswith(
                        ("Example City", "Remote (Example Region)")
                    )
                    for location in profile["locations"]
                )
            )

    def test_eval_metadata_is_neutral(self):
        corpus = json.loads(
            (ROOT / "evals" / "labeled_jobs.json").read_text(encoding="utf-8")
        )
        for case in corpus["cases"]:
            self.assertRegex(case["company"], r"^Synthetic Employer \d{2}$")
            self.assertTrue(
                case["location"].startswith(
                    ("Example City", "Remote (Example Region)")
                )
            )

    def test_sample_outputs_use_neutral_companies(self):
        for path in sorted(
            (ROOT / "examples" / "sample_outputs").glob("assessment_*.json")
        ):
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(
                payload["job"]["company"].startswith("Synthetic Employer")
            )
            self.assertTrue(
                payload["job"]["source_url"].startswith(
                    "https://example.com/jobs/synthetic-role-"
                )
            )


if __name__ == "__main__":
    unittest.main()
