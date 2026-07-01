"""Lever postings API: public, no auth. Returns a bare JSON list.

The list payload already carries the full posting text (description + lists +
additional) and a structured salary range, so sponsorship classification and
pay info cost zero extra requests here.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ..models import Job
from ..net import Net

URL = "https://api.lever.co/v0/postings/{slug}?mode=json"


def _epoch_ms_to_iso(ms) -> str | None:
    if not ms:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, tz=UTC).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    except (ValueError, OSError, TypeError):
        return None


def _description(posting: dict) -> str:
    """All the text an applicant would read, flattened for classification."""
    parts = [posting.get("descriptionPlain") or "", posting.get("additionalPlain") or ""]
    for block in posting.get("lists") or []:
        if isinstance(block, dict):
            parts.append(f"{block.get('text') or ''} {block.get('content') or ''}")
    return " ".join(p for p in parts if p)


def _salary(posting: dict) -> str | None:
    rng = posting.get("salaryRange")
    if isinstance(rng, dict) and rng.get("min") and rng.get("max"):
        currency = rng.get("currency") or "USD"
        interval = (rng.get("interval") or "").replace("-", " ").lower()
        text = f"{int(rng['min']):,}–{int(rng['max']):,} {currency}"
        return f"{text} / {interval}" if interval else text
    return None


async def fetch(company: dict, net: Net) -> list[Job]:
    slug = company["slug"]
    postings = await net.get_json(URL.format(slug=slug))

    jobs = []
    for posting in postings:
        categories = posting.get("categories") or {}
        jobs.append(
            Job(
                id=f"lever:{slug}:{posting.get('id')}",
                source="lever",
                company=company["name"],
                company_slug=slug,
                title=(posting.get("text") or "").strip(),
                location=(categories.get("location") or "—").strip() or "—",
                url=posting.get("hostedUrl") or posting.get("applyUrl") or "",
                posted_at=_epoch_ms_to_iso(posting.get("createdAt")),
                salary=_salary(posting),
                description=_description(posting) or None,
            )
        )
    return jobs
