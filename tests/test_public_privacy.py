import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_PATHS = [ROOT / "README.md", ROOT / "profile.example.json"]
for directory_name in ("docs", "evals", "examples"):
    directory = ROOT / directory_name
    if directory.exists():
        PUBLIC_PATHS.extend(directory.rglob("*"))


class PublicPrivacyTests(unittest.TestCase):
    def test_public_artifacts_contain_no_original_fixture_identifiers(self):
        forbidden = (
            "Northstar Labs",
            "Harbor Data",
            "Meridian Defense Systems",
            "San Diego",
            "Seattle",
            "Remote US",
            "U.S. citizenship",
            "Active Secret",
            "northstar-ai-platform",
            "harbor-applied-ai",
            "meridian-embedded",
        )
        files = [path for path in PUBLIC_PATHS if path.is_file()]
        self.assertTrue(files)
        for path in files:
            content = path.read_text(encoding="utf-8")
            for value in forbidden:
                with self.subTest(path=path, value=value):
                    self.assertNotIn(value, content)


if __name__ == "__main__":
    unittest.main()
