"""Turn the API's column-oriented response into one row per city per day."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta


def flatten_daily(response: dict, city_id: str) -> list[dict]:
    """
    Open-Meteo returns daily data as parallel arrays:
        {"daily": {"time": ["2024-01-01", ...], "temperature_2m_max": [31.2, ...], ...}}
    We pivot it into rows. The per-day values are kept as a JSON payload (raw layer);
    typing and renaming happens later in dbt staging.

    Days where every variable is null (not yet available in the archive) are skipped,
    so they get picked up by a later incremental run instead of being stored as empty.
    """
    daily = response.get("daily") or {}
    times = daily.get("time")
    if times is None:
        raise ValueError(f"{city_id}: response has no daily.time array")

    variables = [k for k in daily if k != "time"]
    for var in variables:
        if len(daily[var]) != len(times):
            raise ValueError(f"{city_id}: '{var}' has {len(daily[var])} values but {len(times)} dates")

    rows: list[dict] = []
    for i, day in enumerate(times):
        values = {var: daily[var][i] for var in variables}
        if all(v is None for v in values.values()):
            continue
        rows.append(
            {
                "city_id": city_id,
                "weather_date": date.fromisoformat(day),
                "payload": values,
                "api_latitude": response.get("latitude"),
                "api_longitude": response.get("longitude"),
                "elevation": response.get("elevation"),
            }
        )
    return rows


def year_chunks(start: date, end: date) -> Iterator[tuple[date, date]]:
    """Split a long backfill range into calendar-year requests."""
    if start > end:
        return
    for year in range(start.year, end.year + 1):
        yield max(start, date(year, 1, 1)), min(end, date(year, 12, 31))


def incremental_window(
    last_loaded: date | None, yesterday: date, lookback_days: int, default_start: date
) -> tuple[date, date] | None:
    """Date range for an incremental run, or None if there is nothing to fetch."""
    start = default_start if last_loaded is None else last_loaded - timedelta(days=lookback_days)
    return (start, yesterday) if start <= yesterday else None
