"""Safe, typed tool functions exposed to the DeepAgents planner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from job_fit.contracts import JobPosting, UserProfile
from job_fit.extraction import extract_job_fields, extract_job_file
from job_fit.validation import validate_job_payload


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



