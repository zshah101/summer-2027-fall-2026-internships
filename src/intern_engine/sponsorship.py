"""Visa-sponsorship classification from real posting text (the F-1 edge).

Reference lists tag sponsorship by hand; we detect it from each job description.
The classifier is deliberately phrase-anchored (whole expressions employers
actually write), not keyword soup — a wrong "no sponsorship" flag steers someone
away from a real opportunity, so precision beats recall here.

Values (strictest wins):
  citizens-only   — U.S. citizenship / clearance / ITAR-style "U.S. persons" only
  no-sponsorship  — the employer says it will not sponsor a work visa
  offers          — the employer explicitly says it sponsors
  unknown         — the text says nothing conclusive (most postings)
"""

from __future__ import annotations

import re
from html import unescape

# ITAR / export control and security clearances require citizenship (or at
# minimum a green card), which excludes F-1/OPT candidates the same way.
_CITIZENS_RE = re.compile(
    r"("
    r"(?:u\.?s\.?|united states)\s+citizen(?:ship)?\s+(?:is\s+)?(?:required|only|mandatory)"
    r"|must\s+be\s+(?:a\s+|an\s+)?(?:u\.?s\.?|united states)\s+citizen"
    r"|citizenship\s*:\s*(?:u\.?s\.?|united states|required)"
    r"|only\s+(?:u\.?s\.?|united states)\s+citizens"
    r"|(?:u\.?s\.?|united states)\s+citizens?\s+(?:or|and)\s+(?:lawful\s+)?(?:permanent\s+residents?|green\s?card)"
    r"|\bitar\b"
    r"|export.{0,20}(?:control|compliance).{0,60}u\.?s\.?\s+person"
    r"|u\.?s\.?\s+persons?\s+(?:status\s+)?(?:is\s+)?required"
    r"|(?:security|government|ts/?sci|top.secret|secret)\s+clearance"
    r"|clearance\s+(?:is\s+)?required"
    r")",
    re.IGNORECASE,
)

_NO_SPONSOR_RE = re.compile(
    r"("
    r"(?:unable|not\s+able|not\s+available)\s+to\s+(?:sponsor|offer|provide|support)[^.]{0,60}?(?:sponsorship|visa|\.|,|;|$)"
    r"|(?:can\s*not|cannot|will\s+not|won'?t|do(?:es)?\s+not|don'?t)\s+(?:currently\s+|now\s+)?"
    r"(?:sponsor|offer\s+(?:visa\s+|immigration\s+|work[\s-]?visa\s+)?sponsorship|provide\s+(?:visa\s+|immigration\s+)?sponsorship)"
    r"|sponsorship\s+(?:is\s+)?(?:not|un)\s*(?:available|offered|provided|possible|supported)"
    r"|no\s+(?:visa|immigration|work[\s-]?visa|h-?1b)\s+sponsorship"
    r"|not\s+eligible\s+for\s+(?:visa\s+|immigration\s+)?sponsorship"
    r"|without\s+(?:the\s+need\s+for\s+|requiring\s+|need\s+of\s+)?(?:visa\s+)?sponsorship"
    r"|without\s+(?:company\s+)?sponsorship\s+(?:now\s+or\s+in\s+the\s+future|at\s+any\s+time)?"
    r"|unable\s+to\s+sponsor"
    r"|does\s+not\s+sponsor"
    r"|not\s+(?:be\s+)?provid(?:e|ing)\s+(?:visa\s+|immigration\s+)?sponsorship"
    r")",
    re.IGNORECASE,
)

_OFFERS_RE = re.compile(
    r"("
    r"(?:visa|h-?1b|immigration|work[\s-]?visa)\s+sponsorship\s+(?:is\s+)?(?:available|offered|provided|possible)"
    r"|sponsorship\s+(?:is\s+|may\s+be\s+|can\s+be\s+)?(?:available|offered|provided)"
    r"|(?:will|can|do(?:es)?|happy\s+to|able\s+to)\s+(?:sponsor|provide\s+(?:visa\s+)?sponsorship|offer\s+(?:visa\s+)?sponsorship)"
    r"|open\s+to\s+sponsor"
    r"|we\s+sponsor\s+(?:work\s+)?visas"
    r")",
    re.IGNORECASE,
)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

# Emoji used in the README / dashboard — same visual language readers already
# know from the big hand-curated lists.
FLAGS = {
    "citizens-only": "\U0001f1fa\U0001f1f8",   # 🇺🇸
    "no-sponsorship": "\U0001f6c2",            # 🛂
}


def strip_html(html: str | None) -> str:
    """Plain text from an HTML blob — good enough for phrase matching."""
    if not html:
        return ""
    return _WS_RE.sub(" ", unescape(_TAG_RE.sub(" ", html))).strip()


def classify(text: str | None) -> str:
    """Classify one posting's text. Strictest verdict wins.

    citizens-only beats no-sponsorship (it also excludes green-card holders),
    and both beat an "offers" phrase elsewhere in the same posting.
    """
    if not text:
        return "unknown"
    plain = strip_html(text) if "<" in text else _WS_RE.sub(" ", text)
    if _CITIZENS_RE.search(plain):
        return "citizens-only"
    if _NO_SPONSOR_RE.search(plain):
        return "no-sponsorship"
    if _OFFERS_RE.search(plain):
        return "offers"
    return "unknown"


def flag(value: str | None) -> str:
    """The emoji shown next to a role title ('' when nothing to warn about)."""
    return FLAGS.get(value or "", "")
