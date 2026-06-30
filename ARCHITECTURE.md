# Architecture

A small, dependency-light Python engine that reads public ATS job feeds, keeps
only the internships we care about (configurable cycle / region / scope), tracks
them over time, and regenerates the public `README.md` + a CSV. GitHub Actions
runs it on a schedule and commits the refreshed output.

## Data flow

```
data/candidates.json        (company name + slug guesses)
        │  python run.py harvest
        ▼
  harvester.py  ──probes Greenhouse/Lever/Ashby──►  data/companies.json
                                                     (validated: name, slug, ats)
        │  python run.py update
        ▼
  pipeline.py  ──fetches all companies concurrently──►  connectors/*.py
        │                                                (return normalized Job[])
        │  keep: internship? scope? target year? region?
        ▼
  store.py  ──merge into──►  data/jobs.json   (dedup + first-seen + open/closed)
        │
        ▼
  readme.py  ──renders──►  README.md  +  data/internships.csv
```

## Files

| File | Responsibility |
|---|---|
| `run.py` | CLI entrypoint: `harvest` \| `update` \| `all`. Puts `src/` on the path. |
| `src/intern_engine/models.py` | The `Job` dataclass — the one shape every connector returns. |
| `src/intern_engine/paths.py` | All file paths, computed from the repo root (CI-safe). |
| `src/intern_engine/config.py` | Loads `data/config.json` (target year, regions, role scope) with defaults. |
| `src/intern_engine/connectors/greenhouse.py` | Fetch + normalize Greenhouse postings. |
| `src/intern_engine/connectors/lever.py` | Fetch + normalize Lever postings. |
| `src/intern_engine/connectors/ashby.py` | Fetch + normalize Ashby postings. |
| `src/intern_engine/filters.py` | Classification: internship? tech? season/year? US/Canada? category. |
| `src/intern_engine/harvester.py` | Discovery: probe candidate slugs, detect which ATS each lives on. |
| `src/intern_engine/store.py` | Persistent JSON store: dedup, first-seen, open/closed tracking. |
| `src/intern_engine/pipeline.py` | Orchestrates fetch → filter → store (concurrent, fault-isolated). |
| `src/intern_engine/readme.py` | Renders `README.md` + `data/internships.csv`. |
| `.github/workflows/update.yml` | Scheduled CI: install, run update, commit changes. |
| `data/config.json` | Tunable settings (see below). |
| `data/candidates.json` | Raw company candidates to probe. |
| `data/companies.json` | Validated companies the pipeline reads. |
| `data/jobs.json` | The persistent job state (source of truth for the README). |

## Configuration (`data/config.json`)

```json
{
  "cycles": ["Summer 2027", "Fall 2026"],
  "regions": ["US"],
  "role_scope": "tech",
  "max_age_days": 270,
  "max_per_company": 3,
  "section_limits": { "Summer 2027": 100, "Fall 2026": 40 }
}
```

- `cycles` — the exact cycles to show; these become the section headings, in order.
  A role is kept ONLY if its title explicitly states the year (e.g. "2027" or
  "Fall 2026"); undated roles and other cycles are dropped.
- `regions` — `["US"]` (United States only), `["US", "Canada"]`, or `["Global"]`
  to disable the location filter.
- `role_scope` — `"tech"` keeps only tech roles; `"all"` keeps every internship.
- `max_age_days` — drop postings published longer ago than this (kills stale/evergreen reqs).
- `max_per_company` — cap roles shown per company per section, for variety.
- `section_limits` — max rows per section; over the cap, the most sought-after companies win.

Run `python run.py discover` to mine public datasets (SimplifyJobs/vanshb03) for
company tokens and grow `data/companies.json` — we then poll those feeds directly.

## Design choices

- **One normalized `Job`** decouples the whole system from any specific ATS —
  adding a source is a single new connector module + one line in
  `pipeline.CONNECTORS`.
- **JSON store, not a DB** — the state file is committed by CI each run, so a
  human-diffable text file beats a binary database here.
- **Fault isolation** — each company is fetched in its own task with its own
  `try/except`; one dead endpoint never breaks a run, and jobs are only marked
  "closed" for companies that fetched successfully.
- **Stable ids** (`<source>:<slug>:<external_id>`) make dedup automatic.

## Workday (enterprise tier) & the optional proxy

Workday is per-tenant (each company has its own host + `site`) and bot-protected.
Discovery extracts tenant/site pairs from public data, limited to a curated set of
desirable tech/finance names. Failures are isolated per company.

Workday blocks **datacenter/cloud IPs** more aggressively than home IPs, so the
GitHub Actions runner may be refused for some tenants. To recover them, set a repo
secret named **`WORKDAY_PROXY`** to a proxy URL (e.g. a cheap residential/rotating
proxy: `http://user:pass@host:port`). The workflow passes it through, and only the
Workday connector uses it. Unset = Workday runs direct (default).

## Running locally

```bash
python -m venv .venv
.\.venv\Scripts\activate        # Windows
pip install -r requirements.txt
python run.py all               # harvest + update
```
