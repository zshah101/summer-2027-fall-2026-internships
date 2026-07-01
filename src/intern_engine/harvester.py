"""Discovery: turn a list of candidate company slugs into a validated registry.

There is no master directory of ATS boards, so we DISCOVER by probing: try each
slug against every simple-token ATS and keep the ones that actually return jobs,
recording which ATS each lives on. Results are MERGED into data/companies.json
(never replacing it — the dataset-mined companies stay untouched).

This is how coverage grows by hand: add slugs to data/candidates.json and
re-harvest. Dataset-scale growth lives in discover.py.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import requests

from . import paths

PROBES = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    "lever": "https://api.lever.co/v0/postings/{slug}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{slug}",
    "smartrecruiters": "https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=1",
    "rippling": "https://api.rippling.com/platform/api/ats/v1/board/{slug}/jobs",
    "recruitee": "https://{slug}.recruitee.com/api/offers/",
    "breezy": "https://{slug}.breezy.hr/json",
}

HEADERS = {"User-Agent": "intern-engine/3.0 (+github.com/intern-engine)"}


def _count(ats: str, payload) -> int:
    if ats in ("lever", "rippling", "breezy"):
        return len(payload) if isinstance(payload, list) else 0
    if ats == "smartrecruiters":
        if isinstance(payload, dict):
            return payload.get("totalFound", len(payload.get("content", [])))
        return 0
    if ats == "recruitee":
        return len(payload.get("offers", [])) if isinstance(payload, dict) else 0
    return len(payload.get("jobs", [])) if isinstance(payload, dict) else 0


def detect(candidate: dict, session: requests.Session) -> dict | None:
    slug = candidate["slug"]
    for ats, template in PROBES.items():
        try:
            resp = session.get(template.format(slug=slug), timeout=12)
            if resp.status_code == 200 and _count(ats, resp.json()) > 0:
                return {"name": candidate["name"], "slug": slug, "ats": ats}
        except (requests.RequestException, ValueError):
            continue
    return None


def harvest() -> tuple[list[dict], list[dict]]:
    with open(paths.CANDIDATES_PATH, encoding="utf-8") as f:
        candidates = json.load(f)

    session = requests.Session()
    session.headers.update(HEADERS)

    found: list[dict] = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        for result in pool.map(lambda c: detect(c, session), candidates):
            if result:
                found.append(result)

    # Merge into the existing registry — a probe run must never wipe out the
    # thousands of companies that dataset discovery already validated.
    merged: dict[tuple[str, str], dict] = {}
    try:
        with open(paths.COMPANIES_PATH, encoding="utf-8") as f:
            for c in json.load(f):
                merged[(c["ats"], c["slug"])] = c
    except (OSError, json.JSONDecodeError, KeyError):
        pass
    for c in found:
        merged.setdefault((c["ats"], c["slug"]), c)

    companies = sorted(merged.values(), key=lambda c: c["name"].lower())
    with open(paths.COMPANIES_PATH, "w", encoding="utf-8") as f:
        json.dump(companies, f, indent=2, ensure_ascii=False)

    return found, candidates
