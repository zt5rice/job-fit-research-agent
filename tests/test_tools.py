import unittest
from pathlib import Path

from job_fit.tools import (
    extract_job_fields_tool,
    list_jobs,
    load_profile,
    read_job,
    validate_job_schema,
)


ROOT = Path(__file__).resolve().parents[1]


class InputToolTests(unittest.TestCase):
    def test_input_tools_work_without_credentials(self):
        profile = load_profile(str(ROOT / "profile.example.json"))
        jobs = list_jobs(str(ROOT / "examples/fixtures/jobs"))
        self.assertEqual(len(jobs), 3)
        payload = read_job(jobs[0]["path"])
        self.assertTrue(payload["evidence"])
        validation = validate_job_schema(payload)
        self.assertTrue(validation["is_valid"], validation["errors"])
        self.assertEqual(profile["candidate_id"], "synthetic-candidate")

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
