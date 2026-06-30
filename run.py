"""Command-line entrypoint.

    python run.py harvest    # probe curated candidates -> data/companies.json
    python run.py discover   # mine public datasets for company tokens (big scale-up)
    python run.py update     # fetch -> filter -> store -> regenerate README + CSV
    python run.py all        # discover + harvest + update
"""

import os
import sys

# Make the package under src/ importable without installation.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from intern_engine import (  # noqa: E402
    dashboard,
    discover,
    harvester,
    pipeline,
    readme,
)


def cmd_harvest() -> None:
    found, candidates = harvester.harvest()
    print(f"Harvested {len(found)}/{len(candidates)} candidates -> data/companies.json")
    by_ats: dict[str, int] = {}
    for c in found:
        by_ats[c["ats"]] = by_ats.get(c["ats"], 0) + 1
    for ats, n in sorted(by_ats.items()):
        print(f"  {ats:<12} {n}")


def cmd_discover() -> None:
    companies, n_found = discover.discover()
    print(f"Discovered {n_found} tokens from public datasets.")
    print(f"Company list now has {len(companies)} companies -> data/companies.json")
    by_ats: dict[str, int] = {}
    for c in companies:
        by_ats[c["ats"]] = by_ats.get(c["ats"], 0) + 1
    for ats, n in sorted(by_ats.items()):
        print(f"  {ats:<12} {n}")


def cmd_update() -> None:
    if not os.path.exists(os.path.join("data", "companies.json")):
        print("No data/companies.json yet — run `python run.py harvest` first.")
        sys.exit(1)
    stats, store_data = pipeline.run_update()
    summary = readme.generate(store_data)
    dashboard.generate(store_data, stats)
    print("Update complete:")
    for k, v in stats.items():
        print(f"  {k:<20} {v}")
    print(f"  README open roles    {summary['open']}")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "update"
    if cmd == "harvest":
        cmd_harvest()
    elif cmd == "discover":
        cmd_discover()
    elif cmd == "update":
        cmd_update()
    elif cmd == "all":
        cmd_discover()
        cmd_harvest()
        cmd_update()
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
