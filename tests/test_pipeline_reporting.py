import tempfile
import unittest
from pathlib import Path

from job_fit.pipeline import run_analysis
from job_fit.reporting import write_reports


ROOT = Path(__file__).resolve().parents[1]


class JsonReportingTests(unittest.TestCase):
    def test_offline_demo_writes_json_and_manifest(self):
        run = run_analysis(
            profile_path=ROOT / "profile.example.json",
            jobs_dir=ROOT / "examples/fixtures/jobs",
            mode="offline",
        )
        with tempfile.TemporaryDirectory() as temp:
            ranked, manifest = write_reports(
                profile=run.profile,
                profile_path=run.profile_path,
                job_paths=run.job_paths,
                records=run.records,
                output_dir=temp,
                mode=run.mode,
                model_name=run.model_name,
                started_at=run.started_at,
                warnings=run.warnings,
                tool_events=run.tool_events,
            )
            output = Path(temp)
            expected = {
                "ranked_jobs.json",
                "run_manifest.json",
                "assessment_job_001_strong.json",
                "assessment_job_002_investigate.json",
                "assessment_job_003_blocked.json",
            }
            self.assertTrue(
                expected.issubset({path.name for path in output.iterdir()})
            )
            self.assertEqual(len(ranked["jobs"]), 3)
            self.assertEqual(manifest.mode, "offline")
            self.assertEqual(len(manifest.inputs), 4)
            self.assertTrue(manifest.tool_events)
            self.assertTrue(manifest.limitations)
            for record in ranked["jobs"]:
                self.assertTrue(record["assessment"]["evidence"])


if __name__ == "__main__":
    unittest.main()
