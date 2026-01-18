{{
    config(
        materialized='table',
        schema='marts'
    )
}}

with staging_messages as (
    select * from {{ ref('stg_telegram_messages') }}
),

dim_channels as (
    select * from {{ ref('dim_channels') }}
),

dim_dates as (
    select * from {{ ref('dim_dates') }}
)

select
    -- Fact key (using message_id as natural key)
    sm.message_id,
    
    -- Foreign keys
    dc.channel_key,
    dd.date_key,
    
    -- Message content
    sm.message_text,
    sm.message_length,
    
    -- Engagement metrics
    sm.view_count,
    sm.forward_count,
    
    -- Media information
    sm.has_image,
    sm.image_path,
    
    -- Reply information
    sm.is_reply,
    sm.reply_to_msg_id,
    
    -- Metadata
    sm.message_date,
    sm.scraped_at,
    sm.loaded_at
    
from staging_messages sm
inner join dim_channels dc
    on sm.channel_name = dc.channel_name
inner join dim_dates dd
    on sm.message_date_only = dd.full_date
