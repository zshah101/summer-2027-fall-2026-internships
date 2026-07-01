from intern_engine import store
from intern_engine.models import Job
from intern_engine.pipeline import _dedup


def _job_dict(jid, title="Software Engineer Intern"):
    return {
        "id": jid, "source": "greenhouse", "company_slug": "stripe",
        "company": "Stripe", "title": title, "location": "San Francisco, CA",
        "url": "https://example.com", "posted_at": None,
        "season": "Summer 2027", "category": "Software",
    }


class TestUpsert:
    def test_new_seen_closed_lifecycle(self):
        existing: dict = {}
        keys = {"greenhouse:stripe"}

        new_ids = store.upsert(existing, [_job_dict("a")], keys)
        assert new_ids == ["a"]
        assert existing["a"]["is_open"] is True
        first_seen = existing["a"]["first_seen_at"]

        # Same job again -> not "new", first_seen frozen.
        assert store.upsert(existing, [_job_dict("a")], keys) == []
        assert existing["a"]["first_seen_at"] == first_seen

        # Job disappears from a company we DID reach -> marked closed.
        store.upsert(existing, [], keys)
        assert existing["a"]["is_open"] is False

    def test_unreached_company_is_not_closed(self):
        existing: dict = {}
        store.upsert(existing, [_job_dict("a")], {"greenhouse:stripe"})
        # This run did NOT successfully reach stripe -> must not close its jobs.
        store.upsert(existing, [], succeeded_keys=set())
        assert existing["a"]["is_open"] is True

    def test_closed_gets_timestamp_and_reopening_clears_it(self):
        existing: dict = {}
        keys = {"greenhouse:stripe"}
        store.upsert(existing, [_job_dict("a")], keys)
        store.upsert(existing, [], keys)
        assert existing["a"]["is_open"] is False
        assert existing["a"]["closed_at"]
        # The role comes back -> open again, closed_at wiped.
        store.upsert(existing, [_job_dict("a")], keys)
        assert existing["a"]["is_open"] is True
        assert "closed_at" not in existing["a"]

    def test_posted_at_backfills_blanks_but_never_shifts(self):
        existing: dict = {}
        keys = {"greenhouse:stripe"}
        store.upsert(existing, [_job_dict("a")], keys)
        assert existing["a"]["posted_at"] is None

        dated = _job_dict("a") | {"posted_at": "2026-06-01T00:00:00Z"}
        store.upsert(existing, [dated], keys)
        assert existing["a"]["posted_at"] == "2026-06-01T00:00:00Z"  # blank filled

        shifted = _job_dict("a") | {"posted_at": "2026-06-20T00:00:00Z"}
        store.upsert(existing, [shifted], keys)
        assert existing["a"]["posted_at"] == "2026-06-01T00:00:00Z"  # frozen

    def test_sponsorship_verdict_never_clobbered_by_unknown(self):
        existing: dict = {}
        keys = {"greenhouse:stripe"}
        flagged = _job_dict("a") | {"sponsorship": "no-sponsorship"}
        store.upsert(existing, [flagged], keys, enriched_ids={"a"})
        assert existing["a"]["sponsorship"] == "no-sponsorship"
        assert existing["a"]["enriched_at"]

        # Next run didn't re-enrich (verdict already stored) -> stays flagged.
        unknown = _job_dict("a") | {"sponsorship": "unknown"}
        store.upsert(existing, [unknown], keys)
        assert existing["a"]["sponsorship"] == "no-sponsorship"


class TestPurge:
    def test_drops_long_closed_keeps_recent_and_open(self):
        existing = {
            "old": {"id": "old", "is_open": False, "closed_at": "2026-01-01T00:00:00Z"},
            "recent": {"id": "recent", "is_open": False, "closed_at": store.now_iso()},
            "open": {"id": "open", "is_open": True},
        }
        assert store.purge(existing, keep_closed_days=60) == 1
        assert set(existing) == {"recent", "open"}


class TestDedup:
    def test_collapses_same_role_and_prefers_dated(self):
        undated = Job(id="1", source="greenhouse", company="Stripe",
                      company_slug="stripe", title="Software Engineer Intern",
                      location="SF", url="a", posted_at=None)
        dated = Job(id="2", source="lever", company="Stripe",
                    company_slug="stripe", title="Software Engineer  Intern!",
                    location="SF", url="b", posted_at="2026-06-01T00:00:00Z")
        out = _dedup([undated, dated])
        assert len(out) == 1
        assert out[0].posted_at == "2026-06-01T00:00:00Z"

    def test_keeps_distinct_titles(self):
        a = Job(id="1", source="ashby", company="Verkada", company_slug="verkada",
                title="Backend SWE Intern", location="CA", url="a", posted_at=None)
        b = Job(id="2", source="ashby", company="Verkada", company_slug="verkada",
                title="Frontend SWE Intern", location="CA", url="b", posted_at=None)
        assert len(_dedup([a, b])) == 2
