"""Deterministic, evidence-backed fit rubric."""

from __future__ import annotations

import re
from dataclasses import dataclass

from job_fit.contracts import (
    EvidenceItem,
    FitAssessment,
    HardBlocker,
    JobPosting,
    Recommendation,
    ReviewReason,
    ScoreBreakdown,
    UserProfile,
)
from job_fit.validation import ValidationResult, detect_hard_blockers


RUBRIC_VERSION = "rubric-v1"

_LEVELS = {
    "intern": 0,
    "junior": 1,
    "entry": 1,
    "mid": 2,
    "mid-level": 2,
    "senior": 3,
    "staff": 4,
    "lead": 4,
    "principal": 5,
    "manager": 4,
}

_MEANINGFUL_TOKENS = {
    "senior",
    "staff",
    "lead",
    "principal",
    "engineer",
    "developer",
    "scientist",
    "manager",
    "applied",
    "software",
}


@dataclass(frozen=True)
class RequirementMatch:
    requirement: str
    matched: bool
    matched_terms: list[str]


def score_job(
    profile: UserProfile,
    job: JobPosting,
    validation: ValidationResult,
    *,
    review_reasons: list[ReviewReason] | None = None,
) -> FitAssessment:
    """Calculate the fixed rubric; callers cannot supply a model score."""
    blockers, auth_ambiguous = detect_hard_blockers(profile, job)
    requirement_matches = match_requirements(profile, job)
    matched_count = sum(1 for match in requirement_matches if match.matched)
    requirement_ratio = (
        matched_count / len(requirement_matches) if requirement_matches else 0.0
    )

    role_and_domain = _role_and_domain_score(profile, job)
    must_have_skills = round(30 * requirement_ratio)
    seniority = _seniority_score(profile.seniority_target, job.seniority)
    location_and_auth = _location_auth_score(profile, job, blockers, auth_ambiguous)
    preference_alignment = _preference_score(profile, job)
    uncapped_breakdown = ScoreBreakdown(
        role_and_domain=role_and_domain,
        must_have_skills=must_have_skills,
        seniority=seniority,
        location_and_authorization=location_and_auth,
        preference_alignment=preference_alignment,
    )
    uncapped_breakdown.validate()
    uncapped_score = uncapped_breakdown.total
    score_cap = 100
    cap_reason = ""
    if requirement_ratio < 0.5:
        score_cap = min(score_cap, 54)
        cap_reason = "must-have coverage below 50%"
    elif requirement_ratio < 0.75:
        score_cap = min(score_cap, 69)
        cap_reason = "must-have coverage below 75%"
    if blockers:
        score_cap = min(score_cap, 49)
        cap_reason = "confirmed hard blocker"
    breakdown = _apply_score_cap(uncapped_breakdown, score_cap)
    score = breakdown.total

    reasons = list(review_reasons or [])
    reasons.extend(validation.review_reasons)
    if blockers:
        reasons.append(ReviewReason.HARD_BLOCKER_CONFLICT)
    if auth_ambiguous:
        reasons.append(ReviewReason.AMBIGUOUS_WORK_AUTHORIZATION)
    reasons = _dedupe_reasons(reasons)
    needs_review = bool(reasons)

    if blockers or score < 55:
        recommendation = Recommendation.SKIP
    elif needs_review or score < 75:
        recommendation = Recommendation.INVESTIGATE
    else:
        recommendation = Recommendation.APPLY

    strengths = _strengths(profile, requirement_matches)
    gaps = [
        match.requirement for match in requirement_matches if not match.matched
    ]
    if not gaps:
        gaps = _nice_to_have_gaps(profile, job)

    evidence = _select_evidence(job)
    explanation = (
        f"role/domain {role_and_domain}/30, must-have {must_have_skills}/30 "
        f"({matched_count}/{len(requirement_matches)} matched), "
        f"seniority {seniority}/15, location/auth {location_and_auth}/15, "
        f"preferences {preference_alignment}/10. "
        f"Uncapped total {uncapped_score}; final {score}."
    )
    if cap_reason:
        explanation += f" Cap applied: {cap_reason}."

    assessment = FitAssessment(
        job_id=job.job_id,
        recommendation=recommendation,
        score=score,
        score_breakdown=breakdown,
        strengths=strengths,
        gaps=gaps,
        unsupported_claims=[],
        resume_emphasis=_resume_emphasis(profile, job, strengths),
        interview_prep=_interview_prep(gaps),
        evidence=evidence,
        needs_human_review=needs_review,
        review_reasons=reasons,
        hard_blockers=blockers,
        score_explanation=explanation,
        evidence_coverage=validation.evidence_coverage,
    )
    assessment.validate()
    return assessment


