# Roadmap & Features

What's built, and what's next. **Want to help? Pick anything under "To build" and open a pull request** (see [CONTRIBUTING.md](CONTRIBUTING.md)).

Difficulty: 🟢 easy · 🟡 medium · 🔴 hard

---

## ✅ Done (working right now)

- [x] Watches **thousands of companies** across **11 job platforms** (Greenhouse, Lever, Ashby, SmartRecruiters, Workday, Oracle, Amazon, Rippling, Workable, Breezy, Recruitee)
- [x] Fetches them all at once (**async**) with auto-retries, backoff, and rate limits
- [x] **Circuit breaker** — dead job boards get quarantined with exponential backoff and retried automatically (no wasted requests, self-healing)
- [x] Finds **brand-new** jobs, removes **duplicates**, and merges every platform into one clean format
- [x] Keeps only **real, dated US tech internships** (Summer 2027 / Fall 2026)
- [x] 🛂 **Visa-sponsorship flags, auto-detected** — reads every matched job's description and marks "no sponsorship" / "US citizens only" (the big lists do this by hand; we compute it)
- [x] **Real posted dates** from Greenhouse `first_published` + Workday detail pages, frozen so they never shift
- [x] **Salary capture** where the ATS exposes it (Ashby / Lever / Breezy) → CSV, API, dashboard
- [x] **Updates itself every 2 hours** via GitHub Actions — no laptop needed
- [x] Auto-builds the **README list** + a **CSV** you can open in Excel/Sheets
- [x] **RSS/Atom feed** (`docs/feed.xml`) — instant alerts in any RSS app, zero infra
- [x] **JSON API** (`docs/api/jobs.json`) — build on the data without scraping
- [x] **Discord alerts** (optional webhook) the moment a run finds new roles
- [x] **Live dashboard** (GitHub Pages) with search, filters, an **"F-1 friendly" toggle**, and a run-history chart
- [x] Saves everything to a real **database** (Postgres / Supabase) with analytics views
- [x] **Quality gate** — hides junk / no-name companies
- [x] **Auto-discovers** new companies weekly from public datasets (both Workday URL shapes, Oracle site numbers, 6 datasets + README mining)
- [x] **Tests** (65) + linting (ruff) + CI so changes don't break things

---

## 🚧 To build (grab one!)

### More jobs (coverage)
- [ ] 🟢 Add more companies — just add names to `data/candidates.json`
- [ ] 🟢 Turn the **International** section back on and tidy it up (already coded, just gated off)
- [ ] 🟢 Add a **"New Grad"** section (not just internships)
- [ ] 🟡 Add more platforms — **Jobvite**, **iCIMS**, or **Eightfold** connectors (copy one in `src/intern_engine/connectors/`)
- [ ] 🔴 Add the big sites (**Google, Microsoft, Apple, TikTok, Tesla**) — they block bots, so this is hard

### Nicer list (presentation)
- [ ] 🟢 Better filters — catch more real tech roles, drop more fakes (`src/intern_engine/filters.py`)
- [ ] 🟢 Show the **salary** column in the README table (already captured in CSV/API/dashboard)
- [ ] 🟢 Add **state / country** tags to each row
- [ ] 🟡 **Trend charts** (which companies post most, % of roles needing Python vs C++, new roles per day)

### AI features 🧠
- [ ] 🟡 **Skill tagger** — AI reads each job and tags the skills it wants (Python, React, SQL…)
- [ ] 🟡 **Resume match** — AI scores how well a job fits your resume (0–100)
- [ ] 🟡 **One-line summaries** — AI writes a quick "what this role actually is"
- [ ] 🔴 **Chat with the jobs (RAG)** — ask in plain English, get answers from our own data

### The F-1 edge 🛂
- [x] ~~Visa-sponsorship tags~~ — **shipped**: auto-detected from posting text (🇺🇸 / 🛂 flags + "F-1 friendly" dashboard filter)
- [ ] 🟡 Cross-check with public **H-1B disclosure data** to also mark "this company has actually sponsored before"

### Alerts 🔔
- [x] ~~RSS feed~~ — **shipped**: `docs/feed.xml` works with any RSS app / Slack / Discord RSS bot
- [x] ~~Discord webhook~~ — **shipped**: set the `DISCORD_WEBHOOK_URL` secret
- [ ] 🟡 **Email alerts** (Resend) the moment a matching role opens
- [ ] 🟡 **SMS** alerts

### The real product 🌐
- [ ] 🟡 **FastAPI** — a simple API to serve the data (`/jobs`, `/companies`, `/stats`)
- [ ] 🔴 **Website** (Next.js) with search + filters + pages
- [ ] 🔴 **User accounts** — save jobs + track applications on a Kanban board

### Under the hood ⚙️
- [ ] 🟡 Put the **database schema in the repo** (so it's version-controlled, not just in Supabase)
- [ ] 🟡 **Conditional requests** (ETag / If-Modified-Since) to skip unchanged boards entirely
- [ ] 🔴 **Task queue** (Celery/Redis) — only if we ever scale way up

---

## 🌟 Good first issues (start here if you're new)
1. **Add companies** to `data/candidates.json`, then run `python run.py harvest` and `python run.py update`.
2. **Improve the filters** in `src/intern_engine/filters.py` (what counts as a tech internship).
3. **Improve the sponsorship classifier** in `src/intern_engine/sponsorship.py` — find a phrasing it misses, add a test, add the pattern.

## How to contribute
Fork → make your change → run `python -m pytest` (all green) → open a PR. Details in [CONTRIBUTING.md](CONTRIBUTING.md). Questions? Open an issue.
