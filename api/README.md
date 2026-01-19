# Medical Telegram Warehouse API

FastAPI analytical API for querying the medical product data warehouse.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Start the API
bash scripts/run_api.sh

# Access documentation
# http://localhost:8000/docs
```

## Configuration

Set database credentials in `.env`:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=medical_warehouse
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
```

## API Endpoints

### 1. Top Products
**GET** `/api/reports/top-products?limit=10&min_length=4`

Returns most frequently mentioned product terms across all channels.

### 2. Channel Activity
**GET** `/api/channels/{channel_name}/activity?days=30`

Returns posting activity and engagement trends for a specific channel.

**Available channels:** `CheMed`, `Lobelia pharmacy and cosmetics`, `Tikvah | Pharma`

### 3. Message Search
**GET** `/api/search/messages?query=paracetamol&limit=20&channel_name=CheMed`

Searches messages containing a specific keyword with relevance scoring.

### 4. Visual Content Statistics
**GET** `/api/reports/visual-content`

Returns statistics about image usage and classifications (promotional, product_display, lifestyle, other).

### Health Check
**GET** `/health`

Returns API and database connection status.

## Features

- ✅ **4 Analytical Endpoints** - Query data warehouse insights
- ✅ **Rate Limiting** - 30-100 requests/minute per endpoint
- ✅ **Response Caching** - 1-5 minute TTL for performance
- ✅ **Auto-generated Docs** - OpenAPI/Swagger at `/docs`
- ✅ **Error Handling** - Consistent error responses with proper HTTP codes
- ✅ **Request Logging** - All requests logged with timing

## Testing

```bash
# Start API in one terminal
bash scripts/run_api.sh

# Run tests in another terminal
python3 scripts/test_api.py http://localhost:8000
```

## Documentation

- **Interactive API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Architecture

- **FastAPI** - Modern async web framework
- **Pydantic** - Request/response validation
- **SQLAlchemy** - Database connection pooling via `src.database`
- **SlowAPI** - Rate limiting
- **Structured Logging** - Via `src.logger_config`

## Production

```bash
# Using Gunicorn
gunicorn api.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000
```

**Note:** Add authentication, HTTPS, and CORS restrictions for production use.