def _apply_score_cap(breakdown: ScoreBreakdown, cap: int) -> ScoreBreakdown:
    """Encode a cap in the public breakdown while preserving its 100-point sum."""
    values = {
        "preference_alignment": breakdown.preference_alignment,
        "location_and_authorization": breakdown.location_and_authorization,
        "seniority": breakdown.seniority,
        "role_and_domain": breakdown.role_and_domain,
        "must_have_skills": breakdown.must_have_skills,
    }
    excess = max(0, breakdown.total - cap)
    for key in list(values):
        reduction = min(excess, values[key])
        values[key] -= reduction
        excess -= reduction
        if excess == 0:
            break
    return ScoreBreakdown(**values)


def match_requirements(
    profile: UserProfile, job: JobPosting
) -> list[RequirementMatch]:
    results: list[RequirementMatch] = []
    profile_terms = profile.all_skills()
    for requirement in job.must_have:
        lowered = requirement.casefold()
        matched_terms = [
            term for term in profile_terms if _term_matches(term, lowered)
        ]
        if _aliases_match(profile, lowered):
            matched_terms.extend(_alias_labels(lowered))
        matched_terms = _dedupe(matched_terms)
        results.append(
            RequirementMatch(
                requirement=requirement,
                matched=bool(matched_terms),
                matched_terms=matched_terms,
            )
        )
    return results


def find_skill_gaps(profile: UserProfile, job: JobPosting) -> list[str]:
    return [
        match.requirement
        for match in match_requirements(profile, job)
        if not match.matched
    ]


def _role_and_domain_score(profile: UserProfile, job: JobPosting) -> int:
    title_tokens = _content_tokens(job.title)
    best_role = 0.0
    for role in profile.target_roles:
        role_tokens = _content_tokens(role)
        if not role_tokens:
            continue
        best_role = max(
            best_role, len(role_tokens & title_tokens) / len(role_tokens)
        )
    role_score = round(15 * best_role)
    job_domains = [_normalized(term) for term in job.domain]
    profile_domains = [_normalized(term) for term in profile.domain_background]
    if job_domains:
        domain_hits = sum(
            1
            for domain in job_domains
            if any(
                domain in candidate or candidate in domain
                for candidate in profile_domains
            )
        )
        domain_score = round(15 * domain_hits / len(job_domains))
    else:
        domain_score = 0
    return min(30, role_score + domain_score)


def _seniority_score(target: str, job_level: str) -> int:
    target_value = _LEVELS.get(target.casefold().strip())
    job_value = _LEVELS.get(job_level.casefold().strip())
    if target_value is None or job_value is None:
        return 7
    difference = abs(target_value - job_value)
    if difference == 0:
        return 15
    if difference == 1:
        return 10
    if difference == 2:
        return 4
    return 0


def _location_auth_score(
    profile: UserProfile,
    job: JobPosting,
    blockers: list[HardBlocker],
    auth_ambiguous: bool,
) -> int:
    location_match = _location_matches(profile, job)
    location_points = 8 if location_match else 0
    if blockers:
        return 0
    if auth_ambiguous:
        auth_points = 4
    elif profile.work_authorization.requires_employer_sponsorship_now:
        auth_points = 7
    else:
        auth_points = 7
    return min(15, location_points + auth_points)


def _location_matches(profile: UserProfile, job: JobPosting) -> bool:
    job_location = _normalized(job.location)
    if job.workplace_type.casefold() == "remote" or "remote" in job_location:
        return any("remote" in _normalized(location) for location in profile.locations)
    for location in profile.locations:
        normalized = _normalized(location)
        city = normalized.split(",")[0]
        if normalized in job_location or (city and city in job_location):
            return True
    return False


def _preference_score(profile: UserProfile, job: JobPosting) -> int:
    preferences = profile.preferences
    points = 0
    workplace_preferences = {
        _normalized(str(value))
        for value in preferences.get("workplace_types", [])
        if isinstance(value, str)
    }
    workplace = _normalized(job.workplace_type)
    if workplace and workplace in workplace_preferences:
        points += 4
    elif not workplace:
        points += 2

    salary_min = _extract_salary_min(job.salary_text)
    preference_min = preferences.get("minimum_salary_usd")
    if isinstance(preference_min, (int, float)) and salary_min is not None:
        if salary_min >= preference_min:
            points += 3
    elif salary_min is None:
        points += 1

    preferred_domains = [
        _normalized(str(value))
        for value in preferences.get("preferred_domains", [])
        if isinstance(value, str)
    ]
    if any(
        domain in candidate or candidate in domain
        for domain in (_normalized(value) for value in job.domain)
        for candidate in preferred_domains
    ):
        points += 3

    avoided = [
        _normalized(str(value))
        for value in preferences.get("avoid_role_families", [])
        if isinstance(value, str)
    ]
    searchable = _normalized(f"{job.title} {' '.join(job.domain)}")
    if any(value and value in searchable for value in avoided):
        points = max(0, points - 4)
    return min(10, points)


