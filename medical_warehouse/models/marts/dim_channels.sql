{{
    config(
        materialized='table',
        schema='marts'
    )
}}

with channel_stats as (
    select
        channel_name,
        min(message_date_only) as first_post_date,
        max(message_date_only) as last_post_date,
        count(*) as total_posts,
        avg(view_count) as avg_views,
        sum(case when has_image then 1 else 0 end) as total_images
    from {{ ref('stg_telegram_messages') }}
    group by channel_name
),

channel_classification as (
    select
        channel_name,
        case
            when lower(channel_name) like '%pharma%' or lower(channel_name) like '%pharmaceutical%' then 'Pharmaceutical'
            when lower(channel_name) like '%cosmetic%' or lower(channel_name) like '%beauty%' then 'Cosmetics'
            when lower(channel_name) like '%medical%' or lower(channel_name) like '%chemed%' then 'Medical'
            else 'Other'
        end as channel_type
    from channel_stats
)

select
    -- Surrogate key (using row_number for simplicity, or hash for uniqueness)
    {{ dbt_utils.generate_surrogate_key(['cs.channel_name']) }} as channel_key,
    
    -- Channel attributes
    cs.channel_name,
    cc.channel_type,
    
    -- Date information
    cs.first_post_date,
    cs.last_post_date,
    
    -- Statistics
    cs.total_posts,
    cs.avg_views::numeric(10, 2) as avg_views,
    cs.total_images,
    round((cs.total_images::numeric / cs.total_posts::numeric) * 100, 2) as image_percentage
    
from channel_stats cs
inner join channel_classification cc
    on cs.channel_name = cc.channel_name
