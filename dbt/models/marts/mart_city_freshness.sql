-- How far behind is each city's data?
select
    c.city_id,
    c.city_name,
    max(w.weather_date)                         as latest_weather_date,
    current_date - max(w.weather_date)          as days_behind,
    max(w.loaded_at)                            as last_loaded_at
from {{ ref('cities') }} c
left join {{ ref('stg_weather_daily') }} w using (city_id)
group by c.city_id, c.city_name
