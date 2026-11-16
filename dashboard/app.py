"""Streamlit dashboard on top of the dbt marts.

Run locally:  streamlit run dashboard/app.py
"""

from __future__ import annotations

import os
from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go
import psycopg
import streamlit as st
from dotenv import load_dotenv
from psycopg.conninfo import make_conninfo

st.set_page_config(page_title="Indonesia Weather", page_icon="🌦️", layout="wide")
load_dotenv()


# ============================================================ connection
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


# ============================================================ look & feel
ICONS = {
    0: "☀️", 1: "🌤️", 2: "⛅", 3: "☁️", 45: "🌫️", 48: "🌫️",
    51: "🌦️", 53: "🌦️", 55: "🌦️", 56: "🌦️", 57: "🌦️",
    61: "🌧️", 63: "🌧️", 65: "🌧️", 66: "🌧️", 67: "🌧️",
    80: "🌦️", 81: "🌧️", 82: "🌧️", 95: "⛈️", 96: "⛈️", 99: "⛈️",
}
# Hero background changes with the weather, like a weather app.
THEMES = {
    "Clear": "linear-gradient(135deg,#f59e0b 0%,#f97316 45%,#0ea5e9 100%)",
    "Cloudy": "linear-gradient(135deg,#38bdf8 0%,#64748b 60%,#334155 100%)",
    "Fog": "linear-gradient(135deg,#94a3b8 0%,#64748b 50%,#475569 100%)",
    "Drizzle": "linear-gradient(135deg,#60a5fa 0%,#3b82f6 50%,#1e3a8a 100%)",
    "Rain showers": "linear-gradient(135deg,#3b82f6 0%,#1d4ed8 50%,#1e1b4b 100%)",
    "Rain": "linear-gradient(135deg,#2563eb 0%,#1e3a8a 55%,#0f172a 100%)",
    "Thunderstorm": "linear-gradient(135deg,#7c3aed 0%,#4c1d95 50%,#0f172a 100%)",
}
ACCENT = {"temp_max": "#f97316", "temp_min": "#38bdf8", "rain": "#3b82f6", "mean": "#fbbf24"}


def icon(code) -> str:
    return ICONS.get(int(code), "🌡️") if pd.notna(code) else "🌡️"


