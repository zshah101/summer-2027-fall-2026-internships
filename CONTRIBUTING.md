# Contributing

The fastest way to help: **add companies.** More companies = more internships.

## Add a company (one line)

1. Find the company's ATS token from their careers "Apply" URL:
   - `boards.greenhouse.io/`**`stripe`** → slug is `stripe`
   - `jobs.lever.co/`**`plaid`** → slug is `plaid`
   - `jobs.ashbyhq.com/`**`openai`** → slug is `openai`
2. Add an entry to [`data/candidates.json`](data/candidates.json):
   ```json
   {"name": "Stripe", "slug": "stripe"}
   ```
3. Re-validate and refresh locally:
   ```bash
   python run.py harvest   # detects which ATS the slug lives on
   python run.py update    # refreshes listings, README, and CSV
   ```
4. Open a pull request.

The harvester auto-detects the ATS (Greenhouse, Lever, Ashby, SmartRecruiters,
Rippling, Workable, Breezy, Recruitee), so you only need the name + slug.
Workday/Oracle tenants need a `wd`/`site` (or `host`/`site`) pair — easiest is
to run `python run.py discover` (it mines them from public datasets), or copy
the shape of an existing entry in `data/companies.json`.

## Run locally

```bash
python -m venv .venv
# Windows:        .\.venv\Scripts\activate
# macOS / Linux:  source .venv/bin/activate
pip install -r requirements.txt
python run.py all      # harvest + update
```

## Tuning what counts as an internship

All the classification (internship / tech / season / category) lives in one
file: [`src/intern_engine/filters.py`](src/intern_engine/filters.py). PRs that
improve precision/recall against real titles are very welcome.

## Improving the sponsorship flags

The 🇺🇸 / 🛂 flags come from
[`src/intern_engine/sponsorship.py`](src/intern_engine/sponsorship.py), which
matches phrases employers actually write. Found a posting it gets wrong? Add
the phrase to the right pattern **with a test** in
`tests/test_sponsorship.py` — precision matters more than recall here.
