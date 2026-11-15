-- How unusual was each day compared with that city's normal for the same month?
with daily as (

    select * from {{ ref('fct_weather_daily') }}

),

climatology as (

    -- "Normal" = average over all loaded years for the same city + calendar month.
    select
        city_id,
        month,
        avg(temp_mean_c)          as normal_temp_mean_c,
        stddev_samp(temp_mean_c)  as temp_mean_stddev,
        avg(precipitation_mm)     as normal_precipitation_mm
    from daily
    group by city_id, month

),

scored as (

    select
        d.weather_day_id,
        d.city_id,
        d.weather_date,
        d.temp_mean_c,
        round(c.normal_temp_mean_c, 2)                              as normal_temp_mean_c,
        round(d.temp_mean_c - c.normal_temp_mean_c, 2)              as temp_anomaly_c,
        case when c.temp_mean_stddev > 0
             then round((d.temp_mean_c - c.normal_temp_mean_c) / c.temp_mean_stddev, 2)
        end                                                         as temp_zscore,
        d.precipitation_mm,
        round(c.normal_precipitation_mm, 2)                         as normal_precipitation_mm,
        d.rain_intensity
    from daily d
    join climatology c using (city_id, month)

)

select
    *,
    abs(temp_zscore) >= 2 as is_temperature_anomaly
from scored
