-- City attributes + data coverage.
with cities as (

    select * from {{ ref('cities') }}

),

coverage as (

    select
        city_id,
        min(weather_date) as first_weather_date,
        max(weather_date) as last_weather_date,
        count(*)          as days_loaded
    from {{ ref('stg_weather_daily') }}
    group by city_id

)

select
    c.city_id,
    c.city_name,
    c.province,
    c.island,
    c.latitude,
    c.longitude,
    c.timezone,
    cov.first_weather_date,
    cov.last_weather_date,
    coalesce(cov.days_loaded, 0) as days_loaded
from cities c
left join coverage cov using (city_id)
