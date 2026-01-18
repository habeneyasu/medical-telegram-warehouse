-- Check all schemas and tables created by dbt
-- Run this in psql: \i scripts/check_dbt_tables.sql

-- List all schemas
SELECT 
    schema_name,
    schema_owner
FROM information_schema.schemata
WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
ORDER BY schema_name;

-- List all tables in raw schema
SELECT 
    table_schema,
    table_name,
    table_type
FROM information_schema.tables
WHERE table_schema = 'raw'
ORDER BY table_name;

-- List all tables in staging schema
SELECT 
    table_schema,
    table_name,
    table_type
FROM information_schema.tables
WHERE table_schema = 'staging'
ORDER BY table_name;

-- List all tables in marts schema
SELECT 
    table_schema,
    table_name,
    table_type
FROM information_schema.tables
WHERE table_schema = 'marts'
ORDER BY table_name;

-- Count rows in each table
SELECT 
    schemaname,
    tablename,
    n_live_tup as row_count
FROM pg_stat_user_tables
WHERE schemaname IN ('raw', 'staging', 'marts')
ORDER BY schemaname, tablename;
