"""Central configuration: API settings, variables, cities and DB connection."""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from psycopg.conninfo import make_conninfo

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]

# Cities live in the dbt seed so Python and dbt share ONE source of truth.
CITIES_CSV = ROOT / "dbt" / "seeds" / "cities.csv"

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Daily variables from the Open-Meteo Historical Weather API.
# Units (API defaults): temperatures °C, precipitation mm, durations seconds,
# wind km/h, radiation MJ/m², precipitation_hours hours.
DAILY_VARIABLES: list[str] = [
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "apparent_temperature_max",
    "apparent_temperature_min",
    "precipitation_sum",
    "rain_sum",
    "precipitation_hours",
    "sunshine_duration",
    "daylight_duration",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "wind_direction_10m_dominant",
    "shortwave_radiation_sum",
    "et0_fao_evapotranspiration",
]

DEFAULT_BACKFILL_START = date(2020, 1, 1)

# Archive (ERA5) data arrives with a ~5-day delay and recent values can be revised,
# so every incremental run re-reads this many days before the latest loaded date.
INCREMENTAL_LOOKBACK_DAYS = int(os.getenv("INCREMENTAL_LOOKBACK_DAYS", "10"))

# Be polite to the free API.
REQUEST_PAUSE_SECONDS = float(os.getenv("REQUEST_PAUSE_SECONDS", "0.5"))

PIPELINE_TIMEZONE = "Asia/Jakarta"


@dataclass(frozen=True)
class City:
    city_id: str
    city_name: str
    province: str
    latitude: float
    longitude: float
    timezone: str


def load_cities(path: Path = CITIES_CSV) -> list[City]:
    with path.open(newline="", encoding="utf-8") as f:
        return [
            City(
                city_id=row["city_id"],
                city_name=row["city_name"],
                province=row["province"],
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
                timezone=row["timezone"],
            )
            for row in csv.DictReader(f)
        ]


def db_conninfo() -> str:
    """Build a Postgres connection string from environment variables (.env locally,
    GitHub Secrets in Actions)."""
    missing = [v for v in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD") if not os.getenv(v)]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)} (see .env.example)")
    return make_conninfo(
        host=os.environ["DB_HOST"],
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        sslmode=os.getenv("DB_SSLMODE", "require"),
    )
