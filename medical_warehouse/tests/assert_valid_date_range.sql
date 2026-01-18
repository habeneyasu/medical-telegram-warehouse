-- Custom test: Ensure message dates are within reasonable range
-- Messages should be between 2020 and 2030

select
    message_id,
    channel_name,
    message_date_only,
    'Message date outside valid range' as test_description
from {{ ref('stg_telegram_messages') }}
where message_date_only < '2020-01-01'::date
    or message_date_only > '2030-12-31'::date
