"""Oracle Recruiting Cloud (enterprise + bank tenants).

Per-tenant like Workday: each company has its own oraclecloud.com host and a
site number (CX_1, CX_2001, ... — captured by discovery, not assumed). Public
REST endpoint, browser-like headers, paginated by offset.
"""

from __future__ import annotations

from ..models import Job
from ..net import Net

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json",
}

_PAGE_SIZE = 50
_MAX_JOBS = 100


def _posted(value) -> str | None:
    # Keep only real ISO-ish dates (YYYY-MM-...), ignore anything else.
    if isinstance(value, str) and len(value) >= 7 and value[:4].isdigit() and value[4] == "-":
        return value
    return None


async def fetch(company: dict, net: Net) -> list[Job]:
    host = company["host"]
    site = company.get("site", "CX_1")
    tenant = company["slug"]
    url = f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
    base = f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job"

    jobs: list[Job] = []
    for offset in range(0, _MAX_JOBS, _PAGE_SIZE):
        params = {
            "onlyData": "true",
            "expand": "requisitionList.secondaryLocations",
            "finder": f"findReqs;siteNumber={site},keyword=intern,sortBy=POSTING_DATES_DESC,offset={offset}",
            "limit": str(_PAGE_SIZE),
        }
        data = await net.get_json(url, params=params, headers=HEADERS)
        items = data.get("items") or []
        requisitions = items[0].get("requisitionList", []) if items else []
        for r in requisitions:
            rid = r.get("Id")
            jobs.append(
                Job(
                    id=f"oracle:{tenant}:{rid}",
                    source="oracle",
                    company=company["name"],
                    company_slug=tenant,
                    title=(r.get("Title") or "").strip(),
                    location=(r.get("PrimaryLocation") or "—").strip() or "—",
                    url=f"{base}/{rid}",
                    posted_at=_posted(r.get("PostedDate")),
                )
            )
        if len(requisitions) < _PAGE_SIZE:
            break
    return jobs
