-- Run history for the pipeline-health page.
select
    run_id,
    mode,
    status,
    started_at,
    finished_at,
    round(extract(epoch from finished_at - started_at)::numeric, 1) as duration_seconds,
    start_date,
    end_date,
    cities_requested,
    rows_received,
    rows_changed,
    error_message
from {{ source('raw', 'pipeline_runs') }}
