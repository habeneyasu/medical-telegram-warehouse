{{
    config(
        materialized='view',
        schema='staging'
    )
}}

-- Staging model: Clean and standardize raw image detection results
-- This model performs:
-- 1. Type casting (integers, decimals, strings)
-- 2. Invalid record filtering (nulls, invalid categories)
-- 3. Data standardization (coalesce, calculated fields)

with raw_detections as (
    select
        message_id,
        channel_name,
        image_path,
        detected_classes,
        total_detections,
        max_confidence,
        image_category,
        processed_at,
        loaded_at
    from {{ source('raw', 'image_detections') }}
    -- INVALID RECORD FILTERING: Remove records with missing critical fields
    where message_id is not null
        and channel_name is not null
)

select
    -- Primary keys
    message_id::bigint as message_id,
    trim(channel_name)::varchar(255) as channel_name,
    
    -- Image information
    coalesce(image_path, '')::varchar(500) as image_path,
    coalesce(detected_classes, '')::text as detected_classes,
    
    -- Detection metrics: Type casting
    coalesce(total_detections, 0)::integer as total_detections,
    coalesce(max_confidence, 0.0)::numeric(5, 4) as max_confidence,
    
    -- Image classification: Standardize category values
    case
        when lower(trim(image_category)) in ('promotional', 'product_display', 'lifestyle', 'other') 
        then lower(trim(image_category))::varchar(50)
        else 'other'::varchar(50)
    end as image_category,
    
    -- METADATA: Type casting timestamps
    processed_at::timestamp as processed_at,
    loaded_at::timestamp as loaded_at
    
from raw_detections
-- INVALID RECORD FILTERING: Ensure we have at least message_id and channel_name
where message_id is not null
    and channel_name is not null
    and length(trim(channel_name)) > 0
