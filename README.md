# 🌦️ Indonesia Weather Data Pipeline

An end-to-end data engineering project. Every day it collects weather data for 10 Indonesian cities from the
[Open-Meteo](https://open-meteo.com/) API, loads it into Postgres, models it with dbt, and serves it in a
Streamlit dashboard. The whole stack runs on free tiers.

**Live dashboard:** [open the app](https://indonesia-weather-pipeline-2bixeqvwpodjkoxqbz32a9.streamlit.app) · **Portfolio:** [dhia-sa.github.io](https://dhia-sa.github.io)

> **Why weather?** In retail and F&B, weather drives store traffic and demand. This project builds a reliable,
> tested weather dataset that could be joined to store sales to explain demand or improve forecasts.

## Dashboard

[![Indonesia Weather dashboard](docs/weather-dashboard-hero.jpg)](https://indonesia-weather-pipeline-2bixeqvwpodjkoxqbz32a9.streamlit.app)

| Daily metrics & last 7 days | Temperature & rainfall trends |
|---|---|
| ![Metric tiles](docs/weather-dashboard-tiles.jpg) | ![Trends chart](docs/weather-dashboard-trends.jpg) |

📄 [Download the full dashboard as PDF](docs/indonesia-weather-dashboard.pdf) · 🔗 [Open the live app](https://indonesia-weather-pipeline-2bixeqvwpodjkoxqbz32a9.streamlit.app)

## Architecture

```mermaid
flowchart LR
    A[Open-Meteo<br/>Historical Weather API] -->|Python extractor<br/>retries, idempotent upserts| B[(Postgres<br/>raw schema)]
    B -->|dbt| C[(staging<br/>typed views)]
    C -->|dbt| D[(marts<br/>facts and summaries)]
    D --> E[Streamlit dashboard]
    F[GitHub Actions<br/>daily cron] -.runs.-> A
    F -.runs.-> B
    F -.dbt build + tests.-> D
```

| Layer | Tool | Details |
|---|---|---|
| Extract | Python, `requests` | Exponential-backoff retries on 429/5xx, per-city error isolation |
| Load | Postgres (Neon / Supabase / local Docker) | Raw JSON payload per city per day, upsert on `(city_id, weather_date)` |
| Transform | dbt | `raw → staging → marts`, 35 data tests, source freshness |
| Orchestrate | GitHub Actions | Daily cron, manual backfill trigger, CI on every push |
| Serve | Streamlit | City trends, city comparison, anomalies, pipeline health |

## Data model

| Schema | Model | Grain | Purpose |
|---|---|---|---|
| raw | `weather_daily` | city × day | API values as received (JSONB) + load metadata |
| raw | `pipeline_runs` | run | status, row counts, errors for every extractor run |
| reference | `cities`, `weather_codes` | — | dbt seeds (city list is shared with the extractor) |
| staging | `stg_weather_daily` | city × day | typed and renamed columns, unit conversion |
| marts | `dim_city` | city | location + data coverage |
| marts | `fct_weather_daily` | city × day | mean temp, rainy-day flag, rain intensity band, weather description |
| marts | `mart_city_monthly` | city × month | monthly climate summary |
| marts | `mart_daily_anomaly` | city × day | deviation from the city's normal for that month (z-score) |
| marts | `mart_pipeline_runs`, `mart_city_freshness` | run / city | pipeline monitoring |

## Design decisions

- **Idempotent loads.** Every write is an upsert keyed on `(city_id, weather_date)`. Re-running any backfill never
  creates duplicates. A `WHERE payload IS DISTINCT FROM excluded.payload` clause skips unchanged rows, so
  `rows_changed` shows exactly what was new or revised.
- **Late and revised data.** Archive data arrives about 5 days late and recent values can be revised. Each
  incremental run re-reads a 10-day lookback window. Days that are still empty are skipped, so they get loaded on a
  later run.
- **Raw layer stays raw.** The extractor stores the API values untouched as JSONB. Typing and business logic live
  in dbt, so they are versioned, tested and documented, and history can be re-modelled without calling the API again.
- **One source of truth for cities.** `dbt/seeds/cities.csv` drives both the extractor and the `dim_city` model.
- **Fail loudly.** One failing city doesn't stop the others, but the run is recorded as `partial_failure` and the
  job exits non-zero, so GitHub Actions marks it red and emails you.
- **Observability.** Every run is logged in `raw.pipeline_runs` and shown on the dashboard's *Pipeline health* tab.
  dbt source freshness alerts when data stops arriving.

## Project structure

```
├── extract/                 # Python extractor
│   ├── config.py            # API variables, settings, DB connection
│   ├── client.py            # Open-Meteo client with retries
│   ├── transform.py         # column arrays → rows, date chunking
│   ├── load.py              # Postgres upserts + run logging
│   └── pipeline.py          # CLI: init-db | backfill | incremental
├── sql/                     # raw-layer DDL
├── dbt/                     # dbt project (seeds, staging, marts, tests)
├── dashboard/               # Streamlit app
├── tests/                   # pytest unit tests
├── .github/workflows/       # daily_pipeline.yml, ci.yml
├── run_dbt.py               # runs dbt with credentials from .env
└── docker-compose.yml       # optional local Postgres
```

## Run it locally

Requirements: Python 3.11+ and a Postgres database (local Docker or a free cloud one, see below).

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt -r dashboard/requirements.txt

cp .env.example .env                 # Windows: copy .env.example .env  — then fill in DB settings
docker compose up -d                 # optional: local Postgres

python -m extract.pipeline backfill --start 2020-01-01   # history (about 1–2 minutes)
python -m extract.pipeline incremental                   # new days since the last run
python run_dbt.py build                                  # dbt seeds + models + tests
python run_dbt.py source freshness
streamlit run dashboard/app.py
```

Run the unit tests and linter with `pytest` and `ruff check .`

## Deploy (free)

1. **Database:** create a free Postgres on [Neon](https://neon.tech) (pick the Singapore region). Copy the host,
   database, user and password.
2. **GitHub secrets:** in the repo, go to *Settings → Secrets and variables → Actions* and add `DB_HOST`, `DB_PORT`
   (`5432`), `DB_NAME`, `DB_USER` and `DB_PASSWORD`.
3. **Backfill once:** go to *Actions → Daily weather pipeline → Run workflow* and pick `mode = backfill`.
4. **Daily runs** then happen automatically at 07:17 WIB. GitHub pauses scheduled workflows in repos with no
   activity for 60 days; re-enable the workflow in the Actions tab if that happens.
5. **Dashboard:** on [Streamlit Community Cloud](https://share.streamlit.io), create an app from this repo with
   main file `dashboard/app.py`. Under *Advanced settings → Secrets*, paste Neon's connection string as one line:
   ```toml
   DATABASE_URL = "postgresql://USER:PASSWORD@ep-xxxx.neon.tech/neondb?sslmode=require"
   ```
   or, alternatively, the separate settings:
   ```toml
   DB_HOST = "..."
   DB_PORT = "5432"
   DB_NAME = "..."
   DB_USER = "..."
   DB_PASSWORD = "..."
   DB_SSLMODE = "require"
   ```

## Ideas to extend

- Add the Forecast API and compare forecast vs. actual accuracy per city
- Make `fct_weather_daily` an incremental dbt model
- Add hourly data, or join to a (synthetic) store-sales dataset to model weather impact on demand
- Send a Slack or Telegram alert when a run fails

## Data source

Weather data by [Open-Meteo.com](https://open-meteo.com/), licensed under CC BY 4.0. The free API is for
non-commercial use.
