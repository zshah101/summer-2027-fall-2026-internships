"""Amazon Jobs search API: public JSON, one fixed endpoint (not per-tenant).

The search payload includes each job's description and qualifications, so
sponsorship classification needs no extra requests.
"""

from __future__ import annotations

from datetime import datetime

from ..models import Job
from ..net import Net

URL = "https://www.amazon.jobs/en/search.json"


def _posted(text: str | None) -> str | None:
    if not text:
        return None
    for fmt in ("%B %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text.strip(), fmt).strftime("%Y-%m-%dT00:00:00Z")
        except ValueError:
            continue
    return None


async def fetch(company: dict, net: Net) -> list[Job]:
    jobs: list[Job] = []
    for offset in (0, 100, 200):
        params = {"base_query": "intern", "result_limit": 100, "offset": offset, "sort": "recent"}
        data = await net.get_json(URL, params=params)
        results = data.get("jobs", [])
        for j in results:
            path = j.get("job_path") or ""
            description = " ".join(
                str(j.get(k) or "")
                for k in ("description", "basic_qualifications", "preferred_qualifications")
            )
            jobs.append(
                Job(
                    id=f"amazon:amazon:{j.get('id_icims') or path}",
                    source="amazon",
                    company="Amazon",
                    company_slug="amazon",
                    title=(j.get("title") or "").strip(),
                    location=(j.get("normalized_location") or j.get("location") or "—").strip() or "—",
                    url=("https://www.amazon.jobs" + path) if path else "https://www.amazon.jobs",
                    posted_at=_posted(j.get("posted_date")),
                    description=description.strip() or None,
                )
            )
        if len(results) < 100:
            break
    return jobs
