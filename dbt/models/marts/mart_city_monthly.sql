-- Monthly climate summary per city.
select
    city_id,
    month_start,
    year,
    month,
    count(*)                                                        as days_observed,
    round(avg(temp_max_c), 2)                                       as avg_temp_max_c,
    round(avg(temp_min_c), 2)                                       as avg_temp_min_c,
    round(avg(temp_mean_c), 2)                                      as avg_temp_mean_c,
    max(temp_max_c)                                                 as hottest_temp_c,
    min(temp_min_c)                                                 as coolest_temp_c,
    round(sum(precipitation_mm), 1)                                 as total_precipitation_mm,
    max(precipitation_mm)                                           as wettest_day_mm,
    count(*) filter (where is_rainy_day)                            as rainy_days,
    count(*) filter (where rain_intensity in ('heavy', 'very heavy', 'extreme'))
                                                                    as heavy_rain_days,
    round(avg(sunshine_hours), 2)                                   as avg_sunshine_hours
from {{ ref('fct_weather_daily') }}
group by city_id, month_start, year, month
