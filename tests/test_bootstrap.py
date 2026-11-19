import unittest
from pathlib import Path

import job_fit


ROOT = Path(__file__).resolve().parents[1]


class BootstrapTests(unittest.TestCase):
    def test_package_version(self):
        self.assertEqual(job_fit.__version__, "0.1.0")

    def test_required_hygiene_files_exist(self):
        self.assertTrue((ROOT / "pyproject.toml").is_file())
        self.assertTrue((ROOT / ".gitignore").is_file())
        self.assertTrue((ROOT / "data" / "README.md").is_file())

    def test_gitignore_excludes_private_inputs(self):
        content = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".env", content)
        self.assertIn("data/*", content)
        self.assertIn(".venv/", content)
