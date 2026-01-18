{{
    config(
        materialized='table',
        schema='marts'
    )
}}

with date_range as (
    select
        min(message_date_only) as min_date,
        max(message_date_only) as max_date
    from {{ ref('stg_telegram_messages') }}
),

date_series as (
    select
        generate_series(
            (select min_date from date_range),
            (select max_date from date_range),
            '1 day'::interval
        )::date as full_date
)

select
    -- Surrogate key (YYYYMMDD format)
    to_char(full_date, 'YYYYMMDD')::integer as date_key,
    
    -- Date attributes
    full_date,
    extract(dow from full_date) as day_of_week,
    to_char(full_date, 'Day') as day_name,
    extract(week from full_date) as week_of_year,
    extract(month from full_date) as month,
    to_char(full_date, 'Month') as month_name,
    extract(quarter from full_date) as quarter,
    extract(year from full_date) as year,
    
    -- Business logic
    case 
        when extract(dow from full_date) in (0, 6) then true 
        else false 
    end as is_weekend,
    
    -- Additional useful fields
    extract(day from full_date) as day_of_month,
    extract(doy from full_date) as day_of_year,
    to_char(full_date, 'YYYY-MM') as year_month

from date_series
