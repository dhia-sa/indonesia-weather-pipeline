from datetime import date

import pytest

from extract.config import load_cities
from extract.transform import flatten_daily, incremental_window, year_chunks

SAMPLE = {
    "latitude": -6.25,
    "longitude": 106.875,
    "elevation": 8.0,
    "daily": {
        "time": ["2024-01-01", "2024-01-02", "2024-01-03"],
        "temperature_2m_max": [31.2, 30.8, None],
        "precipitation_sum": [12.4, 0.0, None],
    },
}


def test_flatten_pivots_arrays_into_rows():
    rows = flatten_daily(SAMPLE, "jakarta")
    assert rows[0]["city_id"] == "jakarta"
    assert rows[0]["weather_date"] == date(2024, 1, 1)
    assert rows[0]["payload"] == {"temperature_2m_max": 31.2, "precipitation_sum": 12.4}
    assert rows[0]["elevation"] == 8.0


def test_flatten_skips_days_not_yet_available():
    rows = flatten_daily(SAMPLE, "jakarta")
    assert [r["weather_date"] for r in rows] == [date(2024, 1, 1), date(2024, 1, 2)]


def test_flatten_keeps_real_zero_values():
    rows = flatten_daily(SAMPLE, "jakarta")
    assert rows[1]["payload"]["precipitation_sum"] == 0.0


def test_flatten_rejects_misaligned_arrays():
    bad = {"daily": {"time": ["2024-01-01", "2024-01-02"], "temperature_2m_max": [30.0]}}
    with pytest.raises(ValueError, match="temperature_2m_max"):
        flatten_daily(bad, "jakarta")


def test_flatten_rejects_missing_daily_block():
    with pytest.raises(ValueError):
        flatten_daily({"error": False}, "jakarta")


def test_year_chunks_split_by_calendar_year():
    assert list(year_chunks(date(2023, 11, 1), date(2025, 2, 10))) == [
        (date(2023, 11, 1), date(2023, 12, 31)),
        (date(2024, 1, 1), date(2024, 12, 31)),
        (date(2025, 1, 1), date(2025, 2, 10)),
    ]


def test_year_chunks_empty_when_start_after_end():
    assert list(year_chunks(date(2025, 1, 2), date(2025, 1, 1))) == []


def test_incremental_window_uses_lookback():
    assert incremental_window(date(2025, 1, 20), date(2025, 1, 25), 10, date(2020, 1, 1)) == (
        date(2025, 1, 10),
        date(2025, 1, 25),
    )


def test_incremental_window_starts_from_default_for_new_city():
    assert incremental_window(None, date(2025, 1, 25), 10, date(2020, 1, 1))[0] == date(2020, 1, 1)


def test_cities_seed_is_valid():
    cities = load_cities()
    assert len({c.city_id for c in cities}) == len(cities)
    for c in cities:
        assert -11 < c.latitude < 6 and 95 < c.longitude < 141  # inside Indonesia
        assert c.timezone in {"Asia/Jakarta", "Asia/Makassar", "Asia/Jayapura"}
