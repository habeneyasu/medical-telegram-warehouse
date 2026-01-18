-- Custom test: Ensure view counts are non-negative
-- This test returns rows (fails) if any messages have negative view counts

select
    message_id,
    channel_name,
    view_count,
    'Message has negative view count' as test_description
from {{ ref('stg_telegram_messages') }}
where view_count < 0
