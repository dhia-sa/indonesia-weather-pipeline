-- Daily weather fact with business-friendly derived fields.
with weather as (

    select * from {{ ref('stg_weather_daily') }}

),

codes as (

    select * from {{ ref('weather_codes') }}

)

select
    w.weather_day_id,
    w.city_id,
    w.weather_date,
    extract(year from w.weather_date)::int                 as year,
    extract(month from w.weather_date)::int                as month,
    date_trunc('month', w.weather_date)::date              as month_start,
    extract(isodow from w.weather_date)::int               as iso_day_of_week,

    w.temp_max_c,
    w.temp_min_c,
    round((w.temp_max_c + w.temp_min_c) / 2, 2)            as temp_mean_c,   -- approx. daily mean
    w.temp_max_c - w.temp_min_c                            as temp_range_c,
    w.feels_like_max_c,
    w.feels_like_min_c,

    w.precipitation_mm,
    w.rain_mm,
    w.precipitation_hours,
    w.precipitation_mm >= 1                                as is_rainy_day,
    -- Daily rainfall intensity bands (mm/day), similar to BMKG's classification.
    case
        when w.precipitation_mm is null then null
        when w.precipitation_mm < 0.5   then 'no rain'
        when w.precipitation_mm < 20    then 'light'
        when w.precipitation_mm < 50    then 'moderate'
        when w.precipitation_mm < 100   then 'heavy'
        when w.precipitation_mm < 150   then 'very heavy'
        else 'extreme'
    end                                                    as rain_intensity,

    w.sunshine_hours,
    w.daylight_hours,
    w.wind_speed_max_kmh,
    w.wind_gusts_max_kmh,
    w.wind_direction_deg,
    w.solar_radiation_mj_m2,
    w.evapotranspiration_mm,

    w.weather_code,
    codes.description                                      as weather_description,
    codes.category                                         as weather_category,

    w.loaded_at
from weather w
left join codes using (weather_code)