def compass(deg) -> str:
    if pd.isna(deg):
        return "-"
    return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][int((float(deg) + 22.5) // 45) % 8]


st.markdown(
    """
<style>
.block-container {padding-top: 2rem; max-width: 1400px;}
.hero {border-radius: 24px; padding: 28px 32px; color: #fff; min-height: 340px;
       box-shadow: 0 20px 40px -12px rgba(0,0,0,.45); position: relative; overflow: hidden;}
.hero:after {content:""; position:absolute; right:-80px; top:-80px; width:260px; height:260px;
       border-radius:50%; background:rgba(255,255,255,.12);}
.hero .place {font-size: 1.6rem; font-weight: 700; margin: 0;}
.hero .sub {opacity: .85; font-size: .95rem;}
.hero .temp {font-size: 5.2rem; font-weight: 800; line-height: 1; margin: 18px 0 6px;}
.hero .icon {font-size: 4.2rem; position: absolute; right: 36px; top: 70px; z-index: 1;}
.hero .desc {font-size: 1.25rem; font-weight: 600;}
.hero .meta {display:flex; gap:22px; flex-wrap:wrap; margin-top:18px; font-size:.95rem; opacity:.95;}
.tile {background: rgba(148,163,184,.10); border: 1px solid rgba(148,163,184,.18);
       border-radius: 18px; padding: 16px 18px; height: 100%;}
.tile .label {font-size: .78rem; text-transform: uppercase; letter-spacing: .06em; opacity: .7;}
.tile .value {font-size: 1.6rem; font-weight: 700; margin-top: 4px;}
.tile .hint {font-size: .8rem; opacity: .65; margin-top: 2px;}
.strip {display:grid; grid-template-columns: repeat(7, minmax(0,1fr)); gap: 10px;}
.day {background: rgba(148,163,184,.10); border: 1px solid rgba(148,163,184,.18);
      border-radius: 16px; padding: 12px 6px; text-align: center;}
.day.today {background: rgba(59,130,246,.25); border-color: rgba(59,130,246,.6);}
.day .dname {font-size: .8rem; opacity: .75; font-weight: 600;}
.day .dicon {font-size: 1.9rem; margin: 6px 0;}
.day .dmax {font-weight: 700;} .day .dmin {opacity: .6;}
.day .drain {font-size: .78rem; color: #60a5fa; margin-top: 4px;}
.sunbar {height: 10px; border-radius: 999px; background: rgba(148,163,184,.25); overflow: hidden; margin-top: 10px;}
.sunbar > div {height: 100%; border-radius: 999px; background: linear-gradient(90deg,#fde047,#f97316);}
.section {font-size: 1.15rem; font-weight: 700; margin: 26px 0 10px;}
@media (max-width: 800px) {.strip {grid-template-columns: repeat(4, minmax(0,1fr));} .hero .temp {font-size: 4rem;}}
</style>
""",
    unsafe_allow_html=True,
)


def tile(label: str, value: str, hint: str = "") -> str:
    return f'<div class="tile"><div class="label">{label}</div><div class="value">{value}</div><div class="hint">{hint}</div></div>'


def style_fig(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(
        template="plotly_dark", height=height, margin=dict(l=10, r=10, t=50, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="top", y=-0.12, x=0),
        title=dict(x=0.01, y=0.97, font=dict(size=15)),
        hovermode="x unified", font=dict(family="Inter, sans-serif"),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(148,163,184,.15)")
    return fig


# ============================================================ data
check_connection()
cities = query(
    "select city_id, city_name, province, island, latitude::float, longitude::float, "
    "first_weather_date, last_weather_date from marts.dim_city order by city_name"
)
if cities["last_weather_date"].isna().all():
    st.warning("No data loaded yet. Run the backfill first: `python -m extract.pipeline backfill`.")
    st.stop()

st.sidebar.markdown("## 🌦️ Indonesia Weather")
default_idx = int((cities["city_id"] == "jakarta").idxmax())
city_name = st.sidebar.selectbox("City", cities["city_name"], index=default_idx)
city = cities[cities["city_name"] == city_name].iloc[0]
max_date, min_date = city["last_weather_date"], city["first_weather_date"]
date_range = st.sidebar.date_input(
    "Date range", (max(min_date, max_date - timedelta(days=365)), max_date), min_value=min_date, max_value=max_date
)
start, end = date_range if len(date_range) == 2 else (date_range[0], max_date)
st.sidebar.caption(
    "Daily data from the Open-Meteo archive (about 5 days behind today). "
    "Pipeline: API → Python → Postgres → dbt → Streamlit, refreshed daily by GitHub Actions."
)
st.sidebar.markdown("[📂 Source code](https://github.com/dhia-sa/indonesia-weather-pipeline) · [🌐 Portfolio](https://dhia-sa.github.io)")

daily = query(
    """select weather_date, temp_max_c::float, temp_min_c::float, temp_mean_c::float,
              feels_like_max_c::float, precipitation_mm::float, precipitation_hours::float,
              is_rainy_day, rain_intensity, sunshine_hours::float, daylight_hours::float,
              wind_speed_max_kmh::float, wind_gusts_max_kmh::float, wind_direction_deg,
              solar_radiation_mj_m2::float, evapotranspiration_mm::float,
              weather_code, weather_description, weather_category
       from marts.fct_weather_daily
       where city_id = %s and weather_date between %s and %s
       order by weather_date""",
    (city["city_id"], start, end),
)
if daily.empty:
    st.info("No data in this date range.")
    st.stop()
latest = daily.iloc[-1]

# ============================================================ hero + map
left, right = st.columns([1.15, 1], gap="large")
with left:
    theme = THEMES.get(latest["weather_category"], THEMES["Cloudy"])
    st.markdown(
        f"""
<div class="hero" style="background:{theme}">
  <p class="place">📍 {city['city_name']}</p>
  <div class="sub">{city['province']} · {city['island']} · {latest['weather_date']:%A, %d %B %Y}</div>
  <div class="icon">{icon(latest['weather_code'])}</div>
  <div class="temp">{latest['temp_max_c']:.0f}°</div>
  <div class="desc">{latest['weather_description'] or '-'}</div>
  <div class="sub">Low {latest['temp_min_c']:.0f}° · Feels like {latest['feels_like_max_c']:.0f}°</div>
  <div class="meta">
    <span>💧 {latest['precipitation_mm']:.1f} mm</span>
    <span>💨 {latest['wind_speed_max_kmh']:.0f} km/h {compass(latest['wind_direction_deg'])}</span>
    <span>☀️ {latest['sunshine_hours']:.1f} h sun</span>
  </div>
</div>""",
        unsafe_allow_html=True,
    )

with right:
    latest_all = query(
        """select c.city_name, c.latitude::float, c.longitude::float, f.temp_max_c::float,
                  f.precipitation_mm::float, f.weather_description
           from marts.dim_city c
           join marts.fct_weather_daily f on f.city_id = c.city_id and f.weather_date = c.last_weather_date"""
    )
    latest_all["size"] = latest_all["city_name"].eq(city_name).map({True: 22, False: 13})
    fig = go.Figure(
        go.Scattergeo(
            lat=latest_all["latitude"], lon=latest_all["longitude"], mode="markers+text",
            text=latest_all["city_name"], textposition="top center", textfont=dict(color="#e2e8f0", size=11),
            marker=dict(size=latest_all["size"], color=latest_all["temp_max_c"], colorscale="Turbo", cmin=24, cmax=36,
                        line=dict(width=1.5, color="#0b1220"), showscale=True,
                        colorbar=dict(title="°C", thickness=10, len=0.6, tickfont=dict(color="#cbd5e1"))),
            customdata=latest_all[["temp_max_c", "precipitation_mm", "weather_description"]],
            hovertemplate="<b>%{text}</b><br>Max %{customdata[0]:.1f}°C<br>"
                          "Rain %{customdata[1]:.1f} mm<br>%{customdata[2]}<extra></extra>",
        )
    )
    fig.update_geos(
        projection_type="mercator", lonaxis_range=[94, 142], lataxis_range=[-11.5, 7.5],
        showland=True, landcolor="#1e293b", showocean=True, oceancolor="#0b1220",
        showcountries=True, countrycolor="#334155", showcoastlines=True, coastlinecolor="#475569",
        showlakes=False, bgcolor="rgba(0,0,0,0)", resolution=50,
    )
    fig.update_layout(height=340, margin=dict(l=0, r=0, t=30, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      title=dict(text="Latest max temperature by city", font=dict(color="#e2e8f0", size=14), x=0.01))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

# ============================================================ tiles
period = daily
heavy = int(period["rain_intensity"].isin(["heavy", "very heavy", "extreme"]).sum())
sun_ratio = latest["sunshine_hours"] / latest["daylight_hours"] if latest["daylight_hours"] else 0
cols = st.columns(4)
cols[0].markdown(tile("Rain (latest day)", f"{latest['precipitation_mm']:.1f} mm",
                      f"{latest['precipitation_hours']:.0f} h of rain · daily total: {latest['rain_intensity']}"), unsafe_allow_html=True)
cols[1].markdown(tile("Wind", f"{latest['wind_speed_max_kmh']:.0f} km/h",
                      f"from {compass(latest['wind_direction_deg'])} · gusts {latest['wind_gusts_max_kmh']:.0f} km/h"),
                 unsafe_allow_html=True)
cols[2].markdown(
    f'<div class="tile"><div class="label">Sunshine</div><div class="value">{latest["sunshine_hours"]:.1f} h</div>'
    f'<div class="hint">of {latest["daylight_hours"]:.1f} h daylight</div>'
    f'<div class="sunbar"><div style="width:{min(sun_ratio, 1) * 100:.0f}%"></div></div></div>',
    unsafe_allow_html=True,
)
cols[3].markdown(tile("Solar radiation", f"{latest['solar_radiation_mj_m2']:.1f} MJ/m²",
                      f"evapotranspiration {latest['evapotranspiration_mm']:.1f} mm"), unsafe_allow_html=True)

st.write("")
cols = st.columns(4)
cols[0].markdown(tile("Avg max temp · period", f"{period['temp_max_c'].mean():.1f}°C",
                      f"hottest {period['temp_max_c'].max():.1f}°C"), unsafe_allow_html=True)
cols[1].markdown(tile("Total rainfall · period", f"{period['precipitation_mm'].sum():,.0f} mm",
                      f"wettest day {period['precipitation_mm'].max():.0f} mm"), unsafe_allow_html=True)
cols[2].markdown(tile("Rainy days · period", f"{int(period['is_rainy_day'].sum())} / {len(period)}",
                      f"{period['is_rainy_day'].mean() * 100:.0f}% of days"), unsafe_allow_html=True)
cols[3].markdown(tile("Heavy-rain days · period", f"{heavy}", "≥ 50 mm in a day"), unsafe_allow_html=True)

# ============================================================ 7-day strip
st.markdown('<div class="section">Last 7 days</div>', unsafe_allow_html=True)
week = daily.tail(7)
cards = "".join(
    f'<div class="day{" today" if i == len(week) - 1 else ""}">'
    f'<div class="dname">{r.weather_date:%a %d}</div><div class="dicon">{icon(r.weather_code)}</div>'
    f'<div><span class="dmax">{r.temp_max_c:.0f}°</span> <span class="dmin">{r.temp_min_c:.0f}°</span></div>'
    f'<div class="drain">💧 {r.precipitation_mm:.1f} mm</div></div>'
    for i, r in enumerate(week.itertuples())
)
st.markdown(f'<div class="strip">{cards}</div>', unsafe_allow_html=True)

# ============================================================ tabs
st.write("")
tab_trend, tab_climate, tab_compare, tab_anomaly, tab_health = st.tabs(
    ["📈 Trends", "🗓️ Climate", "🏙️ Compare cities", "⚠️ Anomalies", "🛠️ Pipeline health"]
)

with tab_trend:
    roll = daily.set_index("weather_date")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=roll.index, y=roll["temp_max_c"], name="Max", line=dict(color=ACCENT["temp_max"], width=1.5)))
    fig.add_trace(go.Scatter(x=roll.index, y=roll["temp_min_c"], name="Min", line=dict(color=ACCENT["temp_min"], width=1.5),
                             fill="tonexty", fillcolor="rgba(249,115,22,.12)"))
    fig.add_trace(go.Scatter(x=roll.index, y=roll["temp_mean_c"].rolling(7, min_periods=1).mean(), name="7-day mean",
                             line=dict(color=ACCENT["mean"], width=3)))
    fig.add_trace(go.Bar(x=roll.index, y=roll["precipitation_mm"], name="Rain (mm)", yaxis="y2",
                         marker_color=ACCENT["rain"], opacity=0.55))
    fig.update_layout(
        yaxis=dict(title="°C"),
        yaxis2=dict(title="mm", overlaying="y", side="right", showgrid=False, rangemode="tozero"),
        title="Temperature range & daily rainfall",
    )
    st.plotly_chart(style_fig(fig, 420), width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        mix = daily["rain_intensity"].value_counts().reindex(
            ["no rain", "light", "moderate", "heavy", "very heavy", "extreme"]).dropna()
        fig = go.Figure(go.Pie(labels=mix.index, values=mix.values, hole=0.6, sort=False,
                               marker=dict(colors=["#475569", "#93c5fd", "#3b82f6", "#1d4ed8", "#7c3aed", "#db2777"])))
        fig.update_layout(title="Days by rain intensity", hovermode=False)
        st.plotly_chart(style_fig(fig, 340), width="stretch")
    with c2:
        cond = daily["weather_category"].fillna("Unknown").value_counts()
        fig = go.Figure(go.Bar(x=cond.values, y=cond.index, orientation="h", marker_color="#38bdf8",
                               text=cond.values, textposition="outside", cliponaxis=False))
        fig.update_layout(title="Days by weather type", hovermode=False, yaxis=dict(autorange="reversed"),
                          xaxis=dict(range=[0, cond.max() * 1.15]))
        st.plotly_chart(style_fig(fig, 340), width="stretch")

with tab_climate:
    monthly = query(
        """select year, month, total_precipitation_mm::float, avg_temp_max_c::float, rainy_days
           from marts.mart_city_monthly where city_id = %s order by year, month""",
        (city["city_id"],),
    )
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    c1, c2 = st.columns(2)
    with c1:
        grid = monthly.pivot(index="year", columns="month", values="total_precipitation_mm").reindex(columns=range(1, 13))
        fig = go.Figure(go.Heatmap(z=grid.values, x=months, y=grid.index.astype(str), colorscale="Blues",
                                   colorbar=dict(title="mm"), hovertemplate="%{y} %{x}: %{z:.0f} mm<extra></extra>"))
        fig.update_layout(title=f"Monthly rainfall · {city_name}", hovermode=False)
        st.plotly_chart(style_fig(fig, 380), width="stretch")
    with c2:
        grid = monthly.pivot(index="year", columns="month", values="avg_temp_max_c").reindex(columns=range(1, 13))
        fig = go.Figure(go.Heatmap(z=grid.values, x=months, y=grid.index.astype(str), colorscale="YlOrRd",
                                   colorbar=dict(title="°C"), hovertemplate="%{y} %{x}: %{z:.1f}°C<extra></extra>"))
        fig.update_layout(title=f"Average max temperature · {city_name}", hovermode=False)
        st.plotly_chart(style_fig(fig, 380), width="stretch")
    st.caption("Indonesia's wet season usually peaks around December–March; compare the darker cells year by year.")

with tab_compare:
    comp = query(
        """select c.city_name, c.island, round(avg(f.temp_max_c), 1)::float as avg_temp_max_c,
                  round(sum(f.precipitation_mm))::float as total_precipitation_mm,
                  count(*) filter (where f.is_rainy_day) as rainy_days, count(*) as days
           from marts.fct_weather_daily f join marts.dim_city c using (city_id)
           where f.weather_date between %s and %s
           group by c.city_name, c.island""",
        (start, end),
    )
    c1, c2 = st.columns(2)
    with c1:
        d = comp.sort_values("total_precipitation_mm")
        fig = go.Figure(go.Bar(x=d["total_precipitation_mm"], y=d["city_name"], orientation="h",
                               marker=dict(color=d["total_precipitation_mm"], colorscale="Blues"),
                               text=d["total_precipitation_mm"].map("{:,.0f} mm".format), textposition="outside", cliponaxis=False))
        fig.update_layout(title="Total rainfall in selected period", hovermode=False,
                          xaxis=dict(range=[0, d["total_precipitation_mm"].max() * 1.22]))
        st.plotly_chart(style_fig(fig, 420), width="stretch")
    with c2:
        d = comp.sort_values("avg_temp_max_c")
        fig = go.Figure(go.Bar(x=d["avg_temp_max_c"], y=d["city_name"], orientation="h",
                               marker=dict(color=d["avg_temp_max_c"], colorscale="YlOrRd"),
                               text=d["avg_temp_max_c"].map("{:.1f}°C".format), textposition="outside", cliponaxis=False))
        fig.update_layout(title="Average max temperature in selected period", hovermode=False,
                          xaxis=dict(range=[d["avg_temp_max_c"].min() - 3, d["avg_temp_max_c"].max() + 1.5]))
        st.plotly_chart(style_fig(fig, 420), width="stretch")
    comp["rainy_share_%"] = (comp["rainy_days"] / comp["days"] * 100).round(0)
    st.dataframe(comp.sort_values("total_precipitation_mm", ascending=False), hide_index=True, width="stretch")

with tab_anomaly:
    anom = query(
        """select weather_date, temp_mean_c::float, normal_temp_mean_c::float, temp_anomaly_c::float,
                  temp_zscore::float, precipitation_mm::float, rain_intensity, is_temperature_anomaly
           from marts.mart_daily_anomaly
           where city_id = %s and weather_date between %s and %s order by weather_date""",
        (city["city_id"], start, end),
    )
    fig = go.Figure(go.Bar(
        x=anom["weather_date"], y=anom["temp_anomaly_c"], name="Difference from normal (°C)",
        marker_color=["#ef4444" if v > 0 else "#3b82f6" for v in anom["temp_anomaly_c"].fillna(0)],
        hovertemplate="%{x|%d %b %Y}: %{y:+.2f}°C vs normal<extra></extra>",
    ))
    flagged = anom[anom["is_temperature_anomaly"].fillna(False)]
    fig.add_trace(go.Scatter(x=flagged["weather_date"], y=flagged["temp_anomaly_c"], mode="markers", name="|z| ≥ 2",
                             marker=dict(size=9, color="#fde047", line=dict(width=1, color="#111"))))
    fig.update_layout(title="Daily temperature vs. the city's normal for that month", showlegend=True, hovermode="closest")
    st.plotly_chart(style_fig(fig, 400), width="stretch")
    st.caption(f"{len(flagged)} unusual day(s) in the selected period. Normal = the average for the same month across all loaded years.")
    st.dataframe(flagged.drop(columns="is_temperature_anomaly").sort_values("temp_zscore", key=abs, ascending=False),
                 hide_index=True, width="stretch")

with tab_health:
    fresh = query(
        "select city_name, latest_weather_date, days_behind, last_loaded_at "
        "from marts.mart_city_freshness order by city_name"
    )
    runs = query(
        """select run_id, mode, status, started_at, duration_seconds::float, start_date, end_date,
                  rows_received, rows_changed, error_message
           from marts.mart_pipeline_runs order by run_id desc limit 30"""
    )
    ok = runs["status"].eq("success").mean() * 100 if len(runs) else 0
    c = st.columns(4)
    c[0].markdown(tile("Last run", runs["status"].iloc[0] if len(runs) else "-",
                       f"{runs['started_at'].iloc[0]:%d %b %Y %H:%M}" if len(runs) else ""), unsafe_allow_html=True)
    c[1].markdown(tile("Success rate", f"{ok:.0f}%", f"last {len(runs)} runs"), unsafe_allow_html=True)
    c[2].markdown(tile("Max lag", f"{int(fresh['days_behind'].max())} days", "archive is ~5 days behind"),
                  unsafe_allow_html=True)
    c[3].markdown(tile("Cities", f"{len(fresh)}", "loaded daily"), unsafe_allow_html=True)
    st.write("")
    st.dataframe(fresh, hide_index=True, width="stretch")
    st.dataframe(runs, hide_index=True, width="stretch")

st.caption("Weather data by [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0) · Built by Dhia Salsabila Azhar")
