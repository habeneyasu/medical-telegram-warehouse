# Medical Telegram Warehouse

End-to-end ELT data pipeline for scraping, transforming, and analyzing medical product data from Telegram channels in Ethiopia.

## Overview

This project implements a modern data pipeline that:
- Extracts messages and images from Telegram channels
- Loads raw data into PostgreSQL data warehouse
- Transforms data using dbt into dimensional star schema
- Enriches data using YOLO object detection
- Exposes insights through FastAPI REST API
- Orchestrates pipeline using Dagster

## Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL 12+
- Docker & Docker Compose (optional)

### Installation

```bash
# Clone repository
git clone <repository-url>
cd medical-telegram-warehouse

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Telegram API credentials
```

### Telegram API Setup

1. Visit [my.telegram.org](https://my.telegram.org)
2. Create application in "API development tools"
3. Add credentials to `.env`:
   ```env
   TELEGRAM_API_ID=your_api_id
   TELEGRAM_API_HASH=your_api_hash
   ```

## Usage

### Run Scraper

```bash
# Default channels
python3 scripts/run_scraper.py

# Custom channels and limits
python3 scripts/run_scraper.py --channels lobelia4cosmetics tikvahpharma --limit 100
```

### Docker

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f app

# Stop services
docker-compose down
```

## Data Structure

```
data/raw/
├── images/
│   └── {channel_name}/{message_id}.jpg
└── telegram_messages/
    └── YYYY-MM-DD/{channel_name}.json
```

**Date-first partitioning** optimizes for:
- Date-range queries
- Incremental loading
- Database partitioning
- dbt incremental models

## Configuration

### Channel-Specific Image Limits

Configure in `.env`:
```env
MAX_IMAGES_CheMed123=1200
MAX_IMAGES_lobelia4cosmetics=1500
MAX_IMAGES_tikvahpharma=1700
MAX_IMAGES=1500  # Default
```

## Features

- ✅ Automatic rate limiting and error handling
- ✅ Per-channel image download limits
- ✅ Date-partitioned data storage
- ✅ Comprehensive logging
- ✅ Message deduplication
- ✅ Progress tracking

## Supported Channels

- `CheMed123` - CheMed Channel
- `lobelia4cosmetics` - Lobelia Cosmetics
- `tikvahpharma` - Tikvah Pharma

## Development

```bash
# Run tests
pytest tests/

# Format code
black src/ scripts/ api/

# Lint code
flake8 src/ scripts/ api/
```

## Project Structure

```
├── api/              # FastAPI application
├── src/              # Source code (scraper, utilities)
├── scripts/          # Utility scripts
├── medical_warehouse/ # dbt project
├── data/             # Data lake (raw/processed)
└── tests/           # Unit tests
```

## License

MIT License - See LICENSE file for details.
