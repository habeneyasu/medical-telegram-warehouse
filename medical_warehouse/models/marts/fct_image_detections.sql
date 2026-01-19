{{
    config(
        materialized='table',
        schema='marts'
    )
}}

-- Fact table: Image detections with YOLO results
-- Joins image detection results with messages and dimensions
-- Enables analysis of visual content patterns

with staging_detections as (
    select * from {{ ref('stg_image_detections') }}
),

staging_messages as (
    select * from {{ ref('stg_telegram_messages') }}
),

dim_channels as (
    select * from {{ ref('dim_channels') }}
),

dim_dates as (
    select * from {{ ref('dim_dates') }}
),

-- Join detections with messages to get message context
detections_with_messages as (
    select
        sd.message_id,
        sd.channel_name,
        sd.image_path,
        sd.detected_classes,
        sd.total_detections,
        sd.max_confidence,
        sd.image_category,
        sd.processed_at,
        -- Get message date for joining with dim_dates
        sm.message_date,
        sm.message_date_only,
        sm.view_count,
        sm.forward_count
    from staging_detections sd
    inner join staging_messages sm
        on sd.message_id = sm.message_id
        and sd.channel_name = sm.channel_name
)

select
    -- Fact key (using message_id as natural key)
    dwm.message_id,
    
    -- Foreign keys
    dc.channel_key,
    dd.date_key,
    
    -- Image detection information
    dwm.image_path,
    dwm.detected_classes,
    dwm.total_detections,
    dwm.max_confidence,
    dwm.image_category,
    
    -- Engagement metrics (from message)
    dwm.view_count,
    dwm.forward_count,
    
    -- Metadata
    dwm.message_date,
    dwm.processed_at
    
from detections_with_messages dwm
inner join dim_channels dc
    on dwm.channel_name = dc.channel_name
inner join dim_dates dd
    on dwm.message_date_only = dd.full_date
