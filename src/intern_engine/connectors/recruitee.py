"""Recruitee offers API ({slug}.recruitee.com/api/offers/): public, no auth.

Offers include their full description HTML, so sponsorship classification is
free for this source.
"""

from __future__ import annotations

from ..models import Job
from ..net import Net

URL = "https://{slug}.recruitee.com/api/offers/"


def _location(offer: dict) -> str:
    text = (offer.get("location") or "").strip()
    if text:
        return text
    parts = [p for p in (offer.get("city"), offer.get("country")) if p]
    return ", ".join(parts) or "—"


async def fetch(company: dict, net: Net) -> list[Job]:
    slug = company["slug"]
    data = await net.get_json(URL.format(slug=slug))

    jobs = []
    for offer in data.get("offers", []):
        jobs.append(
            Job(
                id=f"recruitee:{slug}:{offer.get('id')}",
                source="recruitee",
                company=company["name"],
                company_slug=slug,
                title=(offer.get("title") or "").strip(),
                location=_location(offer),
                url=offer.get("careers_url") or "",
                posted_at=offer.get("created_at"),
                description=offer.get("description"),
            )
        )
    return jobs
