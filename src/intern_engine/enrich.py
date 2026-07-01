"""Enrichment: attach posting text to matched roles and classify sponsorship.

Cost model: this runs ONLY on roles that already passed every filter (a handful
per run, not thousands). Lever/Ashby/Amazon/Recruitee ship descriptions in their
list payloads, so those classify for free; Greenhouse/SmartRecruiters/Workday/
Oracle need one detail request per NEW role, after which the verdict is stored
and never re-fetched. Workday details also carry the exact posting date, which
backfills rows the list API only described as "N days ago".
"""

from __future__ import annotations

import asyncio
import re

from . import sponsorship
from .models import Job
from .net import Net

_CONCURRENCY = 8

_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "application/json",
}

# Both public Workday URL shapes, mapped back to the CXS detail endpoint.
_WD_SUB_RE = re.compile(
    r"https://([\w-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([\w%-]+)(/job/.+)", re.I
)
_WD_SITE_RE = re.compile(
    r"https://(wd\d+\.myworkdaysite\.com)/recruiting/([\w-]+)/([\w%-]+)(/job/.+)", re.I
)
_ORACLE_RE = re.compile(r"https://([\w.-]+\.oraclecloud\.com)/.+/sites/([\w]+)/job/(\d+)", re.I)


async def _greenhouse(job: Job, net: Net) -> str | None:
    external_id = job.id.rsplit(":", 1)[-1]
    url = f"https://boards-api.greenhouse.io/v1/boards/{job.company_slug}/jobs/{external_id}"
    data = await net.get_json(url)
    return data.get("content")


async def _smartrecruiters(job: Job, net: Net) -> str | None:
    external_id = job.id.rsplit(":", 1)[-1]
    url = f"https://api.smartrecruiters.com/v1/companies/{job.company_slug}/postings/{external_id}"
    data = await net.get_json(url)
    sections = ((data.get("jobAd") or {}).get("sections") or {})
    return " ".join(
        str((sections.get(k) or {}).get("text") or "")
        for k in ("jobDescription", "qualifications", "additionalInformation")
    )


async def _workday(job: Job, net: Net) -> str | None:
    m = _WD_SUB_RE.match(job.url)
    if m:
        tenant, wd, site, path = m.groups()
        host = f"{tenant}.{wd}.myworkdayjobs.com"
    else:
        m = _WD_SITE_RE.match(job.url)
        if not m:
            return None
        host, tenant, site, path = m.groups()
    data = await net.get_json(
        f"https://{host}/wday/cxs/{tenant}/{site}{path}", headers=_BROWSER_HEADERS
    )
    info = data.get("jobPostingInfo") or {}
    # The detail API knows the exact go-live date; the list API only said
    # "N days ago". Backfill so more rows get a real Posted date.
    start = info.get("startDate")
    if not job.posted_at and isinstance(start, str) and len(start) == 10:
        job.posted_at = f"{start}T00:00:00Z"
    return info.get("jobDescription")


async def _oracle(job: Job, net: Net) -> str | None:
    m = _ORACLE_RE.match(job.url)
    if not m:
        return None
    host, site, req_id = m.groups()
    url = f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails"
    params = {
        "onlyData": "true",
        "expand": "all",
        "finder": f'ById;Id="{req_id}",siteNumber={site}',
    }
    data = await net.get_json(url, params=params, headers=_BROWSER_HEADERS)
    items = data.get("items") or []
    if not items:
        return None
    return " ".join(
        str(items[0].get(k) or "")
        for k in ("ExternalDescriptionStr", "ExternalQualificationsStr", "CorporateDescriptionStr")
    )


async def _workable(job: Job, net: Net) -> str | None:
    shortcode = job.id.rsplit(":", 1)[-1]
    url = f"https://apply.workable.com/api/v2/accounts/{job.company_slug}/jobs/{shortcode}"
    data = await net.get_json(url)
    return " ".join(str(data.get(k) or "") for k in ("description", "requirements", "benefits"))


_FETCHERS = {
    "greenhouse": _greenhouse,
    "smartrecruiters": _smartrecruiters,
    "workday": _workday,
    "oracle": _oracle,
    "workable": _workable,
}


async def enrich_jobs(jobs: list[Job], existing: dict, net: Net) -> tuple[set[str], int]:
    """Classify sponsorship for every kept job, fetching text only when needed.

    Returns (ids classified from fresh text this run, detail requests made).
    Jobs whose stored record already carries a verdict inherit it without any
    network traffic — enrichment is a one-time cost per role.
    """
    gate = asyncio.Semaphore(_CONCURRENCY)
    fetched = 0

    async def _resolve(job: Job) -> str | None:
        nonlocal fetched
        prior = existing.get(job.id) or {}
        if prior.get("enriched_at") or prior.get("sponsorship", "unknown") != "unknown":
            job.sponsorship = prior.get("sponsorship", "unknown")
            return None  # already settled on an earlier run
        if job.description is None:
            fetcher = _FETCHERS.get(job.source)
            if fetcher is not None:
                try:
                    async with gate:
                        job.description = await fetcher(job, net)
                    fetched += 1
                except Exception:  # noqa: BLE001 — a dead detail page must not kill the run
                    return None  # no enriched_at -> retried on the next run
        job.sponsorship = sponsorship.classify(job.description)
        return job.id

    done = await asyncio.gather(*(_resolve(j) for j in jobs))
    return {jid for jid in done if jid}, fetched
