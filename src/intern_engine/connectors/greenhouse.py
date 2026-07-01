"""Greenhouse board API: public, no auth.

The list endpoint now exposes `first_published` (a true publish date), so the
biggest source on the list gets real Posted dates. Descriptions are NOT in the
list payload — the enrichment stage fetches those per matched role.
"""

from __future__ import annotations

from ..models import Job
from ..net import Net

URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


async def fetch(company: dict, net: Net) -> list[Job]:
    slug = company["slug"]
    data = await net.get_json(URL.format(slug=slug))

    jobs = []
    for posting in data.get("jobs", []):
        location = posting.get("location") or {}
        name = location.get("name") if isinstance(location, dict) else None
        jobs.append(
            Job(
                id=f"greenhouse:{slug}:{posting.get('id')}",
                source="greenhouse",
                company=company["name"],
                company_slug=slug,
                title=(posting.get("title") or "").strip(),
                location=(name or "").strip() or "—",
                url=posting.get("absolute_url") or "",
                posted_at=posting.get("first_published"),
            )
        )
    return jobs
