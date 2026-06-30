"""Render the public-facing README.md (the product) + a CSV tracker.

Plain, professional, human voice. No decorative emojis. Sections are exactly the
configured cycles, in order. Roles are sorted by their PUBLISHED date (newest on
top), and that date is frozen per role so the page behaves like a ladder.
"""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime

from . import config, filters, paths, priority


def _engine_metrics() -> str:
    """One-line observability summary from the last run, if available."""
    try:
        with open(paths.STATS_PATH, encoding="utf-8") as f:
            stats = json.load(f)
    except (OSError, ValueError):
        return ""
    sources = len(stats.get("companies_by_source", {}))
    line = (
        f"_Engine (last run): {stats.get('companies_total', 0):,} companies across "
        f"{sources} ATS platforms · {int(stats.get('fetch_success_rate', 0) * 100)}% "
        f"fetch success · completed in {stats.get('duration_seconds', 0)}s"
    )
    latency = stats.get("detection_latency") or {}
    if latency.get("median_minutes") is not None and latency.get("sample_size", 0) >= 5:
        line += f" · median detection latency {latency['median_minutes']:.0f} min"
    return line + "._"


def _now_str() -> str:
    return datetime.now(UTC).strftime("%b %d, %Y at %H:%M UTC")


def _md_cell(text: str) -> str:
    return (text or "—").replace("|", "/").replace("\n", " ").strip() or "—"


def _short_location(loc: str, limit: int = 40) -> str:
    loc = _md_cell(loc)
    if len(loc) <= limit:
        return loc
    parts = [p.strip() for p in loc.replace(";", ",").split(",") if p.strip()]
    if len(parts) > 1:
        return f"{parts[0]} +{len(parts) - 1} more"
    return loc[: limit - 1].rstrip() + "…"


def _date_str(record: dict) -> str:
    """The published date string we sort/display by (frozen per role)."""
    # Display only a REAL published date (no first_seen fallback) — undated -> dash.
    return record.get("posted_at") or ""


def _sort_key(record: dict):
    # Dated roles first (newest), undated sink to the bottom; first_seen breaks
    # ties so undated roles still have a stable, newest-first order.
    return ((record.get("posted_at") or "")[:10], (record.get("first_seen_at") or "")[:19])


def _pretty_date(record: dict) -> str:
    iso = _date_str(record)
    if not iso:
        return "—"
    try:
        return datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%b %d, %Y")
    except ValueError:
        return iso[:10]


def _row(record: dict) -> str:
    company = _md_cell(record.get("company"))
    title = _md_cell(record.get("title"))
    location = _short_location(record.get("location"))
    category = _md_cell(record.get("category"))
    posted = _pretty_date(record)
    url = record.get("url") or ""
    apply = f"[Apply]({url})" if url else "—"
    return f"| {company} | {title} | {category} | {location} | {posted} | {apply} |"


def _region_label(cfg: dict) -> str:
    if not config.restrict_region(cfg):
        return "Worldwide"
    parts = []
    if config.want_us(cfg):
        parts.append("United States")
    if config.want_canada(cfg):
        parts.append("Canada")
    return " & ".join(parts) if parts else "United States"


def _company_count() -> int:
    try:
        with open(paths.COMPANIES_PATH, encoding="utf-8") as f:
            return len(json.load(f))
    except (OSError, ValueError):
        return 0


def _header(cfg: dict, total_open: int, companies: int) -> list[str]:
    region = _region_label(cfg)
    cycles = config.cycles(cfg)
    cycles_phrase = " and ".join(cycles)

    return [
        "# Summer 2027 Tech Internships",
        "",
        "A self-updating engine that tracks tech internships so you don't have to. "
        "Instead of refreshing a dozen career pages by hand, it reads company hiring "
        "feeds directly and keeps one live list, newest roles on top, refreshed "
        "automatically throughout the day.",
        "",
        f"**{total_open} open roles · {companies} companies tracked · "
        f"updated {_now_str()}**",
        "",
        "**⭐Star this repo⭐** to save it and get updates when new roles are added.",
        "",
        "## What this is",
        "",
        "This is an engine, not a hand-kept list. It polls company career feeds several "
        "times a day, finds the internships, removes duplicates, and rebuilds this page "
        "on its own. Every link comes straight from the source, so it's real and "
        "current, not a stale list someone forgot to update (speed matters).",
        "",
        "## Scope",
        "",
        "- **Roles:** Software Engineering, Data Science & Machine Learning "
        "(and closely related technical internships)",
        f"- **Region:** {region} (primary), with a separate International section",
        f"- **Cycles:** {cycles_phrase}",
        "",
        "## About",
        "",
        "I'm a US-based international student studying in the United States, so I "
        "built this for the search I'm doing myself. It started US-focused and now "
        "covers international roles too. Use it to spot roles early and apply before "
        "they fill up - being first genuinely helps.",
        "",
        "## Where this is going",
        "",
        "I'm building this in the open and adding to it as it grows. Coming soon: "
        "**SMS/email alerts** the moment a role opens, and **filtering** by role, "
        "location, and visa-sponsorship (a real one for fellow international "
        "students). If it helps you, a star means a lot and tells me to keep going.",
        "",
        "## How to use",
        "",
        "- Roles are grouped by cycle below - **newest posting on top, oldest at the bottom.**",
        "- The **Posted** column is the date the company published the role.",
        "- Track your applications with [`data/internships.csv`](data/internships.csv) "
        "(opens in Excel / Google Sheets).",
        "- Missing a company? Adding one takes a single line, see "
        "[CONTRIBUTING.md](CONTRIBUTING.md).",
        "",
        "---",
        "",
    ]


