"""Deterministic validation, evidence coverage, and hard-blocker checks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from job_fit.contracts import (
    ContractError,
    HardBlocker,
    JobPosting,
    ReviewReason,
    UserProfile,
)


@dataclass(frozen=True)
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    review_reasons: list[ReviewReason] = field(default_factory=list)
    evidence_coverage: float = 0.0

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "review_reasons": [reason.value for reason in self.review_reasons],
            "evidence_coverage": round(self.evidence_coverage, 4),
        }


def validate_job_payload(
    payload: dict[str, Any], *, raw_text: str | None = None
) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    review_reasons: list[ReviewReason] = []
    try:
        job = JobPosting.from_dict(payload)
    except ContractError as exc:
        return ValidationResult(
            errors=[str(exc)],
            review_reasons=[ReviewReason.INVALID_MODEL_OUTPUT],
        )

    if len(job.evidence) == 0:
        errors.append("job evidence is required")
        review_reasons.append(ReviewReason.MISSING_EVIDENCE)

    evidence_ids = [item.evidence_id for item in job.evidence]
    if len(evidence_ids) != len(set(evidence_ids)):
        errors.append("evidence_id values must be unique")

    source_text = raw_text if raw_text is not None else job.raw_text
    if source_text:
        line_count = len(source_text.splitlines())
        for item in job.evidence:
            if item.locator.line_end > line_count:
                errors.append(
                    f"{item.evidence_id} locator exceeds source line count"
                )
            if not _quote_present(item.quote, source_text):
                errors.append(
                    f"{item.evidence_id} quote does not appear in source text"
                )
    else:
        warnings.append("source text unavailable; quote fidelity could not be checked")
        review_reasons.append(ReviewReason.MISSING_EVIDENCE)

    coverage = calculate_evidence_coverage(job, source_text or "")
    if coverage < 0.8:
        warnings.append(f"low evidence coverage: {coverage:.2f}")
        review_reasons.append(ReviewReason.LOW_EVIDENCE_COVERAGE)

    if not job.must_have:
        warnings.append("no must-have requirements were extracted")
        review_reasons.append(ReviewReason.UNCERTAIN_ROLE_SCOPE)

    if job.extraction_warnings:
        warnings.extend(job.extraction_warnings)
        review_reasons.append(ReviewReason.SUSPICIOUS_JOB_INSTRUCTIONS)

    return ValidationResult(
        errors=_dedupe(errors),
        warnings=_dedupe(warnings),
        review_reasons=_dedupe_enums(review_reasons),
        evidence_coverage=coverage,
    )


def calculate_evidence_coverage(job: JobPosting, raw_text: str = "") -> float:
    checks: list[bool] = [
        bool(job.evidence_for_field("title")),
        bool(job.evidence_for_field("company")),
        bool(job.evidence_for_field("location")),
    ]
    for requirement in job.must_have:
        checks.append(
            any(
                item.field == "must_have"
                and _normalized(requirement) in _normalized(item.quote)
                for item in job.evidence
            )
        )
    if not checks:
        return 0.0
    return sum(checks) / len(checks)


def detect_hard_blockers(
    profile: UserProfile, job: JobPosting, raw_text: str = ""
) -> tuple[list[HardBlocker], bool]:
    """Return confirmed blockers and whether work authorization is ambiguous."""
    text = " ".join(
        [
            raw_text or job.raw_text,
            job.work_authorization_language,
            " ".join(job.must_have),
        ]
    ).casefold()
    blockers: list[HardBlocker] = []
    evidence_ids = _matching_evidence_ids(job, raw_text)

    rejects_sponsorship = any(
        phrase in text
        for phrase in (
            "no visa sponsorship",
            "no sponsorship",
            "sponsorship is not available",
            "not able to sponsor",
            "unable to sponsor",
            "without sponsorship",
        )
    )
    citizenship_required = any(
        phrase in text
        for phrase in (
            "citizenship required",
            "citizen required",
        )
    )
    clearance_required = any(
        phrase in text
        for phrase in (
            "security clearance required",
            "minimum clearance required",
            "must be able to obtain a security clearance",
        )
    ) and not any(
        phrase in text
        for phrase in ("no clearance required", "clearance not required")
    )

    if profile.work_authorization.requires_employer_sponsorship_now and rejects_sponsorship:
        blockers.append(
            HardBlocker(
                code="sponsorship_unavailable",
                message="The posting rejects employer sponsorship and the profile requires it.",
                evidence_ids=evidence_ids,
            )
        )
    if citizenship_required:
        blockers.append(
            HardBlocker(
                code="citizenship_required",
                message="The posting requires citizenship that the profile does not establish.",
                evidence_ids=evidence_ids,
            )
        )
    if clearance_required and profile.work_authorization.security_clearance.casefold() in {
        "",
        "none",
        "no",
        "n/a",
    }:
        blockers.append(
            HardBlocker(
                code="clearance_required",
                message="The posting requires a security clearance not present in the profile.",
                evidence_ids=evidence_ids,
            )
        )

    auth_language = job.work_authorization_language.casefold()
    clearly_available = any(
        phrase in auth_language
        for phrase in (
            "sponsorship is available",
            "visa sponsorship available",
            "open to sponsorship",
            "will sponsor",
        )
    )
    clearly_not_required = not profile.work_authorization.requires_employer_sponsorship_now
    ambiguous = (
        not blockers
        and profile.work_authorization.requires_employer_sponsorship_now
        and not clearly_available
        and not clearly_not_required
    )
    return blockers, ambiguous


def _quote_present(quote: str, source_text: str) -> bool:
    return _normalized(quote) in _normalized(source_text)


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _matching_evidence_ids(job: JobPosting, raw_text: str) -> list[str]:
    text = (raw_text or job.raw_text).casefold()
    ids: list[str] = []
    for item in job.evidence:
        if item.field in {"work_authorization_language", "must_have"}:
            if item.quote.casefold() in text:
                ids.append(item.evidence_id)
    return ids[:4]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _dedupe_enums(values: list[ReviewReason]) -> list[ReviewReason]:
    seen: set[ReviewReason] = set()
    result: list[ReviewReason] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result

