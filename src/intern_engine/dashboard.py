"""Generate a self-contained metrics + listings dashboard for GitHub Pages.

Writes docs/index.html with the run metrics and current open roles baked in (no
external fetches, so it works the moment Pages serves it). Regenerated every run.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from html import escape

from . import config, paths


def _cards(stats: dict) -> str:
    latency = stats.get("detection_latency") or {}
    lat = (
        f"{latency['median_minutes']:.0f} min"
        if latency.get("median_minutes") is not None and latency.get("sample_size", 0) >= 5
        else "calibrating"
    )
    items = [
        ("Open roles", stats.get("open_total", 0)),
        ("Companies tracked", f"{stats.get('companies_total', 0):,}"),
        ("ATS sources", len(stats.get("companies_by_source", {}))),
        ("Fetch success", f"{int(stats.get('fetch_success_rate', 0) * 100)}%"),
        ("New this run", stats.get("new_this_run", 0)),
        ("Detection latency", lat),
        ("Last run", f"{stats.get('duration_seconds', 0)}s"),
    ]
    return "".join(
        f'<div class="card"><div class="num">{escape(str(v))}</div>'
        f'<div class="lbl">{escape(label)}</div></div>'
        for label, v in items
    )


def _bars(counter: dict) -> str:
    if not counter:
        return "<p class='muted'>none</p>"
    top = max(counter.values())
    rows = []
    for name, n in sorted(counter.items(), key=lambda kv: -kv[1]):
        pct = int(n / top * 100) if top else 0
        rows.append(
            f'<div class="bar"><span class="bname">{escape(str(name))}</span>'
            f'<span class="btrack"><span class="bfill" style="width:{pct}%"></span></span>'
            f'<span class="bval">{n}</span></div>'
        )
    return "".join(rows)


def _rows(open_jobs: list[dict]) -> str:
    rows = []
    for r in open_jobs:
        posted = (r.get("posted_at") or "")[:10] or "—"
        url = r.get("url") or ""
        apply = f'<a href="{escape(url)}" target="_blank" rel="noopener">Apply</a>' if url else "—"
        rows.append(
            "<tr>"
            f"<td>{escape(r.get('company', ''))}</td>"
            f"<td>{escape(r.get('title', ''))}</td>"
            f"<td><span class='tag'>{escape(r.get('season', ''))}</span></td>"
            f"<td>{escape(r.get('category', ''))}</td>"
            f"<td>{escape((r.get('location') or '')[:48])}</td>"
            f"<td>{escape(posted)}</td>"
            f"<td>{apply}</td>"
            "</tr>"
        )
    return "".join(rows)


def generate(store_data: dict, stats: dict) -> None:
    open_jobs = [r for r in store_data.values() if r.get("is_open")]
    open_jobs.sort(
        key=lambda r: ((r.get("posted_at") or "")[:10], (r.get("first_seen_at") or "")),
        reverse=True,
    )
    cfg = config.load_config()
    updated = datetime.now(UTC).strftime("%b %d, %Y at %H:%M UTC")
    region = "United States" if config.want_us(cfg) else "Worldwide"

    html_doc = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Internship Engine - Live Dashboard</title>
<style>
  :root {{ --bg:#0d1117; --card:#161b22; --line:#30363d; --txt:#e6edf3;
           --muted:#8b949e; --accent:#2f81f7; --green:#3fb950; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--txt);
          font:15px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif; }}
  .wrap {{ max-width:1040px; margin:0 auto; padding:32px 20px 64px; }}
  h1 {{ font-size:26px; margin:0 0 4px; }}
  .sub {{ color:var(--muted); margin:0 0 24px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
           gap:12px; margin-bottom:28px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:10px;
           padding:16px; }}
  .num {{ font-size:24px; font-weight:700; }}
  .lbl {{ color:var(--muted); font-size:13px; margin-top:2px; }}
  h2 {{ font-size:16px; margin:26px 0 10px; }}
  .panels {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; }}
  @media(max-width:680px) {{ .panels {{ grid-template-columns:1fr; }} }}
  .bar {{ display:flex; align-items:center; gap:10px; margin:6px 0; font-size:13px; }}
  .bname {{ width:120px; color:var(--muted); }}
  .btrack {{ flex:1; height:8px; background:#21262d; border-radius:6px; overflow:hidden; }}
  .bfill {{ display:block; height:100%; background:var(--accent); }}
  .bval {{ width:36px; text-align:right; }}
  table {{ width:100%; border-collapse:collapse; margin-top:8px; font-size:13.5px; }}
  th,td {{ text-align:left; padding:8px 10px; border-bottom:1px solid var(--line);
           vertical-align:top; }}
  th {{ color:var(--muted); font-weight:600; }}
  a {{ color:var(--accent); text-decoration:none; }}
  a:hover {{ text-decoration:underline; }}
  .tag {{ background:#1f6feb22; color:#79c0ff; padding:1px 7px; border-radius:20px; font-size:12px; }}
  .muted {{ color:var(--muted); }}
  footer {{ color:var(--muted); font-size:12px; margin-top:36px; }}
</style></head><body><div class="wrap">
  <h1>Internship Engine - Live Dashboard</h1>
  <p class="sub">{region} tech internships, refreshed automatically. Updated {escape(updated)}.</p>
  <div class="grid">{_cards(stats)}</div>
  <div class="panels">
    <div><h2>Roles by source</h2>{_bars(stats.get("roles_by_source", {}))}</div>
    <div><h2>Roles by cycle</h2>{_bars(stats.get("roles_by_cycle", {}))}</div>
  </div>
  <h2>Open roles ({len(open_jobs)})</h2>
  <table><thead><tr><th>Company</th><th>Role</th><th>Cycle</th><th>Category</th>
  <th>Location</th><th>Posted</th><th></th></tr></thead>
  <tbody>{_rows(open_jobs)}</tbody></table>
  <footer>Generated by the engine on each run. Companies polled across
  {len(stats.get("companies_by_source", {}))} ATS platforms.</footer>
</div></body></html>"""

    os.makedirs(paths.DOCS_DIR, exist_ok=True)
    with open(paths.DASHBOARD_PATH, "w", encoding="utf-8") as f:
        f.write(html_doc)