def _footer() -> list[str]:
    return [
        "---",
        "",
        "## How it stays current",
        "",
        "A small Python engine reads public company hiring feeds directly, keeps the "
        "roles that match the scope above, de-duplicates across sources, records each "
        "role's published date once (so it never shifts), and regenerates this page "
        "through GitHub Actions. It polls every company concurrently (async) with "
        "retry/backoff and per-host rate limits. The full source is in this repo.",
        "",
        _engine_metrics(),
        "",
        "## Contributing",
        "",
        "Adding a company takes one line, see [CONTRIBUTING.md](CONTRIBUTING.md). "
        "Suggestions and pull requests are welcome.",
        "",
        "## Note on dates",
        "",
        "The **Posted** column shows when a role was published, with the newest at the "
        "top. I pull the posting date straight from each job portal, but a lot of them "
        "don't expose one publicly, so those rows show a dash (—) for now instead of a "
        "guessed date. The ones that do publish a date are dated. Know the real date for "
        "a dashed role? Open a PR and I'll merge it.",
        "",
        "Roles can close at any time, so always confirm on the company's own site before "
        "applying.",
        "",
    ]


def _select(rows: list[dict], limit, per_company) -> list[dict]:
    """Pick which rows to show, then order them newest-first for display.

    1) cap each company to `per_company` (variety, newest kept),
    2) if still over `limit`, keep the most sought-after companies first,
    3) display newest on top.
    """
    rows = sorted(rows, key=_sort_key, reverse=True)
    if per_company:
        seen: dict[str, int] = {}
        capped = []
        for r in rows:
            c = (r.get("company") or "").strip().lower()
            if seen.get(c, 0) >= per_company:
                continue
            seen[c] = seen.get(c, 0) + 1
            capped.append(r)
        rows = capped
    if limit and len(rows) > limit:
        rows = sorted(rows, key=lambda r: priority.rank(r.get("company")))[:limit]
    return sorted(rows, key=lambda r: _date_str(r)[:10], reverse=True)


def _region_of(record: dict) -> str:
    return "US" if filters.is_united_states(record.get("location") or "") else "International"


def generate(store_data: dict) -> dict:
    cfg = config.load_config()
    cycles = config.cycles(cfg)
    per_company = config.max_per_company(cfg)

    open_jobs = [r for r in store_data.values() if r.get("is_open")]
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in open_jobs:
        groups.setdefault((_region_of(r), r.get("season", "")), []).append(r)

    sections: list[tuple[str, list[dict]]] = []
    displayed: list[dict] = []
    for region in ("US", "International"):
        for cycle in cycles:
            rows = _select(
                groups.get((region, cycle)) or [],
                config.section_limit(cfg, cycle),
                per_company,
            )
            if rows:
                heading = cycle if region == "US" else f"{cycle} (International)"
                sections.append((heading, rows))
                displayed.extend(rows)

    lines = _header(cfg, len(displayed), _company_count())
    for heading, rows in sections:
        lines.append(f"## {heading}  ({len(rows)} open)")
        lines.append("")
        lines.append("| Company | Role | Category | Location | Posted | Apply |")
        lines.append("|---|---|---|---|---|---|")
        lines.extend(_row(r) for r in rows)
        lines.append("")

    if not displayed:
        lines.append(
            "_No matching roles right now, the list fills as companies post. "
            "Star it and check back._"
        )
        lines.append("")

    lines.extend(_footer())

    with open(paths.README_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    _write_csv(displayed)

    return {"open": len(displayed), "companies": _company_count()}


def _write_csv(open_jobs: list[dict]) -> None:
    fields = [
        "company", "title", "season", "category", "location",
        "posted_at", "first_seen_at", "url",
    ]
    with open(paths.CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in open_jobs:
            writer.writerow({k: r.get(k, "") for k in fields})
