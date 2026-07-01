"""Connector parsing tests using mocked ATS responses (no network).

Each connector is fed a canned payload through a fake Net, so we verify the
schema-to-Job mapping for every source without hitting the internet.
"""

import asyncio

from intern_engine.connectors import (
    amazon,
    ashby,
    breezy,
    greenhouse,
    lever,
    oracle,
    recruitee,
    rippling,
    smartrecruiters,
    workable,
    workday,
)


class FakeNet:
    """Stands in for net.Net: returns a preset payload for any request."""

    def __init__(self, payload):
        self.payload = payload
        self.urls = []

    async def get_json(self, url, **kwargs):
        self.urls.append(url)
        return self.payload

    async def post_json(self, url, **kwargs):
        self.urls.append(url)
        return self.payload


def _run(coro):
    return asyncio.run(coro)


def test_greenhouse():
    payload = {"jobs": [{
        "id": 42, "title": "Software Engineer Intern",
        "location": {"name": "New York, NY"}, "absolute_url": "https://gh/42",
        "first_published": "2026-06-01T08:00:00-04:00",
        "updated_at": "2026-06-15T00:00:00Z",
    }]}
    jobs = _run(greenhouse.fetch({"name": "Acme", "slug": "acme"}, FakeNet(payload)))
    assert len(jobs) == 1
    j = jobs[0]
    assert j.id == "greenhouse:acme:42"
    assert j.title == "Software Engineer Intern"
    assert j.location == "New York, NY"
    assert j.url == "https://gh/42"
    assert j.posted_at == "2026-06-01T08:00:00-04:00"  # true publish date, not updated_at


def test_lever():
    payload = [{
        "id": "abc", "text": "SWE Intern",
        "categories": {"location": "San Francisco"},
        "hostedUrl": "https://lever/abc", "createdAt": 1717200000000,
        "descriptionPlain": "Build things.",
        "additionalPlain": "We are unable to sponsor visas.",
        "salaryRange": {"min": 40000, "max": 60000, "currency": "USD", "interval": "per-year-salary"},
    }]
    jobs = _run(lever.fetch({"name": "Acme", "slug": "acme"}, FakeNet(payload)))
    assert jobs[0].id == "lever:acme:abc"
    assert jobs[0].location == "San Francisco"
    assert jobs[0].posted_at and jobs[0].posted_at.startswith("2024")
    assert "unable to sponsor" in jobs[0].description  # free text for the classifier
    assert jobs[0].salary == "40,000–60,000 USD / per year salary"


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
    net = FakeNet(payload)
    jobs = _run(workday.fetch(company, net))
    assert jobs[0].posted_at is not None        # "3 Days Ago" resolves to a date
    assert jobs[1].posted_at is None            # "30+ Days Ago" is too vague
    assert jobs[0].url.endswith("/Careers/job/1")
    # 2 postings < page size -> exactly one request, no useless pagination.
    assert len(net.urls) == 1
    assert net.urls[0] == "https://acme.wd5.myworkdayjobs.com/wday/cxs/acme/Careers/jobs"


def test_workday_path_style_host():
    payload = {"jobPostings": [
        {"title": "SWE Intern", "externalPath": "/job/1", "locationsText": "AZ"},
    ]}
    company = {"name": "Microchip", "slug": "microchiphr", "wd": "wd5",
               "site": "External", "host": "wd5.myworkdaysite.com"}
    net = FakeNet(payload)
    jobs = _run(workday.fetch(company, net))
    assert net.urls[0] == "https://wd5.myworkdaysite.com/wday/cxs/microchiphr/External/jobs"
    assert jobs[0].url == "https://wd5.myworkdaysite.com/recruiting/microchiphr/External/job/1"


def test_workable():
    payload = {"results": [{
        "title": "AI Inference Engineer Intern", "shortcode": "ABC123",
        "published": "2026-06-10T00:00:00Z", "remote": False,
        "location": {"country": "United States", "city": "Burlingame", "region": "California"},
    }], "nextPage": None}
    jobs = _run(workable.fetch({"name": "Quadric", "slug": "quadric"}, FakeNet(payload)))
    assert jobs[0].id == "workable:quadric:ABC123"
    assert jobs[0].url == "https://apply.workable.com/quadric/j/ABC123/"
    assert jobs[0].location == "Burlingame, California, United States"
    assert jobs[0].posted_at == "2026-06-10T00:00:00Z"


def test_breezy():
    payload = [{
        "id": "fa06", "name": "SWE Intern", "url": "https://acme.breezy.hr/p/fa06-swe",
        "published_date": "2026-06-15T16:41:15.395Z",
        "location": {"name": "Provo, UT"}, "salary": "$25/hr",
    }]
    jobs = _run(breezy.fetch({"name": "Acme", "slug": "acme"}, FakeNet(payload)))
    assert jobs[0].id == "breezy:acme:fa06"
    assert jobs[0].location == "Provo, UT"
    assert jobs[0].salary == "$25/hr"
    assert jobs[0].posted_at.startswith("2026-06-15")


def test_recruitee():
    payload = {"offers": [{
        "id": 99, "title": "Data Intern", "city": "Amsterdam", "country": "Netherlands",
        "careers_url": "https://acme.recruitee.com/o/data-intern",
        "created_at": "2026-06-01", "description": "<p>No visa sponsorship.</p>",
    }]}
    jobs = _run(recruitee.fetch({"name": "Acme", "slug": "acme"}, FakeNet(payload)))
    assert jobs[0].id == "recruitee:acme:99"
    assert jobs[0].location == "Amsterdam, Netherlands"
    assert "sponsorship" in jobs[0].description


def test_oracle():
    payload = {"items": [{"requisitionList": [
        {"Id": "9", "Title": "ML Intern", "PrimaryLocation": "Dearborn, MI",
         "PostedDate": "2026-06-05"},
    ]}]}
    company = {"name": "Ford", "slug": "ford", "host": "x.oraclecloud.com", "site": "CX_1"}
    jobs = _run(oracle.fetch(company, FakeNet(payload)))
    assert jobs[0].id == "oracle:ford:9"
    assert jobs[0].posted_at == "2026-06-05"
