"""Streamlit dashboard on top of the dbt marts.

Run locally:  streamlit run dashboard/app.py
"""

from __future__ import annotations

import os
from datetime import timedelta

import pandas as pd
import psycopg
import streamlit as st
from dotenv import load_dotenv
from psycopg.conninfo import make_conninfo

st.set_page_config(page_title="Indonesia Weather Pipeline", page_icon="🌦️", layout="wide")
load_dotenv()


def _setting(key: str, default: str | None = None) -> str | None:
    """Read from Streamlit Cloud secrets first, then environment / .env."""
    value = None
    try:
        if key in st.secrets:
            value = str(st.secrets[key])
    except Exception:  # no secrets file locally
        pass
    if value is None:
        value = os.getenv(key, default)
    return value.strip() if isinstance(value, str) else value  # stray spaces/newlines break logins


# Either one DATABASE_URL (paste Neon's connection string as-is) or separate DB_* settings.
DATABASE_URL = _setting("DATABASE_URL")
SETTINGS = {
    "DB_HOST": _setting("DB_HOST"),
    "DB_PORT": _setting("DB_PORT", "5432"),
    "DB_NAME": _setting("DB_NAME"),
    "DB_USER": _setting("DB_USER"),
    "DB_PASSWORD": _setting("DB_PASSWORD"),
    "DB_SSLMODE": _setting("DB_SSLMODE", "require"),
}
CONNINFO = DATABASE_URL or make_conninfo(
    host=SETTINGS["DB_HOST"],
    port=SETTINGS["DB_PORT"],
    dbname=SETTINGS["DB_NAME"],
    user=SETTINGS["DB_USER"],
    password=SETTINGS["DB_PASSWORD"],
    sslmode=SETTINGS["DB_SSLMODE"],
)


