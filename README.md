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

# 3. Run YOLOv8 image detection and classification
python3 src/yolo_detect.py

# 4. Load image detection results to PostgreSQL
python3 scripts/load_detections_to_postgres.py

# 5. Transform with dbt
bash scripts/run_dbt.sh deps
bash scripts/run_dbt.sh run
bash scripts/run_dbt.sh test
```

## Architecture

```
Telegram Channels → Scraper → Data Lake (JSON/Images) → YOLOv8 Detection → PostgreSQL → dbt → Star Schema
```

**Data Flow:**
1. **Extract**: Scrape messages and images from Telegram
2. **Enrich**: Run YOLOv8 object detection on images and classify them
3. **Load**: Store raw data and detection results in PostgreSQL `raw` schema
4. **Transform**: dbt creates `staging` and `marts` schemas (star schema)

**Key Features:**
- **Single Database Connection**: Shared connection pool across all scripts (`src/database.py`)
- **Professional Logging**: Structured logging with file rotation (`src/logger_config.py`)
- **Exception Handling**: Comprehensive error handling and recovery
- **Connection Pooling**: Optimized database connections with automatic recovery

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
- `raw` - Raw scraped data and image detection results
- `staging` - Cleaned and standardized data (dbt views)
- `marts` - Dimensional star schema (dbt tables)
  - `dim_channels` - Channel dimension
  - `dim_dates` - Date dimension
  - `fct_messages` - Messages fact table
  - `fct_image_detections` - Image detection results with classifications

## Supported Channels

- `CheMed123` - CheMed Channel
- `lobelia4cosmetics` - Lobelia Cosmetics
- `tikvahpharma` - Tikvah Pharma

## Project Structure

```
├── src/                    # Core modules
│   ├── scraper.py          # Telegram scraper
│   ├── yolo_detect.py      # YOLOv8 image detection
│   ├── database.py         # Shared database connection
│   └── logger_config.py    # Logging configuration
├── scripts/                # Data loading and utility scripts
│   ├── run_scraper.py      # Main scraper entry point
│   ├── load_raw_to_postgres.py
│   ├── load_detections_to_postgres.py
│   └── run_dbt.sh          # dbt execution helper
├── medical_warehouse/      # dbt project (staging + marts)
│   ├── models/
│   │   ├── staging/        # Staging models
│   │   └── marts/          # Fact and dimension tables
│   └── profiles.yml.example
├── api/                    # FastAPI application (Task 4)
├── data/                   # Data lake
│   ├── raw/                # Raw scraped data
│   └── processed/          # Processed data (CSV files)
├── tests/                  # Unit tests
└── logs/                   # Application logs
```

## Features

### Data Collection
- ✅ Per-channel image and message limits
- ✅ Date-partitioned storage
- ✅ Automatic rate limiting
- ✅ Progress tracking and logging

### Data Processing
- ✅ YOLOv8 object detection (nano model for efficiency)
- ✅ Image classification: promotional, product_display, lifestyle, other
- ✅ Star schema data warehouse
- ✅ Comprehensive data quality tests (60+ tests)

### Infrastructure
- ✅ Shared database connection with connection pooling
- ✅ Professional structured logging with file rotation
- ✅ Comprehensive exception handling
- ✅ Docker support with multi-stage builds
- ✅ CI/CD with GitHub Actions

## Image Detection & Classification

The project uses YOLOv8n (nano) model for efficient object detection on standard laptops. Images are automatically classified into categories:

- **promotional**: Contains person + product (someone showing/holding item)
- **product_display**: Contains bottle/container, no person
- **lifestyle**: Contains person, no product
- **other**: Neither person nor product detected

### Running Image Detection

```bash
# Run YOLOv8 detection on all scraped images
python3 src/yolo_detect.py

# Results are saved to: data/processed/image_detections.csv
# Then load to database:
python3 scripts/load_detections_to_postgres.py
```

### Analysis Queries

After running the pipeline, you can analyze the data:

**1. Do "promotional" posts get more views than "product_display" posts?**
```sql
SELECT 
    image_category,
    COUNT(*) as post_count,
    AVG(view_count) as avg_views,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY view_count) as median_views
FROM marts.fct_image_detections
GROUP BY image_category
ORDER BY avg_views DESC;
```

**2. Which channels use more visual content?**
```sql
SELECT 
    dc.channel_name,
    COUNT(DISTINCT fid.message_id) as images_with_detections,
    COUNT(DISTINCT fm.message_id) as total_messages,
    ROUND(COUNT(DISTINCT fid.message_id) * 100.0 / COUNT(DISTINCT fm.message_id), 2) as visual_content_percentage
FROM marts.dim_channels dc
LEFT JOIN marts.fct_messages fm ON dc.channel_key = fm.channel_key
LEFT JOIN marts.fct_image_detections fid ON fm.message_id = fid.message_id
GROUP BY dc.channel_name
ORDER BY visual_content_percentage DESC;
```

### Limitations of Pre-trained Models

**YOLOv8n Limitations for Domain-Specific Tasks:**

1. **Generic Object Classes**: YOLOv8 is trained on COCO dataset with 80 generic classes (person, bottle, etc.). It cannot detect:
   - Specific medical product types (e.g., "vitamin D3", "omega-3")
   - Brand-specific packaging
   - Product names or text in images

2. **Classification Rules**: Our classification scheme relies on simple heuristics (person + product = promotional). This may misclassify:
   - Complex scenes with multiple objects
   - Unusual angles or lighting
   - Products that don't match COCO classes

3. **Accuracy Trade-offs**: The nano model prioritizes speed over accuracy:
   - Smaller objects may be missed
   - Lower confidence thresholds may increase false positives
   - Domain-specific products may not be recognized

**Recommendations for Production:**
- Fine-tune YOLOv8 on domain-specific medical product images
- Add OCR (Optical Character Recognition) for product text
- Implement custom classification models trained on labeled medical product images
- Combine multiple models for better accuracy

## Development

```bash
# Test database connection
python3 scripts/test_db_connection.py

# Run unit tests
pytest tests/ -v

# Run dbt tests
bash scripts/run_dbt.sh test

# Format code
black src/ scripts/ api/
```

## Troubleshooting

### YOLOv8 Model Not Found
If you see `FileNotFoundError` for `yolov8n.pt`:
- The model will be downloaded automatically on first run
- Ensure you have internet connection
- Check disk space (model is ~6MB)

### Database Connection Issues
```bash
# Test connection
python3 scripts/test_db_connection.py

# Check environment variables
echo $POSTGRES_HOST $POSTGRES_DB $POSTGRES_USER
```

### dbt Command Not Found
```bash
# Activate virtual environment first
source venv/bin/activate

# Or use the helper script
bash scripts/run_dbt.sh run
```

### Import Errors
If you see `ModuleNotFoundError`:
```bash
# Ensure you're in the project root
cd /path/to/medical-telegram-warehouse

# Activate virtual environment
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

## License

MIT License
