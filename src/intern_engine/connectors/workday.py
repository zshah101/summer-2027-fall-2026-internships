"""Workday connector (the hard, enterprise tier).

Workday is per-tenant: each company has its own host + site, e.g.
  https://{tenant}.wd5.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs
It's a POST API protected by bot management, so we send browser-like headers and
accept that some tenants (especially from cloud IPs) may refuse — those failures
are isolated per company and never break a run.

Dates are relative text ("Posted 6 Days Ago"); we convert the precise ones to a
real date and leave vague ones ("30+ Days Ago") blank.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import requests

from ..models import Job

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

_DAYS_RE = re.compile(r"(\d+)\s*\+?\s*days?\s+ago", re.I)


def _posted(text: str | None) -> str | None:
    if not text:
        return None
    t = text.lower()
    if "today" in t:
        days = 0
    elif "yesterday" in t:
        days = 1
    else:
        if "30+" in t:
            return None  # too vague to be a real date
        m = _DAYS_RE.search(t)
        if not m:
            return None
        days = int(m.group(1))
        if days >= 30:
            return None
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.strftime("%Y-%m-%dT00:00:00Z")


def fetch(company: dict, session: requests.Session) -> list[Job]:
    tenant = company["slug"]
    wd = company["wd"]
    site = company["site"]
    url = f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
    body = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": "intern"}

    resp = session.post(url, json=body, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    base = f"https://{tenant}.{wd}.myworkdayjobs.com/{site}"
    jobs: list[Job] = []
    for p in data.get("jobPostings", []):
        path = p.get("externalPath") or ""
        jobs.append(
            Job(
                id=f"workday:{tenant}:{path or p.get('title')}",
                source="workday",
                company=company["name"],
                company_slug=tenant,
                title=(p.get("title") or "").strip(),
                location=(p.get("locationsText") or "—").strip() or "—",
                url=(base + path) if path else base,
                posted_at=_posted(p.get("postedOn")),
            )
        )
    return jobs
