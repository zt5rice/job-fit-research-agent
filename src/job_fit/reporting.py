"""JSON and Markdown reports plus replayable run manifests."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from job_fit import __version__
from job_fit.agent import PROMPT_VERSION
from job_fit.contracts import (
    FitAssessment,
    InputFingerprint,
    JobPosting,
    RunManifest,
    UserProfile,
)
from job_fit.scoring import RUBRIC_VERSION
from job_fit.validation import ValidationResult


LIMITATIONS = [
    "Independent interview-grade prototype; not production software.",
    "Offline mode uses deterministic extraction and does not call an LLM.",
    "Live extraction quality depends on the configured OpenAI-compatible model.",
    "Results require human review before any external use.",
    "No authenticated scraping, automated applications, or employer contact.",
]


def write_reports(
    *,
    profile: UserProfile,
    profile_path: str | Path,
    job_paths: Iterable[str | Path],
    records: list[dict[str, Any]],
    output_dir: str | Path,
    mode: str,
    model_name: str,
    started_at: str,
    warnings: list[str],
    tool_events: list[dict[str, Any]],
) -> tuple[dict[str, Any], RunManifest]:
    """Write assessment JSON, ranked JSON/Markdown, and a run manifest."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    ranked_records = sorted(
        records,
        key=lambda item: (
            -int(item["assessment"]["score"]),
            item["assessment"]["recommendation"],
            item["job"]["job_id"],
        ),
    )
    output_files: list[str] = []
    for record in ranked_records:
        assessment_path = output / f"assessment_{record['job']['job_id']}.json"
        _write_json(
            assessment_path,
            {
                "job": record["job"],
                "assessment": record["assessment"],
                "validation": record["validation"],
                "analysis_source": record["analysis_source"],
            },
        )
        output_files.append(str(assessment_path))

    ranked_payload = {
        "schema_version": "1.0",
        "generated_at": _utc_now(),
        "mode": mode,
        "rubric_version": RUBRIC_VERSION,
        "candidate_id": profile.candidate_id,
        "jobs": ranked_records,
    }
    ranked_json_path = output / "ranked_jobs.json"
    _write_json(ranked_json_path, ranked_payload)
    output_files.append(str(ranked_json_path))

    ranked_markdown_path = output / "ranked_jobs.md"
    ranked_markdown_path.write_text(
        render_markdown(profile, ranked_records, mode=mode), encoding="utf-8"
    )
    output_files.append(str(ranked_markdown_path))

    manifest = RunManifest(
        run_id=_run_id(),
        started_at=started_at,
        completed_at=_utc_now(),
        mode=mode,
        model_name=model_name,
        git_commit=_git_commit(),
        python_version=platform.python_version(),
        deepagents_version=_package_version("deepagents"),
        rubric_version=RUBRIC_VERSION,
        prompt_version=PROMPT_VERSION,
        inputs=[
            fingerprint(profile_path),
            *[fingerprint(path) for path in job_paths],
        ],
        job_results=[
            {
                "job_id": record["job"]["job_id"],
                "score": record["assessment"]["score"],
                "recommendation": record["assessment"]["recommendation"],
                "needs_human_review": record["assessment"]["needs_human_review"],
                "review_reasons": record["assessment"]["review_reasons"],
                "evidence_coverage": record["assessment"]["evidence_coverage"],
                "analysis_source": record["analysis_source"],
            }
            for record in ranked_records
        ],
        tool_events=list(tool_events),
        warnings=_dedupe([*warnings, *LIMITATIONS]),
        limitations=list(LIMITATIONS),
        output_files=output_files,
    )
    manifest_path = output / "run_manifest.json"
    output_files.append(str(manifest_path))
    _write_json(manifest_path, manifest.to_dict())
    return ranked_payload, manifest


