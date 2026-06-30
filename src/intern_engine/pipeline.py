"""The Watcher + Spotter: fetch every company concurrently, filter, store.

Flow:
  load companies -> fetch all (in parallel) -> keep tech 2027 internships
  -> upsert into the store (detect new + close gone) -> return stats.

Per-company failures are isolated: one bad endpoint never breaks the whole run.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

import requests

from . import config, filters, paths, store
from .connectors import ashby, greenhouse, lever, smartrecruiters, workday

CONNECTORS = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
    "smartrecruiters": smartrecruiters.fetch,
    "workday": workday.fetch,
}

HEADERS = {"User-Agent": "intern-engine/1.0 (+github.com/intern-engine)"}


def _fetch_one(company: dict):
    """Returns (company, jobs, error). Never raises."""
    session = requests.Session()
    session.headers.update(HEADERS)
    fetch = CONNECTORS.get(company.get("ats"))
    if fetch is None:
        return company, [], f"no connector for ats={company.get('ats')}"
    try:
        return company, fetch(company, session), None
    except Exception as exc:  # noqa: BLE001 - isolate any per-company failure
        return company, [], str(exc)


def run_update() -> tuple[dict, dict]:
    cfg = config.load_config()
    cycles = config.cycles(cfg)
    tech_only = cfg.get("role_scope", "tech") == "tech"
    restrict = config.restrict_region(cfg)
    want_us = config.want_us(cfg)
    want_ca = config.want_canada(cfg)
    max_age = config.max_age_days(cfg)
    cutoff = (
        (datetime.now(timezone.utc) - timedelta(days=max_age)).strftime("%Y-%m-%d")
        if max_age
        else None
    )

    with open(paths.COMPANIES_PATH, encoding="utf-8") as f:
        companies = json.load(f)

    kept = []
    succeeded: set[str] = set()
    errors: list[tuple[str, str]] = []

    with ThreadPoolExecutor(max_workers=12) as pool:
        for company, jobs, error in pool.map(_fetch_one, companies):
            key = f"{company['ats']}:{company['slug']}"
            if error is not None:
                errors.append((key, error))
                continue
            succeeded.add(key)
            for job in jobs:
                if not filters.is_internship(job.title):
                    continue
                if tech_only and not filters.is_tech(job.title):
                    continue
                season = filters.detect_season(job.title, cycles)
                if season is None:  # no explicit year, or a cycle we don't track
                    continue
                if restrict and not filters.region_ok(job.location, want_us, want_ca):
                    continue
                if cutoff and job.posted_at and job.posted_at[:10] < cutoff:
                    continue  # stale / evergreen posting (e.g. a 2016 req)
                job.season = season
                job.category = filters.categorize(job.title)
                kept.append(job)

    existing = store.load(paths.JOBS_PATH)
    new_ids = store.upsert(existing, [asdict(j) for j in kept], succeeded)
    store.save(paths.JOBS_PATH, existing)

    stats = {
        "companies": len(companies),
        "fetched_ok": len(succeeded),
        "fetch_errors": len(errors),
        "matched_internships": len(kept),
        "new_this_run": len(new_ids),
        "total_open": sum(1 for r in existing.values() if r.get("is_open")),
    }
    return stats, existing
