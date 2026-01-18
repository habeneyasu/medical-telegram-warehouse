-- Check for duplicate message_ids in fct_messages
-- Run in psql: \i scripts/check_duplicates.sql

-- Find duplicate message_ids
SELECT 
    message_id,
    COUNT(*) as count,
    STRING_AGG(DISTINCT channel_key::text, ', ') as channel_keys,
    STRING_AGG(DISTINCT channel_name, ', ') as channel_names
FROM marts.fct_messages
GROUP BY message_id
HAVING COUNT(*) > 1
ORDER BY COUNT(*) DESC;

-- Check raw data for duplicates
SELECT 
    message_id,
    channel_name,
    COUNT(*) as count,
    MIN(message_date) as first_date,
    MAX(message_date) as last_date
FROM raw.telegram_messages
GROUP BY message_id, channel_name
HAVING COUNT(*) > 1
ORDER BY COUNT(*) DESC
LIMIT 10;

-- Check if same message_id appears in different channels
SELECT 
    message_id,
    COUNT(DISTINCT channel_name) as channel_count,
    STRING_AGG(DISTINCT channel_name, ', ') as channels
FROM raw.telegram_messages
GROUP BY message_id
HAVING COUNT(DISTINCT channel_name) > 1
ORDER BY channel_count DESC
LIMIT 10;
