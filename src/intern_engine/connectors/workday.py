"""Workday (enterprise tier) — the biggest ATS in intern hiring.

Per-tenant POST API behind bot management. Two public URL shapes exist and we
support both:
  subdomain:  https://{tenant}.{wd}.myworkdayjobs.com/{site}
  path-style: https://{wd}.myworkdaysite.com/recruiting/{tenant}/{site}
The CXS JSON API lives under /wday/cxs/{tenant}/{site} on either host.

The API caps each page at 20 postings, so we paginate — big tech tenants list
far more than 20 intern roles at peak season. Dates are relative text
("Posted 6 Days Ago"); we resolve precise ones here and the enrichment stage
backfills exact dates from the job detail endpoint.

Cloud IPs are blocked more than home IPs, so the pipeline routes this connector
through an optional proxy (WORKDAY_PROXY) when one is configured.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from ..models import Job
from ..net import Net

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json",
}

_DAYS_AGO = re.compile(r"(\d+)\s*\+?\s*days?\s+ago", re.IGNORECASE)

_PAGE_SIZE = 20   # hard server-side cap per request
_MAX_JOBS = 100   # intern-search results beyond this are noise


def _resolve_posted(text: str | None) -> str | None:
    if not text:
        return None
    lowered = text.lower()
    if "today" in lowered:
        days = 0
    elif "yesterday" in lowered:
        days = 1
    elif "30+" in lowered:
        return None  # too vague to be a real date
    else:
        match = _DAYS_AGO.search(lowered)
        if not match or int(match.group(1)) >= 30:
            return None
        days = int(match.group(1))
    return (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")


def _urls(company: dict) -> tuple[str, str]:
    """(cxs jobs endpoint, public base URL) for either Workday host shape."""
    tenant, site = company["slug"], company["site"]
    host = company.get("host")  # set for path-style tenants by discovery
    if host:
        return (
            f"https://{host}/wday/cxs/{tenant}/{site}/jobs",
            f"https://{host}/recruiting/{tenant}/{site}",
        )
    sub_host = f"{tenant}.{company['wd']}.myworkdayjobs.com"
    return (
        f"https://{sub_host}/wday/cxs/{tenant}/{site}/jobs",
        f"https://{sub_host}/{site}",
    )


async def fetch(company: dict, net: Net) -> list[Job]:
    tenant = company["slug"]
    api_url, base = _urls(company)

    jobs: list[Job] = []
    for offset in range(0, _MAX_JOBS, _PAGE_SIZE):
        body = {"appliedFacets": {}, "limit": _PAGE_SIZE, "offset": offset, "searchText": "intern"}
        data = await net.post_json(api_url, json=body, headers=HEADERS)
        postings = data.get("jobPostings", [])
        for posting in postings:
            path = posting.get("externalPath") or ""
            jobs.append(
                Job(
                    id=f"workday:{tenant}:{path or posting.get('title')}",
                    source="workday",
                    company=company["name"],
                    company_slug=tenant,
                    title=(posting.get("title") or "").strip(),
                    location=(posting.get("locationsText") or "—").strip() or "—",
                    url=(base + path) if path else base,
                    posted_at=_resolve_posted(posting.get("postedOn")),
                )
            )
        if len(postings) < _PAGE_SIZE:
            break
    return jobs
