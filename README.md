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

**Option 1: Manual Execution**
```bash
# 1. Scrape Telegram channels
python3 scripts/run_scraper.py

# 2. Load raw data to PostgreSQL
python3 scripts/load_raw_to_postgres.py

# 3. Run YOLOv8 image detection
python3 src/yolo_detect.py
python3 scripts/load_detections_to_postgres.py

# 4. Transform with dbt
bash scripts/run_dbt.sh deps
bash scripts/run_dbt.sh run
bash scripts/run_dbt.sh test

# 5. Start API (optional)
bash scripts/run_api.sh
```

**Option 2: Dagster Orchestration (Recommended)**
```bash
# Start Dagster UI and run entire pipeline
bash scripts/run_dagster.sh
# Access UI at http://localhost:3000
```

## Architecture

```
Telegram → Scraper → Data Lake → YOLOv8 → PostgreSQL → dbt → Star Schema → FastAPI
```

**Pipeline Steps:**
1. **Extract**: Scrape messages and images from Telegram
2. **Enrich**: YOLOv8 object detection and image classification
3. **Load**: Store in PostgreSQL `raw` schema
4. **Transform**: dbt creates `staging` and `marts` schemas
5. **Analyze**: FastAPI exposes analytical endpoints

## Configuration

**Required** (`.env`):
```env
# Telegram API
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash

# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=medical_warehouse
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# Optional: Per-channel limits
MAX_IMAGES_CheMed=1200
MAX_IMAGES_lobelia4cosmetics=1500
MAX_IMAGES_tikvahpharma=1700
```

## Project Structure

```
├── src/                    # Core modules (scraper, YOLO, database, logging)
├── scripts/                # Data loading and utility scripts
├── medical_warehouse/      # dbt project (staging + marts)
├── api/                    # FastAPI analytical API
├── pipeline.py             # Dagster pipeline definition
├── data/                   # Data lake (raw/processed)
├── tests/                  # Unit tests
└── logs/                   # Application logs
```

## Features

- ✅ **Data Collection**: Telegram scraping with per-channel limits
- ✅ **Image Detection**: YOLOv8n object detection and classification
- ✅ **Data Warehouse**: Star schema with dbt (60+ tests)
- ✅ **Analytical API**: FastAPI with 4 endpoints, rate limiting, caching
- ✅ **Pipeline Orchestration**: Dagster for automated, observable workflows
- ✅ **Infrastructure**: Connection pooling, structured logging, error handling

## Image Classification

Images are automatically classified into:
- **promotional**: Person + product
- **product_display**: Product only
- **lifestyle**: Person only
- **other**: Neither detected

## API

**Endpoints:**
- `GET /api/reports/top-products` - Most mentioned products
- `GET /api/channels/{name}/activity` - Channel activity trends
- `GET /api/search/messages` - Search messages by keyword
- `GET /api/reports/visual-content` - Image usage statistics

**Documentation**: http://localhost:8000/docs  
**Details**: See `api/README.md`

## Database Schemas

- `raw` - Raw scraped data and detections
- `staging` - Cleaned data (dbt views)
- `staging_marts` - Star schema (dbt tables)
  - `dim_channels`, `dim_dates`
  - `fct_messages`, `fct_image_detections`

## Pipeline Orchestration

**Dagster Pipeline:**
- 5 operations with proper dependencies
- Daily schedule (2 AM, configurable)
- Observable execution with logs and metrics
- Configurable channels via UI or environment

**Start:** `bash scripts/run_dagster.sh` → http://localhost:3000

## Development

```bash
# Test database connection
python3 scripts/test_db_connection.py

# Test API
python3 scripts/test_api.py http://localhost:8000

# Run tests
pytest tests/ -v
bash scripts/run_dbt.sh test
```

## Troubleshooting

**Database connection:**
```bash
python3 scripts/test_db_connection.py
```

**dbt not found:**
```bash
bash scripts/run_dbt.sh run  # Uses helper script
```

**YOLOv8 model:** Downloads automatically on first run (~6MB)

## License

MIT License
