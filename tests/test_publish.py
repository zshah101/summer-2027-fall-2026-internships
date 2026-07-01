"""The machine-readable outputs: Atom feed parses, JSON API round-trips."""

import json
import os
import xml.etree.ElementTree as ET

from intern_engine import paths, publish

STORE = {
    "a": {
        "id": "a", "company": "Stripe", "title": "SWE Intern", "season": "Summer 2027",
        "category": "Software", "location": "SF", "url": "https://stripe.com/jobs/1",
        "posted_at": "2026-06-01T00:00:00Z", "first_seen_at": "2026-06-02T00:00:00Z",
        "sponsorship": "no-sponsorship", "salary": None, "source": "greenhouse",
        "is_open": True,
    },
    "b": {
        "id": "b", "company": "Old Co", "title": "Closed Intern", "season": "Fall 2026",
        "category": "Software", "location": "NY", "url": "https://old.co",
        "first_seen_at": "2026-05-01T00:00:00Z", "sponsorship": "unknown",
        "source": "lever", "is_open": False,
    },
}


def _redirect(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "DOCS_DIR", str(tmp_path))
    monkeypatch.setattr(paths, "FEED_PATH", str(tmp_path / "feed.xml"))
    monkeypatch.setattr(paths, "API_DIR", str(tmp_path / "api"))


class TestFeed:
    def test_only_open_roles_and_valid_xml(self, monkeypatch, tmp_path):
        _redirect(monkeypatch, tmp_path)
        n = publish.write_feed(STORE)
        assert n == 1
        tree = ET.parse(tmp_path / "feed.xml")
        ns = {"a": "http://www.w3.org/2005/Atom"}
        entries = tree.getroot().findall("a:entry", ns)
        assert len(entries) == 1
        title = entries[0].find("a:title", ns).text
        assert "Stripe" in title and "🛂" in title


class TestApi:
    def test_jobs_json_shape(self, monkeypatch, tmp_path):
        _redirect(monkeypatch, tmp_path)
        n = publish.write_api(STORE, {"open_total": 1})
        assert n == 1
        with open(os.path.join(str(tmp_path / "api"), "jobs.json"), encoding="utf-8") as f:
            payload = json.load(f)
        assert payload["count"] == 1
        job = payload["jobs"][0]
        assert job["company"] == "Stripe"
        assert job["sponsorship"] == "no-sponsorship"
        assert "is_open" not in job  # only open roles ship, flag is redundant
