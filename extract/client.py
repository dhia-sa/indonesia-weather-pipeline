"""Thin HTTP client for the Open-Meteo Historical Weather API."""

from __future__ import annotations

from datetime import date

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from extract.config import ARCHIVE_URL, DAILY_VARIABLES, City


class OpenMeteoError(RuntimeError):
    """The API answered, but with an error (e.g. invalid parameter)."""


def build_session() -> requests.Session:
    # Retry transient failures (rate limit / server errors) with exponential backoff.
    retry = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers["User-Agent"] = "indonesia-weather-pipeline (portfolio project)"
    return session


def fetch_daily(session: requests.Session, city: City, start: date, end: date) -> dict:
    """Fetch daily weather for one city and date range. Returns the raw JSON response."""
    params = {
        "latitude": city.latitude,
        "longitude": city.longitude,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": ",".join(DAILY_VARIABLES),
        "timezone": city.timezone,  # required when requesting daily data
    }
    response = session.get(ARCHIVE_URL, params=params, timeout=60)

    if response.status_code == 400:
        raise OpenMeteoError(f"{city.city_id}: {response.json().get('reason', response.text)}")
    response.raise_for_status()

    data = response.json()
    if data.get("error"):
        raise OpenMeteoError(f"{city.city_id}: {data.get('reason')}")
    return data
