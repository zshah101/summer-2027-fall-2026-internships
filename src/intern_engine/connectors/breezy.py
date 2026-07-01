"""Breezy HR board API ({slug}.breezy.hr/json): public JSON list, no auth.

Small-company ATS; the list includes real publish dates and salary text.
"""

from __future__ import annotations

from ..models import Job
from ..net import Net

URL = "https://{slug}.breezy.hr/json"


def _location(p: dict) -> str:
    loc = p.get("location")
    if isinstance(loc, dict):
        return (loc.get("name") or "").strip() or "—"
    return (str(loc).strip() or "—") if loc else "—"


async def fetch(company: dict, net: Net) -> list[Job]:
    slug = company["slug"]
    postings = await net.get_json(URL.format(slug=slug))
    if not isinstance(postings, list):
        return []

    jobs = []
    for p in postings:
        salary = (p.get("salary") or "").strip() if isinstance(p.get("salary"), str) else None
        jobs.append(
            Job(
                id=f"breezy:{slug}:{p.get('id')}",
                source="breezy",
                company=company["name"],
                company_slug=slug,
                title=(p.get("name") or "").strip(),
                location=_location(p),
                url=p.get("url") or "",
                posted_at=p.get("published_date"),
                salary=salary or None,
            )
        )
    return jobs
