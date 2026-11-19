"""Command-line interface for the job-fit research demo."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from job_fit.agent import LiveConfigurationError
from job_fit.pipeline import run_analysis
from job_fit.reporting import write_reports


DEFAULT_PROFILE = "profile.example.json"
DEFAULT_JOBS = "examples/fixtures/jobs"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="job-fit",
        description="Evidence-backed, deterministic job-fit research prototype.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo = subparsers.add_parser("demo", help="Analyze local job fixtures.")
    mode = demo.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--offline",
        action="store_const",
        const="offline",
        dest="mode",
        help="Run without credentials or network access.",
    )
    mode.add_argument(
        "--live",
        action="store_const",
        const="live",
        dest="mode",
        help="Use a real DeepAgents planner via OPENAI_API_KEY.",
    )
    demo.add_argument("--profile", default=DEFAULT_PROFILE)
    demo.add_argument("--jobs", default=DEFAULT_JOBS)
    demo.add_argument("--output", default="reports/demo")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "demo":
        return _run_demo(args)
    return 2


def _run_demo(args: argparse.Namespace) -> int:
    output = Path(args.output)
    try:
        run = run_analysis(
            profile_path=args.profile,
            jobs_dir=args.jobs,
            mode=args.mode,
        )
        ranked, manifest = write_reports(
            profile=run.profile,
            profile_path=run.profile_path,
            job_paths=run.job_paths,
            records=run.records,
            output_dir=output,
            mode=run.mode,
            model_name=run.model_name,
            started_at=run.started_at,
            warnings=run.warnings,
            tool_events=run.tool_events,
        )
    except LiveConfigurationError as exc:
        print(f"Live mode configuration error: {exc}", file=sys.stderr)
        print(
            "Set OPENAI_API_KEY, OPENAI_BASE_URL (optional), and MODEL_NAME.",
            file=sys.stderr,
        )
        return 2
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        print(f"Demo failed: {exc}", file=sys.stderr)
        return 2

    print("Job Fit Research Agent")
    print(f"Mode: {run.mode}")
    for record in ranked["jobs"]:
        assessment = record["assessment"]
        review = "review" if assessment["needs_human_review"] else "clear"
        print(
            f"- {record['job']['title']} @ {record['job']['company']}: "
            f"{assessment['recommendation']} ({assessment['score']}/100, {review})"
        )
    print(f"Reports: {output.resolve()}")
    print(f"Manifest: {output.resolve() / 'run_manifest.json'}")
    print(f"Run ID: {manifest.run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
