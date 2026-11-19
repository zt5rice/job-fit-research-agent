"""Typed contracts for the deterministic job-fit pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any, Mapping, Sequence


class ContractError(ValueError):
    """Raised when untrusted JSON does not satisfy a contract."""


class Recommendation(str, Enum):
    APPLY = "apply"
    INVESTIGATE = "investigate"
    SKIP = "skip"


class ReviewReason(str, Enum):
    MISSING_EVIDENCE = "missing_evidence"
    LOW_EVIDENCE_COVERAGE = "low_evidence_coverage"
    AMBIGUOUS_WORK_AUTHORIZATION = "ambiguous_work_authorization"
    HARD_BLOCKER_CONFLICT = "hard_blocker_conflict"
    SUSPICIOUS_JOB_INSTRUCTIONS = "suspicious_job_instructions"
    INVALID_MODEL_OUTPUT = "invalid_model_output"
    PREFERENCE_CONFLICT = "preference_conflict"
    UNCERTAIN_ROLE_SCOPE = "uncertain_role_scope"


@dataclass(frozen=True)
class LineLocator:
    line_start: int
    line_end: int

    def validate(self) -> None:
        if self.line_start < 1 or self.line_end < self.line_start:
            raise ContractError(
                f"invalid line locator: {self.line_start}-{self.line_end}"
            )

    def to_dict(self) -> dict[str, int]:
        self.validate()
        return {"line_start": self.line_start, "line_end": self.line_end}


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    source: str
    quote: str
    locator: LineLocator
    field: str = ""

    def validate(self) -> None:
        if not self.evidence_id.strip():
            raise ContractError("evidence_id is required")
        if not self.source.strip():
            raise ContractError("evidence source is required")
        if not self.quote.strip():
            raise ContractError("evidence quote is required")
        self.locator.validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "evidence_id": self.evidence_id,
            "source": self.source,
            "quote": self.quote,
            "locator": self.locator.to_dict(),
            "field": self.field,
        }


@dataclass(frozen=True)
class WorkAuthorization:
    current: str = ""
    requires_employer_sponsorship_now: bool = False
    future_plan: str = ""
    security_clearance: str = ""
    notes: str = ""

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "WorkAuthorization":
        data = payload or {}
        return cls(
            current=str(data.get("current", "")),
            requires_employer_sponsorship_now=_as_bool(
                data.get("requires_employer_sponsorship_now", False),
                "work_authorization.requires_employer_sponsorship_now",
            ),
            future_plan=str(data.get("future_plan", "")),
            security_clearance=str(data.get("security_clearance", "")),
            notes=str(data.get("notes", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class UserProfile:
    candidate_id: str
    headline: str
    target_roles: list[str]
    strong_skills: list[str]
    supporting_skills: list[str]
    domain_background: list[str]
    seniority_target: str
    locations: list[str]
    work_authorization: WorkAuthorization
    disallowed_claims: list[str] = field(default_factory=list)
    preferences: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "UserProfile":
        if not isinstance(payload, Mapping):
            raise ContractError("profile must be a JSON object")
        candidate_id = _required_str(payload, "candidate_id")
        headline = _required_str(payload, "headline")
        return cls(
            candidate_id=candidate_id,
            headline=headline,
            target_roles=_str_list(payload.get("target_roles"), "target_roles"),
            strong_skills=_str_list(payload.get("strong_skills"), "strong_skills"),
            supporting_skills=_str_list(
                payload.get("supporting_skills"), "supporting_skills"
            ),
            domain_background=_str_list(
                payload.get("domain_background"), "domain_background"
            ),
            seniority_target=str(payload.get("seniority_target", "")).strip().lower(),
            locations=_str_list(payload.get("locations"), "locations"),
            work_authorization=WorkAuthorization.from_dict(
                payload.get("work_authorization")
            ),
            disallowed_claims=_str_list(
                payload.get("disallowed_claims"), "disallowed_claims"
            ),
            preferences=_dict_copy(payload.get("preferences"), "preferences"),
        )

    def all_skills(self) -> list[str]:
        return _dedupe([*self.strong_skills, *self.supporting_skills])

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "headline": self.headline,
            "target_roles": list(self.target_roles),
            "strong_skills": list(self.strong_skills),
            "supporting_skills": list(self.supporting_skills),
            "domain_background": list(self.domain_background),
            "seniority_target": self.seniority_target,
            "locations": list(self.locations),
            "work_authorization": self.work_authorization.to_dict(),
            "disallowed_claims": list(self.disallowed_claims),
            "preferences": dict(self.preferences),
        }


@dataclass(frozen=True)
class JobPosting:
    job_id: str
    source_url: str
    retrieved_at: str
    company: str
    title: str
    location: str
    seniority: str
    responsibilities: list[str]
    must_have: list[str]
    nice_to_have: list[str]
    domain: list[str]
    work_authorization_language: str
    evidence: list[EvidenceItem]
    workplace_type: str = ""
    salary_text: str = ""
    source_path: str = ""
    extraction_warnings: list[str] = field(default_factory=list)
    raw_text: str = field(default="", repr=False, compare=False)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "JobPosting":
        if not isinstance(payload, Mapping):
            raise ContractError("job must be a JSON object")
        evidence_payload = payload.get("evidence", [])
        if not isinstance(evidence_payload, Sequence) or isinstance(
            evidence_payload, (str, bytes)
        ):
            raise ContractError("evidence must be a list")
        evidence: list[EvidenceItem] = []
        for item in evidence_payload:
            if not isinstance(item, Mapping):
                raise ContractError("each evidence item must be an object")
            locator_payload = item.get("locator", {})
            if not isinstance(locator_payload, Mapping):
                raise ContractError("evidence locator must be an object")
            evidence.append(
                EvidenceItem(
                    evidence_id=_required_str(item, "evidence_id"),
                    source=_required_str(item, "source"),
                    quote=_required_str(item, "quote"),
                    locator=LineLocator(
                        line_start=_as_int(
                            locator_payload.get("line_start"), "line_start"
                        ),
                        line_end=_as_int(locator_payload.get("line_end"), "line_end"),
                    ),
                    field=str(item.get("field", "")),
                )
            )
        job = cls(
            job_id=_required_str(payload, "job_id"),
            source_url=str(payload.get("source_url", "")),
            retrieved_at=str(payload.get("retrieved_at", "")),
            company=_required_str(payload, "company"),
            title=_required_str(payload, "title"),
            location=str(payload.get("location", "")),
            seniority=str(payload.get("seniority", "")).lower(),
            responsibilities=_str_list(
                payload.get("responsibilities"), "responsibilities"
            ),
            must_have=_str_list(payload.get("must_have"), "must_have"),
            nice_to_have=_str_list(payload.get("nice_to_have"), "nice_to_have"),
            domain=_str_list(payload.get("domain"), "domain"),
            work_authorization_language=str(
                payload.get("work_authorization_language", "")
            ),
            evidence=evidence,
            workplace_type=str(payload.get("workplace_type", "")),
            salary_text=str(payload.get("salary_text", "")),
            source_path=str(payload.get("source_path", "")),
            extraction_warnings=_str_list(
                payload.get("extraction_warnings"), "extraction_warnings"
            ),
            raw_text=str(payload.get("raw_text", "")),
        )
        job.validate_basic()
        return job

    def validate_basic(self) -> None:
        for field_name in ("job_id", "company", "title"):
            if not getattr(self, field_name).strip():
                raise ContractError(f"job.{field_name} is required")
        for item in self.evidence:
            item.validate()

    def evidence_for_field(self, field_name: str) -> list[EvidenceItem]:
        return [item for item in self.evidence if item.field == field_name]

    def to_dict(self, *, include_raw_text: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "job_id": self.job_id,
            "source_url": self.source_url,
            "retrieved_at": self.retrieved_at,
            "company": self.company,
            "title": self.title,
            "location": self.location,
            "seniority": self.seniority,
            "responsibilities": list(self.responsibilities),
            "must_have": list(self.must_have),
            "nice_to_have": list(self.nice_to_have),
            "domain": list(self.domain),
            "work_authorization_language": self.work_authorization_language,
            "evidence": [item.to_dict() for item in self.evidence],
            "workplace_type": self.workplace_type,
            "salary_text": self.salary_text,
            "source_path": self.source_path,
            "extraction_warnings": list(self.extraction_warnings),
        }
        if include_raw_text:
            payload["raw_text"] = self.raw_text
        return payload


@dataclass(frozen=True)
class HardBlocker:
    code: str
    message: str
    evidence_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "evidence_ids": list(self.evidence_ids),
        }


@dataclass(frozen=True)
class ScoreBreakdown:
    role_and_domain: int
    must_have_skills: int
    seniority: int
    location_and_authorization: int
    preference_alignment: int

    @property
    def total(self) -> int:
        return (
            self.role_and_domain
            + self.must_have_skills
            + self.seniority
            + self.location_and_authorization
            + self.preference_alignment
        )

    def validate(self) -> None:
        limits = {
            "role_and_domain": (self.role_and_domain, 30),
            "must_have_skills": (self.must_have_skills, 30),
            "seniority": (self.seniority, 15),
            "location_and_authorization": (self.location_and_authorization, 15),
            "preference_alignment": (self.preference_alignment, 10),
        }
        for name, (value, maximum) in limits.items():
            if not 0 <= value <= maximum:
                raise ContractError(f"{name} must be between 0 and {maximum}")

    def to_dict(self) -> dict[str, int]:
        self.validate()
        return {
            "role_and_domain": self.role_and_domain,
            "must_have_skills": self.must_have_skills,
            "seniority": self.seniority,
            "location_and_authorization": self.location_and_authorization,
            "preference_alignment": self.preference_alignment,
            "total": self.total,
        }


@dataclass(frozen=True)
class FitAssessment:
    job_id: str
    recommendation: Recommendation
    score: int
    score_breakdown: ScoreBreakdown
    strengths: list[str]
    gaps: list[str]
    unsupported_claims: list[str]
    resume_emphasis: list[str]
    interview_prep: list[str]
    evidence: list[EvidenceItem]
    needs_human_review: bool
    review_reasons: list[ReviewReason] = field(default_factory=list)
    hard_blockers: list[HardBlocker] = field(default_factory=list)
    score_explanation: str = ""
    evidence_coverage: float = 0.0

    def validate(self) -> None:
        if not 0 <= self.score <= 100:
            raise ContractError("score must be between 0 and 100")
        if self.score != self.score_breakdown.total:
            raise ContractError("score must equal the deterministic breakdown total")
        if not self.evidence:
            raise ContractError("an assessment must contain evidence")
        if self.needs_human_review and not self.review_reasons:
            raise ContractError("human review requires at least one review reason")
        if not 0.0 <= self.evidence_coverage <= 1.0:
            raise ContractError("evidence_coverage must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "job_id": self.job_id,
            "recommendation": self.recommendation.value,
            "score": self.score,
            "score_breakdown": self.score_breakdown.to_dict(),
            "strengths": list(self.strengths),
            "gaps": list(self.gaps),
            "unsupported_claims": list(self.unsupported_claims),
            "resume_emphasis": list(self.resume_emphasis),
            "interview_prep": list(self.interview_prep),
            "evidence": [item.to_dict() for item in self.evidence],
            "needs_human_review": self.needs_human_review,
            "review_reasons": [reason.value for reason in self.review_reasons],
            "hard_blockers": [blocker.to_dict() for blocker in self.hard_blockers],
            "score_explanation": self.score_explanation,
            "evidence_coverage": round(self.evidence_coverage, 4),
        }


@dataclass(frozen=True)
class InputFingerprint:
    path: str
    sha256: str
    size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RunManifest:
    run_id: str
    started_at: str
    completed_at: str
    mode: str
    model_name: str
    git_commit: str
    python_version: str
    deepagents_version: str
    rubric_version: str
    prompt_version: str
    inputs: list[InputFingerprint]
    job_results: list[dict[str, Any]]
    tool_events: list[dict[str, Any]]
    warnings: list[str]
    limitations: list[str]
    output_files: list[str]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def jsonable(value: Any) -> Any:
    """Convert dataclasses and enums to deterministic JSON-compatible values."""
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def _required_str(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{key} is required and must be a non-empty string")
    return value.strip()


def _str_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ContractError(f"{field_name} must be a list of strings")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ContractError(f"{field_name} must contain only strings")
        if item.strip():
            result.append(item.strip())
    return result


def _dict_copy(value: Any, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ContractError(f"{field_name} must be an object")
    return dict(value)


def _as_bool(value: Any, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0", ""}:
            return False
    raise ContractError(f"{field_name} must be a boolean")


def _as_int(value: Any, field_name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"{field_name} must be an integer") from exc


def _dedupe(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.casefold().strip()
        if key and key not in seen:
            seen.add(key)
            result.append(value.strip())
    return result