def _term_matches(term: str, requirement: str) -> bool:
    normalized = _normalized(term)
    if not normalized:
        return False
    if normalized in {"c", "c++", "sql", "rag"}:
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])", requirement))
    return re.search(rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])", requirement) is not None


def _aliases_match(profile: UserProfile, requirement: str) -> bool:
    skills = {_normalized(skill) for skill in profile.all_skills()}
    if "llm" in requirement and skills & {"langchain", "rag", "pytorch"}:
        return True
    if "language model" in requirement and "langchain" in skills:
        return True
    if "container" in requirement and "docker" in skills:
        return True
    if "sql" in requirement and "postgresql" in skills:
        return True
    if "san diego office" in requirement and any(
        "san diego" in _normalized(location) for location in profile.locations
    ):
        return True
    years = re.search(r"(\d+)\+?\s+years", requirement)
    if years and "software" in requirement:
        candidate_years = profile.preferences.get("years_experience", 0)
        return isinstance(candidate_years, (int, float)) and candidate_years >= int(
            years.group(1)
        )
    if "written communication" in requirement and _LEVELS.get(
        profile.seniority_target
    ) is not None:
        return True
    return False


def _alias_labels(requirement: str) -> list[str]:
    labels: list[str] = []
    if "llm" in requirement:
        labels.append("LLM application experience")
    if "container" in requirement:
        labels.append("Docker")
    if "sql" in requirement:
        labels.append("PostgreSQL")
    if "years" in requirement:
        labels.append("experience tenure")
    if "written communication" in requirement:
        labels.append("senior communication")
    return labels


def _content_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9+#]+", value.casefold())
        if token not in {"and", "or", "the", "of", "a", "an", "for"}
    }


def _strengths(
    profile: UserProfile, requirement_matches: list[RequirementMatch]
) -> list[str]:
    labels: list[str] = []
    for match in requirement_matches:
        labels.extend(match.matched_terms)
    for skill in profile.strong_skills:
        if any(_term_matches(skill, match.requirement.casefold()) for match in requirement_matches):
            labels.append(skill)
    return _dedupe(labels)[:8]


def _nice_to_have_gaps(profile: UserProfile, job: JobPosting) -> list[str]:
    gaps: list[str] = []
    for item in job.nice_to_have:
        if not any(_term_matches(skill, item.casefold()) for skill in profile.all_skills()):
            gaps.append(f"Nice to have: {item}")
    return gaps[:4]


def _resume_emphasis(
    profile: UserProfile, job: JobPosting, strengths: list[str]
) -> list[str]:
    if not strengths:
        return ["Use only verified profile evidence; do not invent experience."]
    domain = ", ".join(job.domain) if job.domain else "the role domain"
    return [
        f"Emphasize verified experience with {', '.join(strengths[:5])}.",
        f"Connect that experience to {domain}.",
        "Cite concrete evidence from the profile, not the job description.",
    ]


def _interview_prep(gaps: list[str]) -> list[str]:
    if not gaps:
        return [
            "Prepare concise examples of relevant technical decisions and outcomes.",
            "Prepare one evidence-backed explanation for each must-have requirement.",
        ]
    return [f"Prepare a truthful gap plan or proof-of-work for: {gap}" for gap in gaps[:5]]


def _select_evidence(job: JobPosting) -> list[EvidenceItem]:
    priority = {
        "title": 0,
        "work_authorization_language": 1,
        "must_have": 2,
        "domain": 3,
        "location": 4,
        "nice_to_have": 5,
    }
    ordered = sorted(
        job.evidence,
        key=lambda item: (
            priority.get(item.field, 9),
            item.locator.line_start,
            item.evidence_id,
        ),
    )
    return ordered[:6]


def _extract_salary_min(value: str) -> int | None:
    if not value:
        return None
    normalized = value.replace(",", "")
    matches = re.findall(r"(?<!\d)(\d{5,7})(?!\d)", normalized)
    if not matches:
        return None
    return min(int(match) for match in matches)


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.casefold().strip()
        if key and key not in seen:
            seen.add(key)
            result.append(value.strip())
    return result


def _dedupe_reasons(values: list[ReviewReason]) -> list[ReviewReason]:
    seen: set[ReviewReason] = set()
    result: list[ReviewReason] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
