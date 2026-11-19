# Five-minute demo

## 0:00–0:40 — Frame the problem

Open with:

> This is not an auto-apply bot. It is a controlled research agent that turns
> a profile and local job descriptions into evidence-backed recommendations.
> DeepAgents plans and coordinates extraction; deterministic Python validates
> evidence and owns the score.

Point to the architecture diagram in the README.

## 0:40–1:20 — Show the offline contract

```bash
python -m job_fit demo --offline
```

Expected summary:

- Senior AI Platform Engineer: `apply`, score `100`, no review.
- Applied AI Engineer: `investigate`, score `66`, work-authorization review.
- Embedded Software Engineer: `skip`, score `30`, hard-blocker review.

Explain that offline mode uses synthetic fixtures and requires no API key.

## 1:20–2:20 — Inspect the strong match

```bash
sed -n '1,140p' reports/demo/ranked_jobs.md
```

Call out:

- fixed score components that sum to the final score;
- exact quoted requirements with line numbers;
- strengths and gaps tied to the profile;
- resume guidance limited to verified profile claims.

## 2:20–3:10 — Show the safety boundary

Open the blocked assessment:

```bash
python -m json.tool reports/demo/assessment_job_003_blocked.json | less
```

Call out the sponsorship, citizenship, and security-clearance blockers. Explain
that high-impact results are capped and routed to human review; the system never
applies automatically.

## 3:10–4:00 — Show the audit trail

```bash
python -m json.tool reports/demo/run_manifest.json | less
```

Highlight:

- input SHA-256 fingerprints;
- mode and model name;
- DeepAgents/rubric/prompt versions;
- tool events and validation outcomes;
- limitations and review reasons.

## 4:00–4:40 — Run the regression corpus

```bash
python -m job_fit eval --output reports/eval_report.json
```

Explain the gate: a hard-blocker `apply`, low evidence coverage, or unsupported
claim fails the run. The current synthetic corpus has 15 labeled cases.

## 4:40–5:00 — Describe live mode

```bash
export OPENAI_API_KEY="..."
export MODEL_NAME="gpt-4.1-mini"
python -m job_fit demo --live
```

Close with the boundary:

- the real `create_deep_agent` assembly is used in live mode;
- model output must pass deterministic validation;
- invalid model output falls back to deterministic extraction and is marked for
  review;
- this is an independent prototype, not production software.

