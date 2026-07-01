"""SmartRecruiters postings API: public, no auth.

We pass ?q=intern so the server pre-filters to internship-ish roles, and read
`releasedDate` for an accurate posting date. Company identifiers are
case-sensitive, so the discovery layer preserves their case. Paginated by
offset for the enterprise tenants that post 100+ intern reqs.
"""

from __future__ import annotations

from ..models import Job
from ..net import Net

URL = "https://api.smartrecruiters.com/v1/companies/{slug}/postings"

_PAGE_SIZE = 100
_MAX_JOBS = 300

_COUNTRY = {
    "us": "United States", "ca": "Canada", "gb": "United Kingdom",
    "in": "India", "de": "Germany", "ie": "Ireland", "au": "Australia",
}


def _location(loc) -> str:
    if not isinstance(loc, dict):
        return "—"
    country = _COUNTRY.get((loc.get("country") or "").lower(), (loc.get("country") or "").upper())
    text = ", ".join(p for p in (loc.get("city"), loc.get("region"), country) if p)
    if loc.get("remote"):
        text = f"{text} (Remote)" if text else "Remote"
    return text or "—"


async def fetch(company: dict, net: Net) -> list[Job]:
    slug = company["slug"]

    jobs: list[Job] = []
    for offset in range(0, _MAX_JOBS, _PAGE_SIZE):
        params = {"limit": _PAGE_SIZE, "offset": offset, "q": "intern"}
        data = await net.get_json(URL.format(slug=slug), params=params)
        postings = data.get("content", [])
        for posting in postings:
            pid = posting.get("id")
            jobs.append(
                Job(
                    id=f"smartrecruiters:{slug}:{pid}",
                    source="smartrecruiters",
                    company=company["name"],
                    company_slug=slug,
                    title=(posting.get("name") or "").strip(),
                    location=_location(posting.get("location")),
                    url=f"https://jobs.smartrecruiters.com/{slug}/{pid}",
                    posted_at=posting.get("releasedDate"),
                )
            )
        if len(postings) < _PAGE_SIZE:
            break
    return jobs
