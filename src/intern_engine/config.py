"""Tunable settings, loaded from data/config.json (with safe defaults).

Change behavior without touching code:
  - cycles        : the exact intern cycles to show, e.g. ["Summer 2027", "Fall 2026"].
                    These become the section headings, in this order.
  - default_cycle : where to put roles that have no clear term/year (e.g. just
                    "Software Engineer Intern"). Must be one of `cycles`.
  - regions       : ["US"] for United States only, ["US", "Canada"] for both,
                    or ["Global"] to disable the location filter entirely.
  - role_scope    : "tech" (SWE/data/ML/quant/hardware/...) or "all" internships.
"""

from __future__ import annotations

import json
import os
import re

from . import paths

DEFAULTS = {
    "cycles": ["Summer 2027", "Fall 2026"],
    "default_cycle": "Summer 2027",
    "regions": ["US"],
    "role_scope": "tech",
}

_FALLBACK_REPO = "zshah101/Automated-List-Of-Summer-2027-and-Fall-2026-Tech-Internships"


def repo_slug() -> str:
    """"owner/name" for this repo: from Actions env, else the git remote."""
    env = os.environ.get("GITHUB_REPOSITORY")
    if env and "/" in env:
        return env
    try:
        with open(os.path.join(paths.ROOT, ".git", "config"), encoding="utf-8") as f:
            m = re.search(r"github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?\s", f.read())
            if m:
                return m.group(1)
    except OSError:
        pass
    return _FALLBACK_REPO


def pages_base() -> str:
    """The GitHub Pages base URL serving docs/ (dashboard, feed, JSON API)."""
    owner, _, name = repo_slug().partition("/")
    return f"https://{owner.lower()}.github.io/{name}"

_GLOBAL_TOKENS = {"global", "international", "worldwide", "any", "all"}
_US_TOKENS = {"us", "usa", "united states", "u.s.", "america"}


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    try:
        with open(paths.CONFIG_PATH, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, json.JSONDecodeError):
        pass
    return cfg


def cycles(cfg: dict) -> list[str]:
    return list(cfg.get("cycles") or DEFAULTS["cycles"])


def restrict_region(cfg: dict) -> bool:
    regions = cfg.get("regions") or []
    if not regions:
        return False
    return not any(str(r).lower() in _GLOBAL_TOKENS for r in regions)


def want_us(cfg: dict) -> bool:
    return any(str(r).lower() in _US_TOKENS for r in (cfg.get("regions") or []))


def want_canada(cfg: dict) -> bool:
    return any(str(r).lower() == "canada" for r in (cfg.get("regions") or []))


def section_limit(cfg: dict, label: str):
    """Max rows to show for a section, or None for no cap."""
    return (cfg.get("section_limits") or {}).get(label)


def max_age_days(cfg: dict):
    """Drop roles published longer ago than this many days. 0/None = no limit."""
    return cfg.get("max_age_days", 365)


def max_per_company(cfg: dict):
    """Max roles to show per company per section, for variety. 0/None = no limit."""
    return cfg.get("max_per_company", 0)


def allowlist_only(cfg: dict) -> bool:
    """When true, show only recognizable (priority-listed) companies. Off by default."""
    return bool(cfg.get("allowlist_only", False))


def include_international(cfg: dict) -> bool:
    """When true, also keep non-US roles (shown in a separate International section)."""
    return bool(cfg.get("include_international", False))
