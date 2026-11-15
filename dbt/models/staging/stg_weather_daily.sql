-- Type, rename and unit-convert the raw JSON payload. One row per city per day.
with source as (

    select * from {{ source('raw', 'weather_daily') }}

)

select
    city_id || '_' || to_char(weather_date, 'YYYY-MM-DD')           as weather_day_id,
    city_id,
    weather_date,

    (payload ->> 'weather_code')::numeric::int                       as weather_code,
    (payload ->> 'temperature_2m_max')::numeric(5, 2)                as temp_max_c,
    (payload ->> 'temperature_2m_min')::numeric(5, 2)                as temp_min_c,
    (payload ->> 'apparent_temperature_max')::numeric(5, 2)          as feels_like_max_c,
    (payload ->> 'apparent_temperature_min')::numeric(5, 2)          as feels_like_min_c,
    (payload ->> 'precipitation_sum')::numeric(7, 2)                 as precipitation_mm,
    (payload ->> 'rain_sum')::numeric(7, 2)                          as rain_mm,
    (payload ->> 'precipitation_hours')::numeric(4, 1)               as precipitation_hours,
    round((payload ->> 'sunshine_duration')::numeric / 3600, 2)      as sunshine_hours,
    round((payload ->> 'daylight_duration')::numeric / 3600, 2)      as daylight_hours,
    (payload ->> 'wind_speed_10m_max')::numeric(6, 2)                as wind_speed_max_kmh,
    (payload ->> 'wind_gusts_10m_max')::numeric(6, 2)                as wind_gusts_max_kmh,
    (payload ->> 'wind_direction_10m_dominant')::numeric::int        as wind_direction_deg,
    (payload ->> 'shortwave_radiation_sum')::numeric(6, 2)           as solar_radiation_mj_m2,
    (payload ->> 'et0_fao_evapotranspiration')::numeric(6, 2)        as evapotranspiration_mm,

    elevation                                                        as grid_elevation_m,
    run_id,
    loaded_at

from source
