import json
import unittest
from pathlib import Path

from job_fit.contracts import JobPosting, Recommendation, UserProfile
from job_fit.extraction import extract_job_file
from job_fit.scoring import score_job
from job_fit.validation import validate_job_payload


ROOT = Path(__file__).resolve().parents[1]


def load_profile() -> UserProfile:
    return UserProfile.from_dict(
        json.loads((ROOT / "profile.example.json").read_text(encoding="utf-8"))
    )


def analyze(fixture: str):
    payload = extract_job_file(ROOT / "examples/fixtures/jobs" / fixture)
    job = JobPosting.from_dict(payload)
    validation = validate_job_payload(payload, raw_text=job.raw_text)
    return job, score_job(load_profile(), job, validation)


class ScoringTests(unittest.TestCase):
    def test_strong_fixture_is_apply(self):
        _, assessment = analyze("job_001_strong.md")
        self.assertEqual(assessment.recommendation, Recommendation.APPLY)
        self.assertGreaterEqual(assessment.score, 75)
        self.assertFalse(assessment.needs_human_review)
        self.assertTrue(assessment.evidence)

    def test_borderline_fixture_requires_review(self):
        _, assessment = analyze("job_002_investigate.md")
        self.assertEqual(assessment.recommendation, Recommendation.INVESTIGATE)
        self.assertTrue(assessment.needs_human_review)
        self.assertIn("ambiguous_work_authorization", [
            reason.value for reason in assessment.review_reasons
        ])

    def test_hard_blocker_is_skip_and_capped(self):
        _, assessment = analyze("job_003_blocked.md")
        self.assertEqual(assessment.recommendation, Recommendation.SKIP)
        self.assertLess(assessment.score, 55)
        self.assertTrue(assessment.hard_blockers)
        self.assertEqual(assessment.score, assessment.score_breakdown.total)

    def test_score_is_repeatable_and_breakdown_sums_total(self):
        job, first = analyze("job_001_strong.md")
        validation = validate_job_payload(
            job.to_dict(include_raw_text=True), raw_text=job.raw_text
        )
        second = score_job(load_profile(), job, validation)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.score, first.score_breakdown.total)

    def test_model_score_cannot_be_passed(self):
        job, _ = analyze("job_001_strong.md")
        validation = validate_job_payload(
            job.to_dict(include_raw_text=True), raw_text=job.raw_text
        )
        with self.assertRaises(TypeError):
            score_job(load_profile(), job, validation, model_score=99)


if __name__ == "__main__":
    unittest.main()

