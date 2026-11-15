"""Postgres loading: idempotent upserts into the raw layer + run logging."""

from __future__ import annotations

from datetime import date

import psycopg
from psycopg.types.json import Jsonb

from extract.config import ROOT, db_conninfo

DDL_PATH = ROOT / "sql" / "001_create_raw_tables.sql"

# Idempotent: re-loading the same day never creates duplicates.
# The WHERE clause skips the write when nothing changed, so rows_changed tells us
# how many rows were new or revised by the source.
UPSERT_SQL = """
insert into raw.weather_daily
    (city_id, weather_date, payload, api_latitude, api_longitude, elevation, run_id, loaded_at)
values
    (%(city_id)s, %(weather_date)s, %(payload)s, %(api_latitude)s, %(api_longitude)s,
     %(elevation)s, %(run_id)s, now())
on conflict (city_id, weather_date) do update set
    payload       = excluded.payload,
    api_latitude  = excluded.api_latitude,
    api_longitude = excluded.api_longitude,
    elevation     = excluded.elevation,
    run_id        = excluded.run_id,
    loaded_at     = excluded.loaded_at
where raw.weather_daily.payload is distinct from excluded.payload
"""


def connect() -> psycopg.Connection:
    return psycopg.connect(db_conninfo())


def init_db(conn: psycopg.Connection) -> None:
    conn.execute(DDL_PATH.read_text(encoding="utf-8"))
    conn.commit()


def last_loaded_dates(conn: psycopg.Connection) -> dict[str, date]:
    rows = conn.execute(
        "select city_id, max(weather_date) from raw.weather_daily group by city_id"
    ).fetchall()
    return {city_id: last for city_id, last in rows}


def upsert_rows(conn: psycopg.Connection, rows: list[dict], run_id: int) -> int:
    """Upsert rows; returns how many were inserted or actually changed."""
    if not rows:
        return 0
    params = [{**r, "payload": Jsonb(r["payload"]), "run_id": run_id} for r in rows]
    changed = 0
    with conn.cursor() as cur:
        # executemany batches the statements (few network round trips, fast on cloud DBs).
        # "returning 1" yields a row only for inserted/changed rows, giving an exact count.
        cur.executemany(UPSERT_SQL + "\nreturning 1", params, returning=True)
        while True:
            changed += len(cur.fetchall())
            if not cur.nextset():
                break
    conn.commit()
    return changed


def start_run(conn: psycopg.Connection, mode: str, start: date, end: date, cities: int) -> int:
    run_id = conn.execute(
        """insert into raw.pipeline_runs (mode, start_date, end_date, cities_requested)
           values (%s, %s, %s, %s) returning run_id""",
        (mode, start, end, cities),
    ).fetchone()[0]
    conn.commit()
    return run_id


def finish_run(
    conn: psycopg.Connection,
    run_id: int,
    status: str,
    rows_received: int,
    rows_changed: int,
    error_message: str | None = None,
) -> None:
    conn.rollback()  # clear any failed transaction before logging
    conn.execute(
        """update raw.pipeline_runs
           set finished_at = now(), status = %s, rows_received = %s,
               rows_changed = %s, error_message = %s
           where run_id = %s""",
        (status, rows_received, rows_changed, error_message, run_id),
    )
    conn.commit()
