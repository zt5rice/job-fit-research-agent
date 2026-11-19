"""Safe, typed tool functions exposed to the DeepAgents planner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from job_fit.contracts import JobPosting, UserProfile
from job_fit.extraction import extract_job_fields, extract_job_file
from job_fit.scoring import (
    find_skill_gaps,
    match_requirements,
    score_job,
)
from job_fit.validation import detect_hard_blockers, validate_job_payload


def load_profile(path: str) -> dict[str, Any]:
    """Load and validate a local JSON profile. Never returns credentials."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return UserProfile.from_dict(payload).to_dict()


def list_jobs(directory: str) -> list[dict[str, str]]:
    """List local Markdown or text job descriptions without fetching the web."""
    root = Path(directory)
    if not root.is_dir():
        raise ValueError(f"job directory does not exist: {directory}")
    jobs: list[dict[str, str]] = []
    for path in sorted(root.glob("*")):
        if path.is_file() and path.suffix.casefold() in {".md", ".txt"}:
            jobs.append(
                {
                    "job_id": path.stem,
                    "path": str(path),
                    "name": path.name,
                }
            )
    return jobs


def read_job(path: str, job_id: str = "") -> dict[str, Any]:
    """Read a local job file and return validated extraction evidence."""
    payload = extract_job_file(path, job_id=job_id)
    return payload


def extract_job_fields_tool(
    job_text: str, source: str = "inline", job_id: str = ""
) -> dict[str, Any]:
    """Extract posting fields and line-level evidence from untrusted job text."""
    return extract_job_fields(job_text, source=source, job_id=job_id)


def validate_job_schema(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a candidate JobPosting dictionary and quote traceability."""
    raw_text = str(payload.get("raw_text", ""))
    return validate_job_payload(payload, raw_text=raw_text or None).to_dict()


def score_job_tool(
    profile_payload: dict[str, Any], job_payload: dict[str, Any]
) -> dict[str, Any]:
    """Run the deterministic rubric. This tool cannot accept a model score."""
    profile = UserProfile.from_dict(profile_payload)
    job = JobPosting.from_dict(job_payload)
    validation = validate_job_payload(
        job_payload, raw_text=job.raw_text or None
    )
    blockers, _ = detect_hard_blockers(profile, job)
    assessment = score_job(profile, job, validation)
    return {
        "assessment": assessment.to_dict(),
        "hard_blockers": [blocker.to_dict() for blocker in blockers],
    }


def find_skill_gaps_tool(
    profile_payload: dict[str, Any], job_payload: dict[str, Any]
) -> list[str]:
    """Return missing must-have requirements using deterministic matching."""
    profile = UserProfile.from_dict(profile_payload)
    job = JobPosting.from_dict(job_payload)
    return find_skill_gaps(profile, job)


def explain_requirement_matches(
    profile_payload: dict[str, Any], job_payload: dict[str, Any]
) -> list[dict[str, Any]]:
    """Explain which profile terms matched each must-have requirement."""
    profile = UserProfile.from_dict(profile_payload)
    job = JobPosting.from_dict(job_payload)
    return [
        {
            "requirement": match.requirement,
            "matched": match.matched,
            "matched_terms": match.matched_terms,
        }
        for match in match_requirements(profile, job)
    ]


def generate_resume_emphasis(
    profile_payload: dict[str, Any], job_payload: dict[str, Any]
) -> list[str]:
    """Generate resume emphasis that is limited to profile-supported claims."""
    profile = UserProfile.from_dict(profile_payload)
    job = JobPosting.from_dict(job_payload)
    validation = validate_job_payload(job_payload, raw_text=job.raw_text or None)
    return score_job(profile, job, validation).resume_emphasis


def generate_interview_prep(
    profile_payload: dict[str, Any], job_payload: dict[str, Any]
) -> list[str]:
    """Generate interview preparation prompts from deterministic gaps."""
    profile = UserProfile.from_dict(profile_payload)
    job = JobPosting.from_dict(job_payload)
    validation = validate_job_payload(job_payload, raw_text=job.raw_text or None)
    return score_job(profile, job, validation).interview_prep

