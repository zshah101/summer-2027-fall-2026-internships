"""Discover companies at scale from public internship datasets.

We do NOT republish other people's listings. We read their data files only to
learn *which companies exist and on which ATS*, by pulling the ATS token (and,
for Workday, the tenant + site) out of each apply URL. Those are merged into
data/companies.json, and from then on we poll each company's feed DIRECTLY.

Run with:  python run.py discover
"""

from __future__ import annotations

import json
import re

import requests

from . import paths

PUBLIC_SOURCES = [
    "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/dev/.github/scripts/listings.json",
    "https://raw.githubusercontent.com/vanshb03/Summer2026-Internships/dev/.github/scripts/listings.json",
]

# Pull the company token out of an ATS apply URL.
_PATTERNS = {
    "greenhouse": [
        re.compile(r"(?:job-boards|boards)\.greenhouse\.io/([a-z0-9][a-z0-9_\-]*)", re.I),
        re.compile(r"//([a-z0-9][a-z0-9_\-]*)\.greenhouse\.io", re.I),
    ],
    "lever": [re.compile(r"jobs\.lever\.co/([a-z0-9][a-z0-9_\-]*)", re.I)],
    "ashby": [re.compile(r"jobs\.ashbyhq\.com/([a-z0-9][a-z0-9_\-]*)", re.I)],
    "smartrecruiters": [re.compile(r"jobs\.smartrecruiters\.com/([A-Za-z0-9][\w\-]*)")],
}

_BLOCKLIST = {"jobs", "www", "careers", "job", "embed", "search"}

# Workday: capture tenant, datacenter (wdN), and site slug.
_WD_RE = re.compile(
    r"https://([\w-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([\w%-]+)",
    re.I,
)

# Workday hosts thousands of mostly non-tech enterprises, so we only keep the
# tech / finance / fintech names students actually want (matched in the name).
_WD_DESIRABLE = {
    # software / cloud / dev
    "nvidia", "salesforce", "adobe", "servicenow", "workday", "autodesk",
    "intuit", "vmware", "cisco", "dell", "hewlett", "hpe", "sap", "oracle",
    "ibm", "atlassian", "splunk", "palo alto", "fortinet", "zscaler",
    "crowdstrike", "datadog", "snowflake", "twilio", "dropbox", "docusign",
    "zoom", "unity", "roblox", "electronic arts", "activision", "take-two",
    "nutanix", "pure storage", "netapp", "arista", "juniper", "akamai",
    "cloudflare", "hubspot", "zoominfo", "garmin", "dolby", "workiva",
    # semiconductors that hire lots of SWE/ML interns
    "amd", "intel", "qualcomm", "marvell", "micron", "broadcom",
    "analog devices", "texas instruments", "nxp", "microchip", "western digital",
    # finance / fintech / quant
    "paypal", "visa", "mastercard", "capital one", "american express",
    "jpmorgan", "jp morgan", "goldman", "morgan stanley", "citi", "wells fargo",
    "bank of america", "blackrock", "fidelity", "charles schwab", "state street",
    "bny", "nasdaq", "s&p global", "bloomberg", "fiserv", "global payments",
    "sofi", "robinhood", "coinbase", "block", "discover financial",
    # telecom / media-tech
    "comcast", "verizon", "t-mobile", "disney", "warner bros", "expedia",
    "booking", "thomson reuters",
}


def _is_desirable_workday(name: str) -> bool:
    n = (name or "").lower()
    return any(k in n for k in _WD_DESIRABLE)


def _extract_simple(listings: list) -> dict:
    """{(ats, slug): company_name} for Greenhouse/Lever/Ashby/SmartRecruiters."""
    found: dict[tuple[str, str], str] = {}
    for item in listings:
        if not isinstance(item, dict):
            continue
        name = (item.get("company_name") or "").strip()
        blob = " ".join(str(item.get(k, "")) for k in ("url", "company_url"))
        for ats, patterns in _PATTERNS.items():
            for pattern in patterns:
                for slug in pattern.findall(blob):
                    if ats != "smartrecruiters":
                        slug = slug.lower()
                    if slug.lower() in _BLOCKLIST:
                        continue
                    found.setdefault((ats, slug), name or slug)
    return found


def _extract_workday(listings: list) -> dict:
    """{(workday, tenant): {name, wd, site}} for desirable Workday tenants."""
    found: dict[tuple[str, str], dict] = {}
    for item in listings:
        if not isinstance(item, dict):
            continue
        name = (item.get("company_name") or "").strip()
        if not _is_desirable_workday(name):
            continue
        blob = " ".join(str(item.get(k, "")) for k in ("url", "company_url"))
        m = _WD_RE.search(blob)
        if not m:
            continue
        tenant, wd, site = m.group(1), m.group(2).lower(), m.group(3)
        if site.lower() in ("job", "jobs", "en", "en-us"):
            continue  # grabbed a path/locale fragment, not the real site
        found.setdefault((tenant, site), {"name": name or tenant, "wd": wd, "site": site, "tenant": tenant})
    return found


def discover() -> tuple[list[dict], int]:
    session = requests.Session()
    session.headers.update({"User-Agent": "intern-engine/1.0 (+github.com/intern-engine)"})

    simple: dict[tuple[str, str], str] = {}
    wd: dict[tuple[str, str], dict] = {}
    for url in PUBLIC_SOURCES:
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict):
                data = data.get("listings") or list(data.values())
            simple.update(_extract_simple(data))
            wd.update(_extract_workday(data))
        except (requests.RequestException, ValueError) as exc:
            print(f"  source failed: {url} ({exc})")

    # Merge into existing companies.json, preserving full records (incl. wd/site).
    merged: dict[tuple[str, str], dict] = {}
    try:
        with open(paths.COMPANIES_PATH, encoding="utf-8") as f:
            for c in json.load(f):
                merged[(c["ats"], c["slug"])] = c
    except (OSError, json.JSONDecodeError, KeyError):
        pass

    for (ats, slug), name in simple.items():
        merged.setdefault((ats, slug), {"name": name, "slug": slug, "ats": ats})
    for info in wd.values():
        key = ("workday", info["tenant"])
        merged.setdefault(key, {
            "name": info["name"], "slug": info["tenant"], "ats": "workday",
            "wd": info["wd"], "site": info["site"],
        })

    companies = sorted(merged.values(), key=lambda c: c["name"].lower())
    with open(paths.COMPANIES_PATH, "w", encoding="utf-8") as f:
        json.dump(companies, f, indent=2, ensure_ascii=False)

    return companies, len(simple) + len(wd)
