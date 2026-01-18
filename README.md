# Medical Telegram Warehouse

End-to-end ELT pipeline for scraping, transforming, and analyzing medical product data from Telegram channels.

## Quick Start

### Setup

```bash
# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Add Telegram API credentials from https://my.telegram.org
```

### Run Pipeline

```bash
# 1. Scrape Telegram channels
python3 scripts/run_scraper.py

# 2. Load raw data to PostgreSQL
python3 scripts/load_raw_to_postgres.py

# 3. Transform with dbt
cd medical_warehouse
export POSTGRES_PASSWORD=your_password
dbt deps
dbt run
dbt test
```

## Architecture

```
Telegram Channels → Scraper → Data Lake (JSON/Images) → PostgreSQL → dbt → Star Schema
```

**Data Flow:**
1. **Extract**: Scrape messages and images from Telegram
2. **Load**: Store raw data in PostgreSQL `raw` schema
3. **Transform**: dbt creates `staging` and `marts` schemas (star schema)

## Configuration

**Telegram API** (`.env`):
```env
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
```

**Image Limits** (`.env`):
```env
MAX_IMAGES_CheMed123=1200
MAX_IMAGES_lobelia4cosmetics=1500
MAX_IMAGES_tikvahpharma=1700
MAX_MESSAGES_tikvahpharma=3000
```

**Database** (`.env`):
```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=medical_warehouse
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
```

## Data Structure

```
data/raw/
├── images/{channel_name}/{message_id}.jpg
└── telegram_messages/YYYY-MM-DD/{channel_name}.json
```

**Database Schemas:**
- `raw` - Raw scraped data
- `staging` - Cleaned and standardized data (dbt views)
- `marts` - Dimensional star schema (dbt tables)
  - `dim_channels` - Channel dimension
  - `dim_dates` - Date dimension
  - `fct_messages` - Messages fact table

## Supported Channels

- `CheMed123` - CheMed Channel
- `lobelia4cosmetics` - Lobelia Cosmetics
- `tikvahpharma` - Tikvah Pharma

## Project Structure

```
├── src/              # Scraper and utilities
├── scripts/          # Data loading and utility scripts
├── medical_warehouse/ # dbt project (staging + marts)
├── api/              # FastAPI application (Task 4)
├── data/             # Data lake (raw/processed)
└── tests/            # Unit tests
```

## Features

- ✅ Per-channel image and message limits
- ✅ Date-partitioned storage
- ✅ Star schema data warehouse
- ✅ Comprehensive data quality tests
- ✅ Automatic rate limiting
- ✅ Progress tracking and logging

## Development

```bash
# Test database connection
python3 scripts/test_db_connection.py

# Run tests
pytest tests/

# Format code
black src/ scripts/
```

## License

MIT License
