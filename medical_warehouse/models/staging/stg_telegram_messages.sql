{{
    config(
        materialized='view',
        schema='staging'
    )
}}

-- Staging model: Clean and standardize raw Telegram messages
-- This model performs:
-- 1. Type casting (dates, integers, booleans)
-- 2. Invalid record filtering (nulls, empty messages)
-- 3. Data standardization (coalesce, calculated fields)

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
    -- INVALID RECORD FILTERING: Remove records with missing critical fields
    where message_id is not null
        and channel_name is not null
        and message_date is not null
)

select
    -- Primary key (no transformation needed)
    message_id::bigint as message_id,
    
    -- Channel information (standardize text)
    trim(channel_name)::varchar(255) as channel_name,
    
    -- DATE AND TIME TYPE CASTING
    -- Cast to timestamp to ensure consistent datetime format
    message_date::timestamp as message_date,
    -- Extract date-only for joining with dim_dates
    date_trunc('day', message_date)::date as message_date_only,
    
    -- MESSAGE CONTENT: Standardize and calculate fields
    -- Coalesce nulls to empty string, then calculate length
    coalesce(message_text, '')::text as message_text,
    length(coalesce(message_text, ''))::integer as message_length,
    
    -- MEDIA INFORMATION: Type casting and boolean logic
    -- Cast boolean fields explicitly
    coalesce(has_media, false)::boolean as has_media,
    -- Standardize image path (empty string if null)
    coalesce(image_path, '')::varchar(500) as image_path,
    -- Calculated field: has_image flag based on image_path
    case 
        when image_path is not null and image_path != '' then true 
        else false 
    end::boolean as has_image,
    
    -- ENGAGEMENT METRICS: Type casting integers
    -- Cast to integer and handle nulls (default to 0)
    coalesce(views, 0)::integer as view_count,
    coalesce(forwards, 0)::integer as forward_count,
    
    -- REPLY INFORMATION: Type casting booleans and bigints
    coalesce(is_reply, false)::boolean as is_reply,
    reply_to_msg_id::bigint as reply_to_msg_id,
    
    -- METADATA: Type casting timestamps
    scraped_at::timestamp as scraped_at,
    loaded_at::timestamp as loaded_at
    
from raw_messages
-- INVALID RECORD FILTERING: Remove empty or whitespace-only messages
where message_text is not null  -- Filter out completely empty messages
    and length(trim(message_text)) > 0  -- Filter out whitespace-only messages
