"""Circuit-breaker behavior: quarantine after repeat failures, self-heal after."""

from datetime import UTC, datetime, timedelta

from intern_engine import health

COMPANY = {"ats": "greenhouse", "slug": "deadco", "name": "DeadCo"}
NOW = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)


def _fail_n(data: dict, n: int, now=NOW):
    for _ in range(n):
        health.record(data, COMPANY, "HTTPStatusError: 404", now=now)


class TestBreaker:
    def test_under_threshold_still_fetched(self):
        data: dict = {}
        _fail_n(data, 2)
        active, benched = health.partition([COMPANY], data, now=NOW)
        assert active == [COMPANY] and benched == []

    def test_quarantined_after_threshold(self):
        data: dict = {}
        _fail_n(data, 3)
        active, benched = health.partition([COMPANY], data, now=NOW + timedelta(hours=1))
        assert active == [] and benched == [COMPANY]

    def test_window_expires_and_retries(self):
        data: dict = {}
        _fail_n(data, 3)
        # 3 failures -> 6h window; at 7h the board gets another chance.
        active, _ = health.partition([COMPANY], data, now=NOW + timedelta(hours=7))
        assert active == [COMPANY]

    def test_backoff_grows(self):
        data: dict = {}
        _fail_n(data, 5)
        # 5 failures -> 24h window: still benched at 20h, retried at 25h.
        _, benched = health.partition([COMPANY], data, now=NOW + timedelta(hours=20))
        assert benched == [COMPANY]
        active, _ = health.partition([COMPANY], data, now=NOW + timedelta(hours=25))
        assert active == [COMPANY]

    def test_success_resets_and_shrinks_file(self):
        data: dict = {}
        _fail_n(data, 4)
        health.record(data, COMPANY, None, now=NOW)
        assert data == {}  # healthy companies carry no entry at all

    def test_healthy_company_untracked(self):
        data: dict = {}
        health.record(data, COMPANY, None, now=NOW)
        assert data == {}
