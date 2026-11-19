import json
import tempfile
import unittest
from pathlib import Path

from job_fit.pipeline import run_analysis
from job_fit.reporting import write_reports


ROOT = Path(__file__).resolve().parents[1]


class PipelineReportingTests(unittest.TestCase):
    def test_offline_demo_writes_all_required_outputs(self):
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
                "ranked_jobs.md",
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
            self.assertTrue(manifest.tool_events)
            all_text = "\n".join(
                path.read_text(encoding="utf-8")
                for path in output.iterdir()
                if path.suffix in {".json", ".md"}
            )
            self.assertNotIn("## Responsibilities", all_text)
            for record in ranked["jobs"]:
                self.assertTrue(record["assessment"]["evidence"])

    def test_manifest_records_input_hashes_and_limitations(self):
        run = run_analysis(
            profile_path=ROOT / "profile.example.json",
            jobs_dir=ROOT / "examples/fixtures/jobs",
            mode="offline",
        )
        with tempfile.TemporaryDirectory() as temp:
            _, manifest = write_reports(
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
            payload = manifest.to_dict()
            self.assertEqual(len(payload["inputs"]), 4)
            self.assertTrue(all(item["sha256"] for item in payload["inputs"]))
            self.assertTrue(payload["limitations"])
            self.assertEqual(payload["rubric_version"], "rubric-v1")


if __name__ == "__main__":
    unittest.main()

