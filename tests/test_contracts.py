import json
import unittest
from pathlib import Path

from job_fit.contracts import (
    ContractError,
    Recommendation,
    ScoreBreakdown,
    UserProfile,
)


ROOT = Path(__file__).resolve().parents[1]


class ContractTests(unittest.TestCase):
    def test_profile_round_trip(self):
        payload = json.loads(
            (ROOT / "profile.example.json").read_text(encoding="utf-8")
        )
        profile = UserProfile.from_dict(payload)
        self.assertEqual(profile.candidate_id, "synthetic-candidate")
        self.assertEqual(profile.to_dict()["candidate_id"], "synthetic-candidate")

    def test_profile_requires_candidate_id(self):
        with self.assertRaises(ContractError):
            UserProfile.from_dict({"headline": "Missing id"})

    def test_invalid_recommendation_is_rejected(self):
        with self.assertRaises(ValueError):
            Recommendation("maybe")

    def test_score_breakdown_rejects_out_of_range_dimension(self):
        breakdown = ScoreBreakdown(
            role_and_domain=31,
            must_have_skills=0,
            seniority=0,
            location_and_authorization=0,
            preference_alignment=0,
        )
        with self.assertRaises(ContractError):
            breakdown.validate()


if __name__ == "__main__":
    unittest.main()

