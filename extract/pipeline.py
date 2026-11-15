"""
Command-line entry point.

    python -m extract.pipeline init-db
    python -m extract.pipeline backfill --start 2020-01-01 [--end 2024-12-31] [--cities jakarta,bogor]
    python -m extract.pipeline incremental [--cities jakarta,bogor]
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from extract import client, load
from extract.config import (
    DEFAULT_BACKFILL_START,
    INCREMENTAL_LOOKBACK_DAYS,
    PIPELINE_TIMEZONE,
    REQUEST_PAUSE_SECONDS,
    City,
    load_cities,
)
from extract.transform import flatten_daily, incremental_window, year_chunks

log = logging.getLogger("weather")

Plan = list[tuple[City, date, date]]


def yesterday_local() -> date:
    return datetime.now(ZoneInfo(PIPELINE_TIMEZONE)).date() - timedelta(days=1)


def select_cities(arg: str | None) -> list[City]:
    cities = load_cities()
    if not arg:
        return cities
    wanted = {c.strip() for c in arg.split(",")}
    unknown = wanted - {c.city_id for c in cities}
    if unknown:
        raise SystemExit(f"Unknown city_id(s): {', '.join(sorted(unknown))}")
    return [c for c in cities if c.city_id in wanted]


def execute(conn, mode: str, plan: Plan) -> int:
    """Fetch + load every (city, start, end) request. Returns a process exit code."""
    if not plan:
        log.info("Nothing to load - already up to date.")
        return 0

    run_id = load.start_run(
        conn, mode, min(p[1] for p in plan), max(p[2] for p in plan), len({p[0].city_id for p in plan})
    )
    log.info("Run %s started: %s request(s)", run_id, len(plan))

    session = client.build_session()
    received = changed = 0
    errors: list[str] = []

    for city, start, end in plan:
        try:
            response = client.fetch_daily(session, city, start, end)
            rows = flatten_daily(response, city.city_id)
            n_changed = load.upsert_rows(conn, rows, run_id)
            received += len(rows)
            changed += n_changed
            log.info("%-12s %s..%s  received=%-4s changed=%s", city.city_id, start, end, len(rows), n_changed)
        except Exception as exc:  # keep going for other cities, but record the failure
            conn.rollback()
            log.error("%s %s..%s failed: %s", city.city_id, start, end, exc)
            errors.append(f"{city.city_id} {start}..{end}: {exc}")
        time.sleep(REQUEST_PAUSE_SECONDS)

    if not errors:
        status = "success"
    elif len(errors) < len(plan):
        status = "partial_failure"
    else:
        status = "failed"
    load.finish_run(conn, run_id, status, received, changed, "\n".join(errors)[:4000] or None)
    log.info("Run %s finished: %s (received=%s, changed=%s)", run_id, status, received, changed)
    return 0 if status == "success" else 1  # non-zero exit makes GitHub Actions fail loudly


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Open-Meteo -> Postgres loader")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db", help="create raw schema and tables (safe to re-run)")

    bf = sub.add_parser("backfill", help="load a historical date range")
    bf.add_argument("--start", type=date.fromisoformat, default=DEFAULT_BACKFILL_START)
    bf.add_argument("--end", type=date.fromisoformat, default=None)
    bf.add_argument("--cities", help="comma-separated city_ids (default: all)")

    inc = sub.add_parser("incremental", help="load new days since the last run")
    inc.add_argument("--lookback-days", type=int, default=INCREMENTAL_LOOKBACK_DAYS)
    inc.add_argument("--cities", help="comma-separated city_ids (default: all)")

    args = parser.parse_args(argv)

    with load.connect() as conn:
        load.init_db(conn)
        if args.command == "init-db":
            log.info("Raw tables are ready.")
            return 0

        cities = select_cities(args.cities)
        yesterday = yesterday_local()

        if args.command == "backfill":
            end = min(args.end or yesterday, yesterday)
            plan = [(c, s, e) for c in cities for s, e in year_chunks(args.start, end)]
            return execute(conn, "backfill", plan)

        last = load.last_loaded_dates(conn)
        plan = []
        for c in cities:
            window = incremental_window(last.get(c.city_id), yesterday, args.lookback_days, DEFAULT_BACKFILL_START)
            if window:
                plan.extend((c, s, e) for s, e in year_chunks(*window))
        return execute(conn, "incremental", plan)


if __name__ == "__main__":
    sys.exit(main())
