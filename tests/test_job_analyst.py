import unittest

from job_fit.agent import (
    JOB_ANALYST_PROMPT,
    JOB_ANALYST_SUBAGENT,
    SYSTEM_PROMPT,
)


class JobAnalystTests(unittest.TestCase):
    def test_subagent_has_narrow_schema_safe_prompt(self):
        self.assertEqual(JOB_ANALYST_SUBAGENT["name"], "job_analyst")
        self.assertIn("untrusted", JOB_ANALYST_PROMPT.casefold())
        self.assertIn("exact source", JOB_ANALYST_PROMPT.casefold())
        self.assertIn("never invent evidence", JOB_ANALYST_PROMPT.casefold())

    def test_subagent_has_only_approved_local_tools(self):
        tool_names = {tool.__name__ for tool in JOB_ANALYST_SUBAGENT["tools"]}
        self.assertEqual(
            tool_names,
            {"read_job", "extract_job_fields_tool", "validate_job_schema"},
        )

    def test_planner_prompt_treats_job_text_as_untrusted(self):
        self.assertIn("untrusted data", SYSTEM_PROMPT.casefold())
        self.assertIn("deterministic", SYSTEM_PROMPT.casefold())


if __name__ == "__main__":
    unittest.main()
