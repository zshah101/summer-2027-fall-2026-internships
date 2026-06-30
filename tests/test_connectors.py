"""Connector parsing tests using mocked ATS responses (no network).

Each connector is fed a canned payload through a fake Net, so we verify the
schema-to-Job mapping for every source without hitting the internet.
"""

import asyncio

from intern_engine.connectors import (
    amazon,
    ashby,
    greenhouse,
    lever,
    oracle,
    rippling,
    smartrecruiters,
    workday,
)


class FakeNet:
    """Stands in for net.Net: returns a preset payload for any request."""

    def __init__(self, payload):
        self.payload = payload

    async def get_json(self, url, **kwargs):
        return self.payload

    async def post_json(self, url, **kwargs):
        return self.payload


def _run(coro):
    return asyncio.run(coro)


def test_greenhouse():
    payload = {"jobs": [{
        "id": 42, "title": "Software Engineer Intern",
        "location": {"name": "New York, NY"}, "absolute_url": "https://gh/42",
        "updated_at": "2026-06-01T00:00:00Z",
    }]}
    jobs = _run(greenhouse.fetch({"name": "Acme", "slug": "acme"}, FakeNet(payload)))
    assert len(jobs) == 1
    j = jobs[0]
    assert j.id == "greenhouse:acme:42"
    assert j.title == "Software Engineer Intern"
    assert j.location == "New York, NY"
    assert j.url == "https://gh/42"
    assert j.posted_at is None  # Greenhouse exposes no real publish date


def test_lever():
    payload = [{
        "id": "abc", "text": "SWE Intern",
        "categories": {"location": "San Francisco"},
        "hostedUrl": "https://lever/abc", "createdAt": 1717200000000,
    }]
    jobs = _run(lever.fetch({"name": "Acme", "slug": "acme"}, FakeNet(payload)))
    assert jobs[0].id == "lever:acme:abc"
    assert jobs[0].location == "San Francisco"
    assert jobs[0].posted_at and jobs[0].posted_at.startswith("2024")


def test_ashby_skips_unlisted():
    payload = {"jobs": [
        {"title": "SWE Intern", "location": "SF", "jobUrl": "https://ashby/x/uuid1",
         "publishedAt": "2026-06-01T00:00:00Z", "isListed": True},
        {"title": "Hidden", "jobUrl": "https://ashby/x/uuid2", "isListed": False},
    ]}
    jobs = _run(ashby.fetch({"name": "Acme", "slug": "x"}, FakeNet(payload)))
    assert len(jobs) == 1
    assert jobs[0].id == "ashby:x:uuid1"
    assert jobs[0].posted_at == "2026-06-01T00:00:00Z"


def test_smartrecruiters():
    payload = {"content": [{
        "id": "p1", "name": "Data Science Intern",
        "location": {"city": "Austin", "region": "TX", "country": "us"},
        "releasedDate": "2026-06-10T00:00:00Z",
    }]}
    jobs = _run(smartrecruiters.fetch({"name": "Acme", "slug": "Acme"}, FakeNet(payload)))
    assert jobs[0].id == "smartrecruiters:Acme:p1"
    assert "United States" in jobs[0].location
    assert jobs[0].posted_at == "2026-06-10T00:00:00Z"


def test_amazon():
    payload = {"jobs": [{
        "title": "SDE Intern", "job_path": "/en/jobs/1/sde",
        "normalized_location": "Seattle, Washington, USA",
        "posted_date": "June 1, 2026", "id_icims": "1",
    }]}
    jobs = _run(amazon.fetch({"name": "Amazon", "slug": "amazon"}, FakeNet(payload)))
    assert jobs[0].url == "https://www.amazon.jobs/en/jobs/1/sde"
    assert jobs[0].posted_at.startswith("2026-06-01")


def test_rippling():
    payload = [{
        "uuid": "u1", "name": "Backend Intern",
        "workLocation": {"label": "Remote, US"}, "url": "https://ats.rippling.com/x/jobs/u1",
    }]
    jobs = _run(rippling.fetch({"name": "Acme", "slug": "x"}, FakeNet(payload)))
    assert jobs[0].id == "rippling:x:u1"
    assert jobs[0].location == "Remote, US"


def test_workday_relative_dates():
    payload = {"jobPostings": [
        {"title": "SWE Intern", "externalPath": "/job/1", "locationsText": "Austin, TX",
         "postedOn": "Posted 3 Days Ago"},
        {"title": "Old Intern", "externalPath": "/job/2", "locationsText": "NY",
         "postedOn": "Posted 30+ Days Ago"},
    ]}
    company = {"name": "Acme", "slug": "acme", "wd": "wd5", "site": "Careers"}
    jobs = _run(workday.fetch(company, FakeNet(payload)))
    assert jobs[0].posted_at is not None        # "3 Days Ago" resolves to a date
    assert jobs[1].posted_at is None            # "30+ Days Ago" is too vague
    assert jobs[0].url.endswith("/Careers/job/1")


def test_oracle():
    payload = {"items": [{"requisitionList": [
        {"Id": "9", "Title": "ML Intern", "PrimaryLocation": "Dearborn, MI",
         "PostedDate": "2026-06-05"},
    ]}]}
    company = {"name": "Ford", "slug": "ford", "host": "x.oraclecloud.com", "site": "CX_1"}
    jobs = _run(oracle.fetch(company, FakeNet(payload)))
    assert jobs[0].id == "oracle:ford:9"
    assert jobs[0].posted_at == "2026-06-05"
