"""Classifier precision tests: real phrases employers write, and the traps.

A wrong flag steers someone away from a real opportunity, so the negative
cases (boilerplate that must NOT trigger) matter as much as the positives.
"""

from intern_engine import sponsorship


class TestCitizensOnly:
    def test_citizenship_required(self):
        assert sponsorship.classify(
            "Applicants must be a U.S. citizen due to contract requirements."
        ) == "citizens-only"

    def test_clearance(self):
        assert sponsorship.classify(
            "Candidates need an active TS/SCI clearance to start."
        ) == "citizens-only"
        assert sponsorship.classify(
            "Ability to obtain a security clearance is required."
        ) == "citizens-only"

    def test_itar(self):
        assert sponsorship.classify(
            "This position is subject to ITAR regulations."
        ) == "citizens-only"

    def test_citizens_or_green_card(self):
        assert sponsorship.classify(
            "Open to U.S. citizens and lawful permanent residents only."
        ) == "citizens-only"

    def test_beats_no_sponsorship_wording(self):
        text = "US citizenship required. We are unable to sponsor visas."
        assert sponsorship.classify(text) == "citizens-only"


class TestNoSponsorship:
    def test_unable_to_sponsor(self):
        assert sponsorship.classify(
            "We are unable to sponsor or take over sponsorship of an employment visa."
        ) == "no-sponsorship"

    def test_does_not_offer(self):
        assert sponsorship.classify(
            "Please note this role does not offer visa sponsorship."
        ) == "no-sponsorship"

    def test_without_sponsorship(self):
        assert sponsorship.classify(
            "Must be authorized to work in the United States without sponsorship "
            "now or in the future."
        ) == "no-sponsorship"

    def test_not_available(self):
        assert sponsorship.classify(
            "Immigration sponsorship is not available for this position."
        ) == "no-sponsorship"

    def test_html_input(self):
        html = "<p>We <b>cannot sponsor</b> work visas for this role.</p>"
        assert sponsorship.classify(html) == "no-sponsorship"


class TestOffers:
    def test_sponsorship_available(self):
        assert sponsorship.classify(
            "Visa sponsorship is available for exceptional candidates."
        ) == "offers"

    def test_will_sponsor(self):
        assert sponsorship.classify("We will sponsor H-1B visas.") == "offers"


class TestUnknownAndTraps:
    def test_empty(self):
        assert sponsorship.classify(None) == "unknown"
        assert sponsorship.classify("") == "unknown"

    def test_plain_role_text(self):
        assert sponsorship.classify(
            "Build distributed systems in Go and Python. Free lunch."
        ) == "unknown"

    def test_eeo_boilerplate_is_not_citizens_only(self):
        # Standard non-discrimination text mentions citizenship without requiring it.
        assert sponsorship.classify(
            "We consider applicants regardless of race, religion, national origin, "
            "citizenship status, or veteran status."
        ) == "unknown"

    def test_flag_emoji(self):
        assert sponsorship.flag("citizens-only") == "🇺🇸"
        assert sponsorship.flag("no-sponsorship") == "🛂"
        assert sponsorship.flag("offers") == ""
        assert sponsorship.flag("unknown") == ""
        assert sponsorship.flag(None) == ""

    def test_strip_html(self):
        assert sponsorship.strip_html("<p>Hello&nbsp;<b>world</b></p>") == "Hello world"
