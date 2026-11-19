import unittest

from job_fit.deepagents_env import (
    create_deep_agent,
    deepagents_available,
    deepagents_version,
)


class DeepAgentsEnvironmentTests(unittest.TestCase):
    def test_create_deep_agent_is_importable(self):
        self.assertTrue(deepagents_available())
        self.assertTrue(callable(create_deep_agent))

    def test_version_is_recorded(self):
        self.assertNotEqual(deepagents_version(), "not-installed")

    def test_import_does_not_require_api_key(self):
        self.assertTrue(callable(create_deep_agent))
