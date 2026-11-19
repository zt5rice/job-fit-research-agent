import unittest
from pathlib import Path
from unittest.mock import patch

from deepagents import create_deep_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

from job_fit.agent import (
    JOB_ANALYST_SUBAGENT,
    SYSTEM_PROMPT,
    build_deep_agent,
)


ROOT = Path(__file__).resolve().parents[1]


class AgentTests(unittest.TestCase):
    def test_real_create_deep_agent_is_importable(self):
        self.assertTrue(callable(create_deep_agent))

    def test_agent_spec_has_required_safety_and_subagent(self):
        self.assertIn("untrusted data", SYSTEM_PROMPT.casefold())
        self.assertEqual(JOB_ANALYST_SUBAGENT["name"], "job_analyst")
        self.assertGreaterEqual(len(JOB_ANALYST_SUBAGENT["tools"]), 2)

    def test_live_builder_calls_create_deep_agent(self):
        with patch("job_fit.agent.create_deep_agent") as mocked:
            mocked.return_value = object()
            build_deep_agent(object(), project_root=ROOT)
        kwargs = mocked.call_args.kwargs
        self.assertEqual(kwargs["name"], "job_fit_research_agent")
        self.assertEqual(kwargs["subagents"][0]["name"], "job_analyst")
        self.assertTrue(kwargs["tools"])

    def test_real_deepagents_graph_can_be_built_with_injected_fake_model(self):
        model = GenericFakeChatModel(messages=iter(['{"title": "unused"}']))
        graph = build_deep_agent(model, project_root=ROOT)
        self.assertIsNotNone(graph)
        self.assertTrue(hasattr(graph, "invoke"))


if __name__ == "__main__":
    unittest.main()

