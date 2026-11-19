"""Offline and live analysis orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from job_fit.agent import (
    analyze_job_with_agent,
    build_deep_agent,
    load_model_from_env,
)
from job_fit.contracts import (
    FitAssessment,
    JobPosting,
    ReviewReason,
    UserProfile,
)
from job_fit.extraction import extract_job_file
from job_fit.scoring import score_job
from job_fit.tools import list_jobs, load_profile
from job_fit.validation import ValidationResult, validate_job_payload


@dataclass
class AnalysisRun:
    mode: str
    model_name: str
    profile: UserProfile
    profile_path: Path
    job_paths: list[Path]
    records: list[dict[str, Any]]
    warnings: list[str]
    tool_events: list[dict[str, Any]]
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
    )


def run_analysis(
    *,
    profile_path: str | Path,
    jobs_dir: str | Path,
    mode: str,
) -> AnalysisRun:
    if mode not in {"offline", "live"}:
        raise ValueError("mode must be 'offline' or 'live'")
    profile = UserProfile.from_dict(load_profile(str(profile_path)))
    job_paths = [
        Path(item["path"]) for item in list_jobs(str(jobs_dir))
    ]
    if len(job_paths) < 1:
        raise ValueError(f"no Markdown or text jobs found in {jobs_dir}")

    warnings: list[str] = []
    events: list[dict[str, Any]] = [
        {
            "event": "planner_started",
            "mode": mode,
            "job_count": len(job_paths),
        }
    ]
    records: list[dict[str, Any]] = []
    model_name = "deterministic-offline"

    if mode == "offline":
        events.append(
            {
                "event": "offline_deterministic_pipeline",
                "reason": "No model credentials or network requests are used.",
            }
        )
        for path in job_paths:
            payload = extract_job_file(str(path), job_id=path.stem)
            job = JobPosting.from_dict(payload)
            validation = validate_job_payload(payload, raw_text=job.raw_text)
            records.append(
                _record(
                    profile=profile,
                    job=job,
                    validation=validation,
                    analysis_source="deterministic",
                )
            )
            events.append(
                {
                    "event": "job_analyzed",
                    "job_id": job.job_id,
                    "source": "deterministic",
                }
            )
    else:
        model = load_model_from_env()
        model_name = str(getattr(model, "model_name", None) or "configured-model")
        agent = build_deep_agent(model, project_root=Path.cwd())
        events.append(
            {
                "event": "deepagents_agent_built",
                "subagents": ["job_analyst"],
                "filesystem_backend": "FilesystemBackend",
            }
        )
        for path in job_paths:
            extra_reasons: list[ReviewReason] = []
            source = "deepagents"
            try:
                job, job_warnings = analyze_job_with_agent(
                    agent, profile=profile, job_path=path
                )
                validation = validate_job_payload(
                    job.to_dict(include_raw_text=True), raw_text=job.raw_text
                )
                warnings.extend(job_warnings)
            except Exception as exc:
                source = "deterministic_fallback"
                warnings.append(
                    f"{path.name}: DeepAgents output failed validation; "
                    f"deterministic fallback used: {exc}"
                )
                payload = extract_job_file(str(path), job_id=path.stem)
                job = JobPosting.from_dict(payload)
                validation = validate_job_payload(payload, raw_text=job.raw_text)
                extra_reasons.append(ReviewReason.INVALID_MODEL_OUTPUT)
            if not validation.is_valid:
                raise ValueError(
                    f"unable to validate {path.name}: "
                    + "; ".join(validation.errors)
                )
            records.append(
                _record(
                    profile=profile,
                    job=job,
                    validation=validation,
                    analysis_source=source,
                    extra_reasons=extra_reasons,
                )
            )
            events.append(
                {
                    "event": "job_analyzed",
                    "job_id": job.job_id,
                    "source": source,
                    "validation": validation.to_dict(),
                }
            )

    events.append(
        {
            "event": "deterministic_scoring_completed",
            "job_count": len(records),
        }
    )
    return AnalysisRun(
        mode=mode,
        model_name=model_name,
        profile=profile,
        profile_path=Path(profile_path),
        job_paths=job_paths,
        records=records,
        warnings=_dedupe(warnings),
        tool_events=events,
    )


def _record(
    *,
    profile: UserProfile,
    job: JobPosting,
    validation: ValidationResult,
    analysis_source: str,
    extra_reasons: list[ReviewReason] | None = None,
) -> dict[str, Any]:
    assessment: FitAssessment = score_job(
        profile,
        job,
        validation,
        review_reasons=extra_reasons or [],
    )
    return {
        "job": job.to_dict(),
        "assessment": assessment.to_dict(),
        "validation": validation.to_dict(),
        "analysis_source": analysis_source,
    }


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
