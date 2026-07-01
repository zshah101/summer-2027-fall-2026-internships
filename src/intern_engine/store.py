"""Persistent job state, stored as a single human-diffable JSON file.

Why JSON and not SQLite for this repo: the file is committed back to the repo by
GitHub Actions each run, so a text file gives clean diffs ("3 jobs added") and
zero binary/database-persistence headaches. The store is a dict keyed by job id.

Lifecycle work that happens here:
  - first-seen tracking: the moment WE first saw a job (powers "🆕" + sorting)
  - open/closed tracking: a job not seen in a successful fetch is marked closed,
    with a closed_at timestamp (powers the "recently closed" section)
  - retention: long-closed records are purged so the file never grows unbounded
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        # sort_keys keeps the file order stable so git diffs stay small.
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)


# Fields we refresh on every run for jobs we've seen before.
# NOTE: posted_at is deliberately NOT here — we freeze the published date the
# first time we see a role so the "Posted" column never shifts on later runs
# (the report behaves like a ladder: old roles sink, new ones land on top).
# sponsorship/salary/enriched_at are handled specially below: a settled verdict
# must never be clobbered by a run that didn't re-enrich.
_REFRESH_FIELDS = (
    "title", "location", "url",
    "season", "category", "company", "source", "company_slug",
)


def upsert(existing: dict, jobs: list[dict], succeeded_keys: set[str],
           enriched_ids: set[str] | None = None) -> list[str]:
    """Merge freshly-fetched jobs into the existing store.

    Returns the list of NEWLY-seen job ids (this is the "Spotter" result).

    `succeeded_keys` is the set of "<source>:<slug>" we fetched successfully this
    run. We only mark a job closed if its company was fetched successfully but
    the job wasn't in the results — so a network blip never wrongly closes jobs.

    `enriched_ids` are jobs whose sponsorship verdict came from posting text
    THIS run; those get an enriched_at stamp so enrichment never repeats.
    """
    ts = now_iso()
    enriched_ids = enriched_ids or set()
    seen_ids: set[str] = set()
    new_ids: list[str] = []

    for job in jobs:
        jid = job["id"]
        seen_ids.add(jid)
        if jid in existing:
            record = existing[jid]
            for key in _REFRESH_FIELDS:
                if key in job:
                    record[key] = job[key]
            # Backfill-only fields: fill blanks, never overwrite real data.
            if not record.get("posted_at") and job.get("posted_at"):
                record["posted_at"] = job["posted_at"]
            if job.get("salary"):
                record["salary"] = job["salary"]
            if job.get("sponsorship", "unknown") != "unknown":
                record["sponsorship"] = job["sponsorship"]
            if record.get("closed_at"):
                del record["closed_at"]  # the role came back
            record["last_seen_at"] = ts
            record["is_open"] = True
        else:
            record = dict(job)
            record["first_seen_at"] = ts
            record["last_seen_at"] = ts
            record["is_open"] = True
            existing[jid] = record
            new_ids.append(jid)
        if jid in enriched_ids:
            existing[jid]["enriched_at"] = ts

    # Close jobs that belong to a successfully-fetched company but didn't appear.
    for jid, record in existing.items():
        company_key = f"{record.get('source')}:{record.get('company_slug')}"
        if company_key in succeeded_keys and jid not in seen_ids and record.get("is_open"):
            record["is_open"] = False
            record["closed_at"] = ts

    return new_ids


def purge(existing: dict, keep_closed_days: int = 60) -> int:
    """Drop records that closed more than `keep_closed_days` ago.

    Keeps the store (and its git diffs) bounded while preserving enough closed
    history for the "recently closed" section and lifetime analytics.
    """
    cutoff = (datetime.now(UTC) - timedelta(days=keep_closed_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale = [
        jid for jid, record in existing.items()
        if not record.get("is_open") and (record.get("closed_at") or record.get("last_seen_at") or "") < cutoff
    ]
    for jid in stale:
        del existing[jid]
    return len(stale)
