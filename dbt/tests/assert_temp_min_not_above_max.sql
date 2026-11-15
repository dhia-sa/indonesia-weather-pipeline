-- A day's minimum temperature can never be higher than its maximum.
select weather_day_id, temp_min_c, temp_max_c
from {{ ref('fct_weather_daily') }}
where temp_min_c > temp_max_c
