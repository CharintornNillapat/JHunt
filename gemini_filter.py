# gemini_filter.py
"""
Optional semantic relevance pass over jobs that survived the cheap filters.

The substring filters in state_manager can only match text. They keep a sales
role whose ad happens to mention "Python", and they cannot tell a graduate
backend role from one demanding eight years' experience. This module asks Gemini
Flash to make that call.

Every failure path returns the input list unchanged. A filter that is wrong
about a job costs the user one alert; a filter that crashes costs them all of
them, so this one never raises.
"""
import json
import time

import requests

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-2.5-flash"

# Free tier is roughly 10 requests/minute. One request per 40 jobs with a 7s
# gap keeps a normal run to a couple of requests, far inside the quota.
BATCH_SIZE = 40
BATCH_DELAY = 7.0
TIMEOUT = 60

# Below this the job is dropped. Deliberately permissive — a false positive
# costs one noisy alert, a false negative costs a real opportunity.
KEEP_THRESHOLD = 4

PROMPT = """You are screening job ads for a junior/entry-level software engineer in Thailand.

KEEP a job when it is a genuine engineering role in one of these areas, open to \
someone early in their career (0-3 years):
- Python development (backend, scripting, automation)
- Backend / full-stack engineering
- Data engineering, data analysis, data science
- Computer vision, machine learning, AI engineering

DROP a job when:
- It is not an engineering role — sales, marketing, admin, HR, recruitment, \
customer support, teaching — even if the ad mentions Python, data or AI in passing.
- It requires substantial seniority: team lead, manager, architect, head of, \
or an explicit demand for 5+ years of experience.
- It is unrelated technical work with no programming, e.g. hardware repair, \
IT helpdesk, network administration, QA manual testing.

For each job return:
- index: the job's index, exactly as given
- keep: true if it passes the rules above
- score: 0-10 confidence that this suits a junior software engineer
- reason: at most 15 words explaining the decision

Return one entry for every job. Do not omit any.

Jobs:
"""

RESPONSE_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "index": {"type": "INTEGER"},
            "keep": {"type": "BOOLEAN"},
            "score": {"type": "INTEGER"},
            "reason": {"type": "STRING"},
        },
        "required": ["index", "keep", "score", "reason"],
    },
}


def _job_payload(index: int, job: dict) -> dict:
    """The minimum the model needs to judge a job. Keeps tokens (and cost) down."""
    return {
        "index": index,
        "title": job.get("title", ""),
        "company": job.get("company", ""),
        "teaser": (job.get("teaser") or "")[:400],
        "bullet_points": (job.get("bullet_points") or [])[:4],
    }


def _call_gemini(batch: list[dict], model: str, api_key: str) -> list[dict] | None:
    """
    Scores one batch. Returns the parsed verdicts, or None if anything went wrong.

    None means "could not judge" and is always treated as keep-everything by the
    caller — never as "drop everything".
    """
    body = {
        "contents": [{
            "parts": [{"text": PROMPT + json.dumps(batch, ensure_ascii=False, indent=1)}]
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
            "temperature": 0,
        },
    }

    try:
        response = requests.post(
            API_URL.format(model=model),
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json=body,
            timeout=TIMEOUT,
        )
    except requests.exceptions.RequestException as e:
        print(f"[Gemini] Request failed: {e}")
        return None

    if not response.ok:
        detail = ""
        try:
            detail = (response.json().get("error") or {}).get("message", "")
        except ValueError:
            detail = response.text[:200]
        print(f"[Gemini] HTTP {response.status_code}: {detail}")
        return None

    try:
        payload = response.json()
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
        verdicts = json.loads(text)
    except (ValueError, KeyError, IndexError, TypeError) as e:
        print(f"[Gemini] Could not parse response: {e}")
        return None

    if not isinstance(verdicts, list):
        print(f"[Gemini] Expected a list of verdicts, got {type(verdicts).__name__}")
        return None

    return verdicts


def filter_semantically(jobs: list[dict], config: dict) -> list[dict]:
    """
    Drops jobs the model judges irrelevant to a junior software engineer.

    Fail-open by contract: disabled, unconfigured, or broken all return `jobs`
    exactly as received.
    """
    if not config.get("gemini_enabled", False):
        return jobs

    if not jobs:
        return jobs

    api_key = config.get("gemini_api_key")
    if not api_key:
        print("[Gemini] GEMINI_API_KEY is not set — skipping semantic filter "
              "(all jobs kept).")
        return jobs

    model = config.get("gemini_model") or DEFAULT_MODEL

    # Start from "keep everything". Only an explicit, well-formed verdict can
    # remove a job, so any gap in the model's response fails open per-job.
    keep_flags: dict[int, bool] = {i: True for i in range(len(jobs))}
    judged = 0

    batches = [jobs[i:i + BATCH_SIZE] for i in range(0, len(jobs), BATCH_SIZE)]
    print(f"[Gemini] Scoring {len(jobs)} job(s) with {model} "
          f"in {len(batches)} batch(es)...")

    for batch_num, batch in enumerate(batches):
        offset = batch_num * BATCH_SIZE
        if batch_num > 0:
            time.sleep(BATCH_DELAY)

        payload = [_job_payload(offset + i, job) for i, job in enumerate(batch)]
        verdicts = _call_gemini(payload, model, api_key)

        if verdicts is None:
            print(f"[Gemini] Batch {batch_num + 1}/{len(batches)} failed — "
                  "keeping all jobs in it.")
            continue

        for verdict in verdicts:
            if not isinstance(verdict, dict):
                continue
            try:
                index = int(verdict["index"])
            except (KeyError, TypeError, ValueError):
                continue
            if not (offset <= index < offset + len(batch)):
                continue  # model invented an index; ignore it

            score = verdict.get("score")
            try:
                score = int(score)
            except (TypeError, ValueError):
                score = KEEP_THRESHOLD  # unscored -> benefit of the doubt

            keep = bool(verdict.get("keep", True)) and score >= KEEP_THRESHOLD
            keep_flags[index] = keep
            judged += 1

            if not keep:
                reason = str(verdict.get("reason", "")).strip() or "no reason given"
                print(f"[Gemini] Excluded (score {score}): "
                      f"{jobs[index].get('title', '?')} — {reason}")

    kept = [job for i, job in enumerate(jobs) if keep_flags[i]]
    unjudged = len(jobs) - judged
    if unjudged:
        print(f"[Gemini] {unjudged} job(s) were not judged — kept by default.")
    print(f"[Gemini] Kept {len(kept)}/{len(jobs)} job(s).")
    return kept