def check_connection() -> None:
    """Fail with a readable explanation instead of Streamlit's redacted error."""
    try:
        with psycopg.connect(CONNINFO, connect_timeout=20) as conn:
            conn.execute("select 1")
        return
    except psycopg.OperationalError as exc:
        message = str(exc)

    problems = []
    if not DATABASE_URL:
        missing = [k for k in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD") if not SETTINGS[k]]
        if missing:
            problems.append(f"Missing secrets: **{', '.join(missing)}**. Add them in Manage app → Settings → Secrets.")
        host = SETTINGS["DB_HOST"] or ""
        if "://" in host or "/" in host or "@" in host:
            problems.append("`DB_HOST` should be only the host name (from `ep-` to `.neon.tech`), not a full URL.")
        elif host and not host.endswith(".neon.tech"):
            problems.append(f"`DB_HOST` is `{host}` - a Neon host normally ends with `.neon.tech`.")
    for secret in (SETTINGS["DB_PASSWORD"], DATABASE_URL):
        if secret:
            message = message.replace(secret, "****")  # never show the password

    st.error("Can't connect to the database.")
    for p in problems:
        st.markdown(f"- {p}")
    st.code(message, language=None)
    st.stop()


@st.cache_data(ttl=3600, show_spinner=False)
def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    with psycopg.connect(CONNINFO) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d.name for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


# ---------------------------------------------------------------- sidebar
st.title("🌦️ Indonesia Weather Pipeline")
st.caption(
    "Open-Meteo API → Python (GitHub Actions, daily) → Postgres → dbt → Streamlit. "
    "Data: [Open-Meteo](https://open-meteo.com/) (CC BY 4.0)."
)

check_connection()
cities = query(
    "select city_id, city_name, island, first_weather_date, last_weather_date from marts.dim_city order by city_name"
)
if cities["last_weather_date"].isna().all():
    st.warning("No data loaded yet. Run the backfill first: `python -m extract.pipeline backfill`.")
    st.stop()

city_name = st.sidebar.selectbox("City", cities["city_name"], index=int((cities["city_id"] == "jakarta").idxmax()))
city = cities[cities["city_name"] == city_name].iloc[0]

max_date = city["last_weather_date"]
min_date = city["first_weather_date"]
default_start = max(min_date, max_date - timedelta(days=365))
date_range = st.sidebar.date_input("Date range", (default_start, max_date), min_value=min_date, max_value=max_date)
start, end = (date_range if len(date_range) == 2 else (date_range[0], max_date))

tab_city, tab_compare, tab_anomaly, tab_health = st.tabs(
    ["City overview", "Compare cities", "Anomalies", "Pipeline health"]
)

# ---------------------------------------------------------------- city overview
with tab_city:
    daily = query(
        """select weather_date, temp_max_c::float, temp_min_c::float, temp_mean_c::float,
                  precipitation_mm::float, is_rainy_day, rain_intensity, weather_description
           from marts.fct_weather_daily
           where city_id = %s and weather_date between %s and %s
           order by weather_date""",
        (city["city_id"], start, end),
    )
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Avg max temp", f"{daily['temp_max_c'].mean():.1f} °C")
    k2.metric("Total rainfall", f"{daily['precipitation_mm'].sum():,.0f} mm")
    k3.metric("Rainy days", f"{int(daily['is_rainy_day'].sum())} / {len(daily)}")
    k4.metric("Heavy-rain days", int(daily["rain_intensity"].isin(["heavy", "very heavy", "extreme"]).sum()))

    st.subheader("Temperature (°C)")
    st.line_chart(daily.set_index("weather_date")[["temp_max_c", "temp_mean_c", "temp_min_c"]])
    st.subheader("Daily precipitation (mm)")
    st.bar_chart(daily.set_index("weather_date")["precipitation_mm"])

    st.subheader("Monthly summary")
    monthly = query(
        """select month_start, days_observed, avg_temp_max_c::float, avg_temp_min_c::float,
                  total_precipitation_mm::float, rainy_days, heavy_rain_days
           from marts.mart_city_monthly
           where city_id = %s and month_start between date_trunc('month', %s::date) and %s
           order by month_start desc""",
        (city["city_id"], start, end),
    )
    st.dataframe(monthly, hide_index=True, width="stretch")

# ---------------------------------------------------------------- compare
with tab_compare:
    st.subheader("Total rainfall by city and month (mm)")
    compare = query(
        """select c.city_name, m.month_start, m.total_precipitation_mm::float
           from marts.mart_city_monthly m join marts.dim_city c using (city_id)
           where m.month_start between date_trunc('month', %s::date) and %s""",
        (start, end),
    )
    pivot = compare.pivot_table(index="month_start", columns="city_name", values="total_precipitation_mm")
    st.line_chart(pivot)
    st.dataframe(
        compare.groupby("city_name")["total_precipitation_mm"].sum().sort_values(ascending=False).rename("total mm"),
        width="stretch",
    )

# ---------------------------------------------------------------- anomalies
with tab_anomaly:
    st.subheader(f"Most unusual days in {city_name}")
    st.caption("Compared with the city's average for the same month across all loaded years (|z| ≥ 2).")
    anomalies = query(
        """select weather_date, temp_mean_c::float, normal_temp_mean_c::float,
                  temp_anomaly_c::float, temp_zscore::float, precipitation_mm::float, rain_intensity
           from marts.mart_daily_anomaly
           where city_id = %s and weather_date between %s and %s and is_temperature_anomaly
           order by abs(temp_zscore) desc limit 25""",
        (city["city_id"], start, end),
    )
    st.dataframe(anomalies, hide_index=True, width="stretch")

# ---------------------------------------------------------------- pipeline health
with tab_health:
    st.subheader("Data freshness per city")
    st.dataframe(
        query(
            "select city_name, latest_weather_date, days_behind, last_loaded_at "
            "from marts.mart_city_freshness order by city_name"
        ),
        hide_index=True,
        width="stretch",
    )
    st.caption("Archive data normally lags ~5 days behind today.")
    st.subheader("Recent pipeline runs")
    st.dataframe(
        query(
            """select run_id, mode, status, started_at, duration_seconds::float, start_date, end_date,
                      rows_received, rows_changed, error_message
               from marts.mart_pipeline_runs order by run_id desc limit 30"""
        ),
        hide_index=True,
        width="stretch",
    )
