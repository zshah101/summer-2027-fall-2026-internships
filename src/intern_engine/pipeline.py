"""The watcher + spotter.

Fetches every tracked company concurrently (async, with global and per-host
concurrency caps), normalizes results into one shape, keeps the roles that match
the configured scope, de-duplicates across sources, merges them into the store
(detecting what's new and what's closed), and records run metrics.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import statistics
import time
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

import httpx

from . import config, filters, paths, quality, store
from .connectors import (
    amazon,
    ashby,
    greenhouse,
    lever,
    oracle,
    rippling,
    smartrecruiters,
    workday,
)
from .net import HostLimiter, Net

CONNECTORS = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
    "smartrecruiters": smartrecruiters.fetch,
    "workday": workday.fetch,
    "amazon": amazon.fetch,
    "oracle": oracle.fetch,
    "rippling": rippling.fetch,
}

GLOBAL_CONCURRENCY = 32
PER_HOST_CONCURRENCY = 8
USER_AGENT = "intern-engine/2.0 (+github.com/intern-engine)"


def _load_companies() -> list[dict]:
    with open(paths.COMPANIES_PATH, encoding="utf-8") as f:
        return json.load(f)


async def _fetch_one(company: dict, net: Net):
    """Return (company, jobs, error); never raises (failures are isolated)."""
    fetch = CONNECTORS.get(company.get("ats"))
    if fetch is None:
        return company, [], f"no connector for {company.get('ats')}"
    try:
        return company, await fetch(company, net), None
    except Exception as exc:  # noqa: BLE001 — one bad endpoint must not stop the run
        return company, [], f"{type(exc).__name__}: {exc}"


async def _fetch_all(companies: list[dict]):
    limiter = HostLimiter(PER_HOST_CONCURRENCY)
    gate = asyncio.Semaphore(GLOBAL_CONCURRENCY)
    proxy = os.environ.get("WORKDAY_PROXY") or None

    common = dict(
        limits=httpx.Limits(max_connections=64, max_keepalive_connections=32),
        timeout=httpx.Timeout(20.0, connect=10.0),
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    )

    async with httpx.AsyncClient(**common) as client:
        default_net = Net(client, limiter)
        workday_client = httpx.AsyncClient(proxy=proxy, **common) if proxy else None
        workday_net = Net(workday_client, limiter) if workday_client else default_net

        async def worker(company: dict):
            net = workday_net if company.get("ats") in ("workday", "oracle") else default_net
            async with gate:
                return await _fetch_one(company, net)

        try:
            return await asyncio.gather(*(worker(c) for c in companies))
        finally:
            if workday_client is not None:
                await workday_client.aclose()


def _dedup(jobs: list) -> list:
    """Collapse the same role seen more than once (e.g. via two ATS).

    Keyed by company + normalized title; a posting that carries a real date wins
    over one that doesn't.
    """
    jobs = sorted(jobs, key=lambda j: (j.posted_at is None,))
    seen: set[tuple[str, str]] = set()
    unique = []
    for job in jobs:
        key = (job.company.lower().strip(), re.sub(r"[^a-z0-9]+", "", job.title.lower()))
        if key in seen:
            continue
        seen.add(key)
        unique.append(job)
    return unique


def run_update() -> tuple[dict, dict]:
    cfg = config.load_config()
    cycles = config.cycles(cfg)
    tech_only = cfg.get("role_scope", "tech") == "tech"
    restrict = config.restrict_region(cfg)
    include_intl = config.include_international(cfg)
    max_age = config.max_age_days(cfg)
    cutoff = (
        (datetime.now(UTC) - timedelta(days=max_age)).strftime("%Y-%m-%d")
        if max_age else None
    )

    blocklist = quality.load_blocklist()
    allowlist_only = config.allowlist_only(cfg)

    companies = _load_companies()
    started = time.monotonic()
    results = asyncio.run(_fetch_all(companies))

    kept = []
    succeeded: set[str] = set()
    errors = 0
    for company, jobs, error in results:
        if error is not None:
            errors += 1
            continue
        succeeded.add(f"{company['ats']}:{company['slug']}")
        if quality.is_blocked(company["name"], blocklist):
            continue
        if allowlist_only and not quality.is_recognized(company["name"]):
            continue
        for job in jobs:
            if not filters.is_internship(job.title):
                continue
            if tech_only and not filters.is_tech(job.title):
                continue
            season = filters.detect_season(job.title, cycles)
            if season is None:
                continue
            is_us = filters.is_united_states(job.location)
            if restrict and not is_us and not include_intl:
                continue
            loc = (job.location or "").strip()
            if not is_us and (not loc or loc == "—"):
                continue  # international roles need a real location
            posted_day = (job.posted_at or "")[:10]
            if cutoff and posted_day and posted_day < cutoff:
                continue
            job.season = season
            job.category = filters.categorize(job.title)
            kept.append(job)

    kept = _dedup(kept)
    existing = store.load(paths.JOBS_PATH)
    new_ids = store.upsert(existing, [asdict(j) for j in kept], succeeded)
    store.save(paths.JOBS_PATH, existing)

    stats = _build_stats(companies, succeeded, errors, kept, existing, new_ids,
                         round(time.monotonic() - started, 1))
    _write_stats(stats)
    return stats, existing


def _parse_iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _detection_latency(existing: dict, window_days: int = 7) -> dict:
    """Median minutes between a role being published and us first seeing it.

    Only counts roles caught within `window_days` of their posting, so the figure
    reflects real-time detection rather than the one-off backfill of old roles.
    """
    window_minutes = window_days * 24 * 60
    deltas = []
    for record in existing.values():
        posted, seen = record.get("posted_at"), record.get("first_seen_at")
        if not posted or not seen:
            continue
        posted_dt, seen_dt = _parse_iso(posted), _parse_iso(seen)
        if not posted_dt or not seen_dt:
            continue
        minutes = (seen_dt - posted_dt).total_seconds() / 60
        if 0 <= minutes <= window_minutes:
            deltas.append(minutes)
    return {
        "median_minutes": round(statistics.median(deltas), 1) if deltas else None,
        "sample_size": len(deltas),
        "window_days": window_days,
    }


def _build_stats(companies, succeeded, errors, kept, existing, new_ids, duration) -> dict:
    open_records = [r for r in existing.values() if r.get("is_open")]
    return {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_seconds": duration,
        "companies_total": len(companies),
        "companies_by_source": dict(Counter(c["ats"] for c in companies)),
        "fetched_ok": len(succeeded),
        "fetch_errors": errors,
        "fetch_success_rate": round(len(succeeded) / max(len(companies), 1), 3),
        "roles_matched": len(kept),
        "roles_by_source": dict(Counter(j.source for j in kept)),
        "roles_by_cycle": dict(Counter(j.season for j in kept)),
        "roles_by_region": dict(Counter(
            "US" if filters.is_united_states(j.location) else "International" for j in kept
        )),
        "new_this_run": len(new_ids),
        "open_total": len(open_records),
        "detection_latency": _detection_latency(existing),
    }


def _write_stats(stats: dict) -> None:
    with open(paths.STATS_PATH, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
