{{
    config(
        materialized='view',
        schema='staging'
    )
}}

with raw_messages as (
    select
        message_id,
        channel_name,
        message_date,
        message_text,
        has_media,
        image_path,
        views,
        forwards,
        is_reply,
        reply_to_msg_id,
        scraped_at,
        loaded_at
    from {{ source('raw', 'telegram_messages') }}
    where message_id is not null
        and channel_name is not null
        and message_date is not null
)

select
    -- Primary key
    message_id,
    
    -- Channel information
    channel_name,
    
    -- Date and time
    message_date::timestamp as message_date,
    date_trunc('day', message_date)::date as message_date_only,
    
    -- Message content
    coalesce(message_text, '') as message_text,
    length(coalesce(message_text, '')) as message_length,
    
    -- Media information
    coalesce(has_media, false) as has_media,
    coalesce(image_path, '') as image_path,
    case 
        when image_path is not null and image_path != '' then true 
        else false 
    end as has_image,
    
    -- Engagement metrics
    coalesce(views, 0) as view_count,
    coalesce(forwards, 0) as forward_count,
    
    -- Reply information
    coalesce(is_reply, false) as is_reply,
    reply_to_msg_id,
    
    -- Metadata
    scraped_at::timestamp as scraped_at,
    loaded_at::timestamp as loaded_at
    
from raw_messages
where message_text is not null  -- Filter out completely empty messages
    and length(trim(message_text)) > 0  -- Filter out whitespace-only messages
