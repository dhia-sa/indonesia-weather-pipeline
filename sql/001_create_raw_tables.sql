-- Raw (bronze) layer: data as received from the API, plus run metadata.
-- Safe to run repeatedly.

create schema if not exists raw;

create table if not exists raw.pipeline_runs (
    run_id            bigint generated always as identity primary key,
    mode              text        not null check (mode in ('backfill', 'incremental')),
    started_at        timestamptz not null default now(),
    finished_at       timestamptz,
    status            text        not null default 'running'
                      check (status in ('running', 'success', 'partial_failure', 'failed')),
    start_date        date,
    end_date          date,
    cities_requested  int,
    rows_received     int,
    rows_changed      int,
    error_message     text
);

create table if not exists raw.weather_daily (
    city_id        text        not null,
    weather_date   date        not null,
    payload        jsonb       not null,   -- one day's values, exactly as the API returned them
    api_latitude   double precision,       -- grid cell the API actually used
    api_longitude  double precision,
    elevation      double precision,
    run_id         bigint      references raw.pipeline_runs (run_id),
    loaded_at      timestamptz not null default now(),
    primary key (city_id, weather_date)
);

create index if not exists weather_daily_loaded_at_idx on raw.weather_daily (loaded_at);
