"""Per-company circuit breaker: stop hammering boards that keep failing.

Public datasets inevitably contain renamed slugs and retired boards. Without a
breaker every dead endpoint costs retries on every run, forever. Instead we
track consecutive failures per company and quarantine repeat offenders with an
exponential backoff window:

    3 fails -> skip for 6h, 4 -> 12h, 5 -> 24h, 6 -> 48h, 7+ -> 72h (cap)

A quarantined company is still retried once its window expires, so boards that
come back (rate-limit storms, Workday bot walls) recover on their own — and one
success resets the count to zero. State lives in data/health.json, committed by
CI, so the breaker's decisions are auditable in git history like everything else.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta

from . import paths

_THRESHOLD = 3          # consecutive failures before quarantine kicks in
_BASE_HOURS = 6         # first quarantine window
_CAP_HOURS = 72         # never back off longer than this — boards do come back


def key(company: dict) -> str:
    return f"{company.get('ats')}:{company.get('slug')}"


def load() -> dict:
    try:
        with open(paths.HEALTH_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save(data: dict) -> None:
    os.makedirs(os.path.dirname(paths.HEALTH_PATH), exist_ok=True)
    with open(paths.HEALTH_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)


def _window_hours(failures: int) -> float:
    return min(_BASE_HOURS * 2 ** (failures - _THRESHOLD), _CAP_HOURS)


def is_quarantined(entry: dict | None, now: datetime) -> bool:
    if not entry:
        return False
    failures = entry.get("consecutive_failures", 0)
    if failures < _THRESHOLD:
        return False
    last = entry.get("last_attempt_at")
    if not last:
        return False
    try:
        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
    except ValueError:
        return False
    return now < last_dt + timedelta(hours=_window_hours(failures))


def partition(companies: list[dict], data: dict, now: datetime | None = None) -> tuple[list[dict], list[dict]]:
    """Split into (companies to fetch, companies sitting out this run)."""
    now = now or datetime.now(UTC)
    active, benched = [], []
    for company in companies:
        (benched if is_quarantined(data.get(key(company)), now) else active).append(company)
    return active, benched


def record(data: dict, company: dict, error: str | None, now: datetime | None = None) -> None:
    """Update one company's entry after a fetch attempt."""
    now = now or datetime.now(UTC)
    ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    k = key(company)
    entry = data.get(k) or {}
    entry["last_attempt_at"] = ts
    if error is None:
        # Recovered or healthy: drop the entry entirely to keep the file small.
        data.pop(k, None)
    else:
        entry["consecutive_failures"] = entry.get("consecutive_failures", 0) + 1
        entry["last_error"] = error[:200]
        data[k] = entry