def render_markdown(
    profile: UserProfile,
    records: list[dict[str, Any]],
    *,
    mode: str,
) -> str:
    lines = [
        "# Job Fit Research Report",
        "",
        f"- Candidate: `{profile.candidate_id}`",
        f"- Mode: `{mode}`",
        f"- Rubric: `{RUBRIC_VERSION}`",
        "- This is a research aid, not an application or hiring decision.",
        "",
        "## Ranking",
        "",
        "| Rank | Job | Company | Recommendation | Score | Review | Evidence |",
        "|---:|---|---|---|---:|---|---:|",
    ]
    for rank, record in enumerate(records, start=1):
        assessment = record["assessment"]
        review = "yes" if assessment["needs_human_review"] else "no"
        lines.append(
            "| {rank} | {title} | {company} | **{recommendation}** | "
            "{score} | {review} | {coverage:.0%} |".format(
                rank=rank,
                title=_md(record["job"]["title"]),
                company=_md(record["job"]["company"]),
                recommendation=assessment["recommendation"],
                score=assessment["score"],
                review=review,
                coverage=assessment["evidence_coverage"],
            )
        )

    for record in records:
        job = record["job"]
        assessment = record["assessment"]
        lines.extend(
            [
                "",
                f"## {job['title']} — {job['company']}",
                "",
                f"**Recommendation:** `{assessment['recommendation']}`  ",
                f"**Deterministic score:** `{assessment['score']}/100`  ",
                f"**Human review:** "
                f"`{'required' if assessment['needs_human_review'] else 'not required'}`",
                "",
                assessment["score_explanation"],
                "",
                "### Score breakdown",
                "",
                "| Dimension | Points |",
                "|---|---:|",
                f"| Role and domain | {assessment['score_breakdown']['role_and_domain']}/30 |",
                f"| Must-have skills | {assessment['score_breakdown']['must_have_skills']}/30 |",
                f"| Seniority | {assessment['score_breakdown']['seniority']}/15 |",
                f"| Location and authorization | "
                f"{assessment['score_breakdown']['location_and_authorization']}/15 |",
                f"| Preferences | {assessment['score_breakdown']['preference_alignment']}/10 |",
                "",
            ]
        )
        if assessment["review_reasons"]:
            lines.extend(
                [
                    "### Human-review reasons",
                    "",
                    *[f"- `{reason}`" for reason in assessment["review_reasons"]],
                    "",
                ]
            )
        if assessment["hard_blockers"]:
            lines.extend(
                [
                    "### Hard blockers",
                    "",
                    *[
                        f"- **{blocker['code']}:** {_md(blocker['message'])}"
                        for blocker in assessment["hard_blockers"]
                    ],
                    "",
                ]
            )
        lines.extend(
            [
                "### Strengths",
                "",
                *_bullets(assessment["strengths"], empty="No deterministic strengths."),
                "",
                "### Gaps",
                "",
                *_bullets(assessment["gaps"], empty="No unmatched must-haves."),
                "",
                "### Resume emphasis",
                "",
                *_bullets(assessment["resume_emphasis"]),
                "",
                "### Interview preparation",
                "",
                *_bullets(assessment["interview_prep"]),
                "",
                "### Evidence",
                "",
            ]
        )
        for item in assessment["evidence"]:
            locator = item["locator"]
            lines.append(
                f"- `{item['evidence_id']}` ({_md(item['field'])}, "
                f"lines {locator['line_start']}-{locator['line_end']}): "
                f"> {_md(item['quote'])}"
            )
    lines.append("")
    return "\n".join(lines)


def fingerprint(path: str | Path) -> InputFingerprint:
    file_path = Path(path)
    data = file_path.read_bytes()
    return InputFingerprint(
        path=str(file_path),
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
    )


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _bullets(values: Iterable[str], *, empty: str = "None.") -> list[str]:
    items = list(values)
    return [f"- {_md(item)}" for item in items] if items else [empty]


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")


def _package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def _git_commit() -> str:
    env_sha = os.environ.get("GITHUB_SHA", "").strip()
    if env_sha:
        return env_sha
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"

