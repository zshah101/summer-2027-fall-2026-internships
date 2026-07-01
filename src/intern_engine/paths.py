"""Central place for every file path, computed from the repo root.

Everything is relative to this file's location, so the project works the same
on your laptop and inside GitHub Actions, regardless of the current directory.
"""

import os

# .../src/intern_engine/paths.py  ->  repo root is two levels up.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

DATA_DIR = os.path.join(ROOT, "data")

CONFIG_PATH = os.path.join(DATA_DIR, "config.json")          # tunable settings
BLOCKLIST_PATH = os.path.join(DATA_DIR, "blocklist.json")    # companies to exclude
CANDIDATES_PATH = os.path.join(DATA_DIR, "candidates.json")  # raw slugs to probe
COMPANIES_PATH = os.path.join(DATA_DIR, "companies.json")    # validated companies
JOBS_PATH = os.path.join(DATA_DIR, "jobs.json")              # persistent job state
CSV_PATH = os.path.join(DATA_DIR, "internships.csv")         # downloadable tracker
STATS_PATH = os.path.join(DATA_DIR, "stats.json")            # last-run metrics
HEALTH_PATH = os.path.join(DATA_DIR, "health.json")          # circuit-breaker state
HISTORY_PATH = os.path.join(DATA_DIR, "history.jsonl")       # one line of metrics per run

README_PATH = os.path.join(ROOT, "README.md")
DOCS_DIR = os.path.join(ROOT, "docs")
DASHBOARD_PATH = os.path.join(DOCS_DIR, "index.html")        # GitHub Pages dashboard
FEED_PATH = os.path.join(DOCS_DIR, "feed.xml")               # Atom feed (new roles)
API_DIR = os.path.join(DOCS_DIR, "api")                      # static JSON API
