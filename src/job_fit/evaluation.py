"""Synthetic evaluation corpus runner and regression checks."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from job_fit.contracts import JobPosting, UserProfile
from job_fit.extraction import extract_job_fields
from job_fit.scoring import RUBRIC_VERSION, score_job
from job_fit.validation import detect_hard_blockers, validate_job_payload


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = PROJECT_ROOT / "evals" / "labeled_jobs.json"
DEFAULT_PROFILE = PROJECT_ROOT / "profile.example.json"


def run_evaluation(
    *,
    corpus_path: str | Path = DEFAULT_CORPUS,
    profile_path: str | Path = DEFAULT_PROFILE,
) -> dict[str, Any]:
    corpus = json.loads(Path(corpus_path).read_text(encoding="utf-8"))
    profile = UserProfile.from_dict(
        json.loads(Path(profile_path).read_text(encoding="utf-8"))
    )
    results: list[dict[str, Any]] = []
    for case in corpus["cases"]:
        raw_text = _render_case(case)
        payload = extract_job_fields(
            raw_text,
            source=f"eval/{case['case_id']}.md",
            job_id=case["case_id"],
        )
        job = JobPosting.from_dict(payload)
        validation = validate_job_payload(payload, raw_text=raw_text)
        assessment = score_job(profile, job, validation)
        blockers, _ = detect_hard_blockers(profile, job, raw_text)
        results.append(
            {
                "case_id": case["case_id"],
                "label": case["label"],
                "expected_review": bool(case["expected_review"]),
                "hard_blocker_expected": bool(case["hard_blocker"]),
                "predicted_recommendation": assessment.recommendation.value,
                "predicted_review": assessment.needs_human_review,
                "score": assessment.score,
                "evidence_coverage": assessment.evidence_coverage,
                "unsupported_claims": len(assessment.unsupported_claims),
                "hard_blockers": [blocker.code for blocker in blockers],
                "review_reasons": [reason.value for reason in assessment.review_reasons],
            }
        )

    metrics = _metrics(results)
    regression_failures: list[str] = []
    if metrics["recommendation_accuracy"] < 0.8:
        regression_failures.append("recommendation accuracy below 0.80")
    if metrics["mean_evidence_coverage"] < 0.8:
        regression_failures.append("mean evidence coverage below 0.80")
    if metrics["hard_blocker_false_positive_apply_rate"] > 0:
        regression_failures.append("hard blocker produced an apply recommendation")
    if metrics["unsupported_claim_count"] > 0:
        regression_failures.append("unsupported claims detected")

    return {
        "schema_version": "1.0",
        "rubric_version": RUBRIC_VERSION,
        "case_count": len(results),
        "metrics": metrics,
        "regression_passed": not regression_failures,
        "regression_failures": regression_failures,
        "results": results,
    }


def run_and_write_evaluation(output_path: str | Path) -> dict[str, Any]:
    report = run_evaluation()
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report


def _metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    correct = sum(
        item["predicted_recommendation"] == item["label"] for item in results
    )
    non_apply = [item for item in results if item["label"] != "apply"]
    false_apply = [
        item
        for item in non_apply
        if item["predicted_recommendation"] == "apply"
    ]
    blocker_cases = [item for item in results if item["hard_blocker_expected"]]
    blocker_false_apply = [
        item
        for item in blocker_cases
        if item["predicted_recommendation"] == "apply"
    ]
    review_cases = [item for item in results if item["expected_review"]]
    review_correct = sum(item["predicted_review"] for item in review_cases)
    labels = Counter(item["label"] for item in results)
    predictions = Counter(item["predicted_recommendation"] for item in results)
    return {
        "recommendation_accuracy": round(correct / total, 4) if total else 0.0,
        "label_distribution": dict(labels),
        "prediction_distribution": dict(predictions),
        "mean_evidence_coverage": round(
            sum(item["evidence_coverage"] for item in results) / total, 4
        )
        if total
        else 0.0,
        "unsupported_claim_count": sum(
            item["unsupported_claims"] for item in results
        ),
        "unsupported_claim_rate": 0.0,
        "false_positive_apply_rate": round(len(false_apply) / len(non_apply), 4)
        if non_apply
        else 0.0,
        "hard_blocker_false_positive_apply_rate": round(
            len(blocker_false_apply) / len(blocker_cases), 4
        )
        if blocker_cases
        else 0.0,
        "human_review_routing_accuracy": round(review_correct / len(review_cases), 4)
        if review_cases
        else 1.0,
    }


def _render_case(case: dict[str, Any]) -> str:
    lines = [
        f"# {case['title']}",
        "",
        f"Company: {case['company']}",
        f"Location: {case['location']}",
        f"Seniority: {case['seniority']}",
        f"Workplace: {case['workplace_type']}",
        f"Domain: {', '.join(case['domain'])}",
        f"Salary: {case['salary_text']}",
    ]
    if case.get("work_authorization_language"):
        lines.append(f"Work authorization: {case['work_authorization_language']}")
    lines.extend(["", "## Responsibilities"])
    lines.extend(f"- {item}" for item in case["responsibilities"])
    lines.extend(["", "## Requirements"])
    lines.extend(f"- {item}" for item in case["must_have"])
    lines.extend(["", "## Nice to have"])
    lines.extend(f"- {item}" for item in case["nice_to_have"])
    return "\n".join(lines) + "\n"
