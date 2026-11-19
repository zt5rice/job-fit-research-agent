import unittest
from pathlib import Path

from job_fit.tools import (
    extract_job_fields_tool,
    find_skill_gaps_tool,
    generate_interview_prep,
    generate_resume_emphasis,
    list_jobs,
    load_profile,
    read_job,
    score_job_tool,
    validate_job_schema,
)


ROOT = Path(__file__).resolve().parents[1]


class ToolTests(unittest.TestCase):
    def test_input_tools_work_without_credentials(self):
        profile = load_profile(str(ROOT / "profile.example.json"))
        jobs = list_jobs(str(ROOT / "examples/fixtures/jobs"))
        self.assertEqual(len(jobs), 3)
        payload = read_job(jobs[0]["path"])
        self.assertTrue(payload["evidence"])
        validation = validate_job_schema(payload)
        self.assertTrue(validation["is_valid"], validation["errors"])
        gaps = find_skill_gaps_tool(profile, payload)
        self.assertIsInstance(gaps, list)
        result = score_job_tool(profile, payload)
        self.assertEqual(result["assessment"]["score"], 100)
        self.assertTrue(generate_resume_emphasis(profile, payload))
        self.assertTrue(generate_interview_prep(profile, payload))

    def test_extract_tool_labels_untrusted_input(self):
        payload = extract_job_fields_tool(
            "# Role\n\nCompany: Synthetic\nLocation: Remote US\n\n"
            "## Requirements\n- Python\n",
            source="inline.md",
        )
        self.assertIn("untrusted_notice", payload)
        self.assertEqual(payload["must_have"], ["Python"])


if __name__ == "__main__":
    unittest.main()

