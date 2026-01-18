-- Custom test: Ensure no messages have future dates
-- This test returns rows (fails) if any messages have dates in the future

select
    message_id,
    channel_name,
    message_date,
    'Message has future date' as test_description
from {{ ref('stg_telegram_messages') }}
where message_date > current_timestamp
    or message_date_only > current_date
