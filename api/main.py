"""
FastAPI Analytical API for Medical Telegram Warehouse.

This API exposes analytical endpoints that query the data warehouse
to answer business questions about Telegram channel data.

Endpoints:
- GET /api/reports/top-products - Most frequently mentioned products
- GET /api/channels/{channel_name}/activity - Channel posting activity
- GET /api/search/messages - Search messages by keyword
- GET /api/reports/visual-content - Visual content statistics
- GET /health - Health check endpoint
"""

import sys
from pathlib import Path
from datetime import datetime, date
from typing import Optional
from functools import lru_cache, wraps
import time

from fastapi import FastAPI, Depends, HTTPException, Query, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import psycopg2
from psycopg2.extras import RealDictCursor
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from typing import Any, Callable

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.database import get_db, check_database_health
from api.schemas import (
    TopProductsResponse,
    ProductTerm,
    ChannelActivityResponse,
    DailyActivity,
    MessageSearchResponse,
    MessageSearchResult,
    VisualContentStatsResponse,
    ChannelVisualStats,
    HealthCheckResponse,
    ErrorResponse
)
from src.logger_config import setup_logger

# Initialize logger
logger = setup_logger(__name__, log_file="api.log")

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Simple in-memory cache for API responses
_cache: dict = {}
_cache_timestamps: dict = {}


def cached(expire_seconds: int = 60):
    """
    Simple cache decorator for API endpoints.
    
    Args:
        expire_seconds: Cache expiration time in seconds
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            # Exclude Request objects from cache key (they're not hashable and vary per request)
            cache_kwargs = {k: v for k, v in kwargs.items() if k != 'request' and not hasattr(v, 'client')}
            cache_key = f"{func.__name__}:{str(sorted(cache_kwargs.items()))}"
            
            # Check if cached and not expired
            if cache_key in _cache:
                timestamp = _cache_timestamps.get(cache_key, 0)
                if time.time() - timestamp < expire_seconds:
                    logger.debug(f"Cache hit for {func.__name__}")
                    return _cache[cache_key]
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            _cache[cache_key] = result
            _cache_timestamps[cache_key] = time.time()
            logger.debug(f"Cached result for {func.__name__}")
            
            # Cleanup old cache entries (simple cleanup)
            if len(_cache) > 100:
                current_time = time.time()
                expired_keys = [
                    k for k, ts in _cache_timestamps.items()
                    if current_time - ts > expire_seconds * 2
                ]
                for k in expired_keys:
                    _cache.pop(k, None)
                    _cache_timestamps.pop(k, None)
            
            return result
        return wrapper
    return decorator

# Initialize FastAPI app
app = FastAPI(
    title="Medical Telegram Warehouse API",
    description="""
    Analytical API for querying medical product data from Telegram channels.
    
    ## Features
    
    * **Top Products**: Find most frequently mentioned products across channels
    * **Channel Activity**: Analyze posting patterns and engagement metrics
    * **Message Search**: Search messages by keywords with relevance scoring
    * **Visual Content**: Statistics on image usage and classifications
    
    ## Authentication
    
    Currently, this API does not require authentication. In production,
    implement API key or OAuth2 authentication.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add rate limiter to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Startup/Shutdown Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize cache and verify database connection on startup."""
    logger.info("Starting Medical Telegram Warehouse API...")
    
    # Cache is initialized via decorator
    logger.info("Cache system initialized (in-memory)")
    
    # Verify database connection
    db_status = check_database_health()
    if db_status == "connected":
        logger.info("✓ Database connection verified")
    else:
        logger.warning("⚠ Database connection not available - some endpoints may fail")
    
    logger.info("API startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down API...")


# ============================================================================
# Request/Response Middleware
# ============================================================================

@app.middleware("http")
async def log_requests(request, call_next):
    """Log all API requests with timing information."""
    start_time = time.time()
    
    logger.info(f"Request: {request.method} {request.url.path} - Client: {request.client.host if request.client else 'unknown'}")
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(f"Response: {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.3f}s")
        response.headers["X-Process-Time"] = str(process_time)
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"Error: {request.method} {request.url.path} - Time: {process_time:.3f}s - Error: {str(e)}", exc_info=True)
        raise


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Handle HTTP exceptions with consistent error format."""
    logger.warning(f"HTTP {exc.status_code}: {exc.detail} - Path: {request.url.path}")
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            status_code=exc.status_code
        ).dict()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {str(exc)} - Path: {request.url.path}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="Internal server error",
            detail="An unexpected error occurred. Please try again later.",
            status_code=500
        ).dict()
    )


# ============================================================================
# Health Check Endpoint
# ============================================================================

@app.get(
    "/health",
    response_model=HealthCheckResponse,
    tags=["System"],
    summary="Health Check",
    description="Check API and database connection health"
)
async def health_check():
    """
    Health check endpoint.
    
    Returns the status of the API and database connection.
    """
    db_status = check_database_health()
    return HealthCheckResponse(
        status="healthy" if db_status == "connected" else "degraded",
        database=db_status
    )


# ============================================================================
# Endpoint 1: Top Products
# ============================================================================

@app.get(
    "/api/reports/top-products",
    response_model=TopProductsResponse,
    tags=["Reports"],
    summary="Top Products",
    description="""
    Returns the most frequently mentioned product terms across all channels.
    
    Extracts meaningful terms from message text and ranks them by frequency.
    Useful for identifying trending products and keywords.
    
    Results are cached for 5 minutes to improve performance.
    """
)
@limiter.limit("30/minute")  # Rate limit: 30 requests per minute
@cached(expire_seconds=300)  # Cache for 5 minutes
async def get_top_products(
    request: Request,
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results to return"),
    min_length: int = Query(4, ge=2, le=20, description="Minimum term length to consider"),
    db = Depends(get_db)
):
    """
    Get top products by frequency across all channels.
    
    Args:
        limit: Maximum number of products to return (1-100)
        min_length: Minimum term length to consider (2-20)
        db: Database connection (injected)
        
    Returns:
        TopProductsResponse with ranked product terms
    """
    try:
        logger.info(f"Fetching top {limit} products (min_length={min_length})")
        
        with db.cursor(cursor_factory=RealDictCursor) as cursor:
            # Extract terms from message text using word boundaries
            # Filter out common stop words and short terms
            query = """
                WITH message_terms AS (
                    SELECT
                        unnest(string_to_array(lower(trim(message_text)), ' ')) as term
                    FROM staging_marts.fct_messages
                    WHERE message_text IS NOT NULL
                        AND length(trim(message_text)) > 0
                ),
                filtered_terms AS (
                    SELECT term
                    FROM message_terms
                    WHERE length(term) >= %s
                        AND term !~ '^[0-9]+$'  -- Exclude pure numbers
                        AND term NOT IN ('the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'from', 'is', 'are', 'was', 'were', 'a', 'an')
                ),
                term_counts AS (
                    SELECT
                        term,
                        COUNT(*) as frequency
                    FROM filtered_terms
                    GROUP BY term
                    HAVING COUNT(*) >= 2  -- At least 2 occurrences
                ),
                total_count AS (
                    SELECT SUM(frequency) as total FROM term_counts
                )
                SELECT
                    tc.term,
                    tc.frequency,
                    ROUND((tc.frequency::numeric / NULLIF(tc_total.total, 0)) * 100, 2) as percentage
                FROM term_counts tc
                CROSS JOIN total_count tc_total
                ORDER BY tc.frequency DESC, tc.term ASC
                LIMIT %s
            """
            
            cursor.execute(query, (min_length, limit))
            results = cursor.fetchall()
            
            # Get total unique terms
            cursor.execute("""
                SELECT COUNT(DISTINCT term) as total
                FROM (
                    SELECT unnest(string_to_array(lower(trim(message_text)), ' ')) as term
                    FROM staging_marts.fct_messages
                    WHERE message_text IS NOT NULL
                        AND length(trim(message_text)) > 0
                ) terms
                WHERE length(term) >= %s
                    AND term !~ '^[0-9]+$'
                    AND term NOT IN ('the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'from', 'is', 'are', 'was', 'were', 'a', 'an')
            """, (min_length,))
            total_terms = cursor.fetchone()['total'] or 0
            
            products = [
                ProductTerm(
                    term=row['term'],
                    frequency=row['frequency'],
                    percentage=float(row['percentage'] or 0)
                )
                for row in results
            ]
            
            logger.info(f"Found {len(products)} top products (total terms: {total_terms})")
            
            return TopProductsResponse(
                limit=limit,
                total_terms=total_terms,
                products=products
            )
            
    except psycopg2.Error as e:
        logger.error(f"Database error in get_top_products: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in get_top_products: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch top products"
        )


# ============================================================================
# Endpoint 2: Channel Activity
# ============================================================================

@app.get(
    "/api/channels/{channel_name}/activity",
    response_model=ChannelActivityResponse,
    tags=["Channels"],
    summary="Channel Activity",
    description="""
    Returns posting activity and engagement trends for a specific channel.
    
    Includes daily activity breakdown, total statistics, and engagement metrics.
    
    Results are cached for 2 minutes to improve performance.
    """
)
@limiter.limit("60/minute")  # Rate limit: 60 requests per minute
@cached(expire_seconds=120)  # Cache for 2 minutes
async def get_channel_activity(
    request: Request,
    channel_name: str,
    days: Optional[int] = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db = Depends(get_db)
):
    """
    Get channel activity and trends.
    
    Args:
        channel_name: Name of the Telegram channel
        days: Number of days to analyze (1-365)
        db: Database connection (injected)
        
    Returns:
        ChannelActivityResponse with activity statistics
    """
    try:
        logger.info(f"Fetching activity for channel: {channel_name} (last {days} days)")
        
        with db.cursor(cursor_factory=RealDictCursor) as cursor:
            # Check if channel exists
            cursor.execute("""
                SELECT channel_name, channel_type, first_post_date, last_post_date
                FROM staging_marts.dim_channels
                WHERE channel_name = %s
            """, (channel_name,))
            channel_info = cursor.fetchone()
            
            if not channel_info:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Channel '{channel_name}' not found"
                )
            
            # Get overall statistics
            cursor.execute("""
                SELECT
                    COUNT(*) as total_messages,
                    SUM(view_count) as total_views,
                    AVG(view_count) as avg_views,
                    SUM(forward_count) as total_forwards
                FROM staging_marts.fct_messages fm
                INNER JOIN staging_marts.dim_channels dc ON fm.channel_key = dc.channel_key
                WHERE dc.channel_name = %s
            """, (channel_name,))
            stats = cursor.fetchone()
            
            # Get daily activity
            cursor.execute("""
                SELECT
                    dd.full_date as date,
                    COUNT(*) as message_count,
                    SUM(fm.view_count) as total_views,
                    AVG(fm.view_count) as avg_views,
                    SUM(fm.forward_count) as total_forwards
                FROM staging_marts.fct_messages fm
                INNER JOIN staging_marts.dim_channels dc ON fm.channel_key = dc.channel_key
                INNER JOIN staging_marts.dim_dates dd ON fm.date_key = dd.date_key
                WHERE dc.channel_name = %s
                    AND dd.full_date >= CURRENT_DATE - INTERVAL '%s days'
                GROUP BY dd.full_date
                ORDER BY dd.full_date DESC
            """, (channel_name, days))
            daily_results = cursor.fetchall()
            
            daily_activity = [
                DailyActivity(
                    activity_date=row['date'],
                    message_count=row['message_count'],
                    total_views=row['total_views'] or 0,
                    avg_views=float(row['avg_views'] or 0),
                    total_forwards=row['total_forwards'] or 0
                )
                for row in daily_results
            ]
            
            logger.info(f"Found {len(daily_activity)} days of activity for {channel_name}")
            
            return ChannelActivityResponse(
                channel_name=channel_info['channel_name'],
                channel_type=channel_info['channel_type'],
                total_messages=stats['total_messages'] or 0,
                total_views=stats['total_views'] or 0,
                avg_views=float(stats['avg_views'] or 0),
                total_forwards=stats['total_forwards'] or 0,
                first_post_date=channel_info['first_post_date'],
                last_post_date=channel_info['last_post_date'],
                daily_activity=daily_activity
            )
            
    except HTTPException:
        raise
    except psycopg2.Error as e:
        logger.error(f"Database error in get_channel_activity: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in get_channel_activity: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch channel activity"
        )


# ============================================================================
# Endpoint 3: Message Search
# ============================================================================

@app.get(
    "/api/search/messages",
    response_model=MessageSearchResponse,
    tags=["Search"],
    summary="Search Messages",
    description="""
    Searches for messages containing a specific keyword.
    
    Uses PostgreSQL full-text search for efficient keyword matching.
    Results are ranked by relevance and include engagement metrics.
    
    Results are cached for 1 minute to improve performance.
    """
)
@limiter.limit("100/minute")  # Rate limit: 100 requests per minute
@cached(expire_seconds=60)  # Cache for 1 minute
async def search_messages(
    request: Request,
    query: str = Query(..., min_length=2, max_length=100, description="Search keyword"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    channel_name: Optional[str] = Query(None, description="Filter by channel name"),
    db = Depends(get_db)
):
    """
    Search messages by keyword.
    
    Args:
        query: Search keyword (2-100 characters)
        limit: Maximum results to return (1-100)
        channel_name: Optional channel filter
        db: Database connection (injected)
        
    Returns:
        MessageSearchResponse with matching messages
    """
    try:
        logger.info(f"Searching messages: query='{query}', limit={limit}, channel={channel_name}")
        
        with db.cursor(cursor_factory=RealDictCursor) as cursor:
            # Build query with optional channel filter
            base_query = """
                SELECT
                    fm.message_id,
                    dc.channel_name,
                    LEFT(fm.message_text, 500) as message_text,
                    fm.message_date,
                    fm.view_count,
                    fm.forward_count,
                    fm.has_image,
                    CASE
                        WHEN LOWER(fm.message_text) LIKE LOWER(%s) THEN 1.0
                        WHEN LOWER(fm.message_text) LIKE LOWER(%s) THEN 0.8
                        ELSE 0.5
                    END as relevance_score
                FROM staging_marts.fct_messages fm
                INNER JOIN staging_marts.dim_channels dc ON fm.channel_key = dc.channel_key
                WHERE LOWER(fm.message_text) LIKE LOWER(%s)
            """
            
            params = [
                f"%{query}%",  # Exact match pattern
                f"%{query}%",  # Partial match pattern
                f"%{query}%"   # Search pattern
            ]
            
            if channel_name:
                base_query += " AND dc.channel_name = %s"
                params.append(channel_name)
            
            # Get total count - replace the SELECT clause properly
            count_query = """
                SELECT COUNT(*) as total
                FROM staging_marts.fct_messages fm
                INNER JOIN staging_marts.dim_channels dc ON fm.channel_key = dc.channel_key
                WHERE LOWER(fm.message_text) LIKE LOWER(%s)
            """
            count_params = [f"%{query}%"]
            if channel_name:
                count_query += " AND dc.channel_name = %s"
                count_params.append(channel_name)
            
            cursor.execute(count_query, count_params)
            total_found = cursor.fetchone()['total'] or 0
            
            # Get results
            base_query += """
                ORDER BY relevance_score DESC, fm.view_count DESC, fm.message_date DESC
                LIMIT %s
            """
            params.append(limit)
            
            cursor.execute(base_query, params)
            results = cursor.fetchall()
            
            messages = [
                MessageSearchResult(
                    message_id=row['message_id'],
                    channel_name=row['channel_name'],
                    message_text=row['message_text'],
                    message_date=row['message_date'],
                    view_count=row['view_count'],
                    forward_count=row['forward_count'],
                    has_image=row['has_image'],
                    relevance_score=float(row['relevance_score'])
                )
                for row in results
            ]
            
            logger.info(f"Found {len(messages)} messages matching '{query}' (total: {total_found})")
            
            return MessageSearchResponse(
                query=query,
                limit=limit,
                total_found=total_found,
                results=messages
            )
            
    except psycopg2.Error as e:
        logger.error(f"Database error in search_messages: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in search_messages: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search messages"
        )


# ============================================================================
# Endpoint 4: Visual Content Stats
# ============================================================================

@app.get(
    "/api/reports/visual-content",
    response_model=VisualContentStatsResponse,
    tags=["Reports"],
    summary="Visual Content Statistics",
    description="""
    Returns statistics about image usage and classifications across channels.
    
    Includes breakdown by image category (promotional, product_display, lifestyle, other)
    and engagement metrics for visual content.
    
    Results are cached for 5 minutes to improve performance.
    """
)
@limiter.limit("30/minute")  # Rate limit: 30 requests per minute
@cached(expire_seconds=300)  # Cache for 5 minutes
async def get_visual_content_stats(
    request: Request,
    db = Depends(get_db)
):
    """
    Get visual content statistics across all channels.
    
    Args:
        db: Database connection (injected)
        
    Returns:
        VisualContentStatsResponse with visual content statistics
    """
    try:
        logger.info("Fetching visual content statistics")
        
        with db.cursor(cursor_factory=RealDictCursor) as cursor:
            # Get per-channel statistics
            cursor.execute("""
                SELECT
                    dc.channel_name,
                    COUNT(*) as total_images,
                    SUM(CASE WHEN fid.image_category = 'promotional' THEN 1 ELSE 0 END) as promotional_count,
                    SUM(CASE WHEN fid.image_category = 'product_display' THEN 1 ELSE 0 END) as product_display_count,
                    SUM(CASE WHEN fid.image_category = 'lifestyle' THEN 1 ELSE 0 END) as lifestyle_count,
                    SUM(CASE WHEN fid.image_category = 'other' THEN 1 ELSE 0 END) as other_count,
                    AVG(fid.total_detections) as avg_detections,
                    AVG(fid.max_confidence) as avg_confidence,
                    AVG(fid.view_count) as avg_views
                FROM staging_marts.fct_image_detections fid
                INNER JOIN staging_marts.dim_channels dc ON fid.channel_key = dc.channel_key
                GROUP BY dc.channel_name
                ORDER BY total_images DESC
            """)
            channel_results = cursor.fetchall()
            
            # Get overall statistics
            cursor.execute("""
                SELECT
                    COUNT(*) as total_images,
                    COUNT(DISTINCT dc.channel_name) as total_channels,
                    SUM(CASE WHEN fid.image_category = 'promotional' THEN 1 ELSE 0 END) as promotional_count,
                    SUM(CASE WHEN fid.image_category = 'product_display' THEN 1 ELSE 0 END) as product_display_count,
                    SUM(CASE WHEN fid.image_category = 'lifestyle' THEN 1 ELSE 0 END) as lifestyle_count,
                    SUM(CASE WHEN fid.image_category = 'other' THEN 1 ELSE 0 END) as other_count
                FROM staging_marts.fct_image_detections fid
                INNER JOIN staging_marts.dim_channels dc ON fid.channel_key = dc.channel_key
            """)
            overall = cursor.fetchone()
            
            total_images = overall['total_images'] or 0
            total_channels = overall['total_channels'] or 0
            
            # Calculate percentages
            promotional_pct = (overall['promotional_count'] / total_images * 100) if total_images > 0 else 0
            product_display_pct = (overall['product_display_count'] / total_images * 100) if total_images > 0 else 0
            lifestyle_pct = (overall['lifestyle_count'] / total_images * 100) if total_images > 0 else 0
            other_pct = (overall['other_count'] / total_images * 100) if total_images > 0 else 0
            
            channels = [
                ChannelVisualStats(
                    channel_name=row['channel_name'],
                    total_images=row['total_images'],
                    promotional_count=row['promotional_count'],
                    product_display_count=row['product_display_count'],
                    lifestyle_count=row['lifestyle_count'],
                    other_count=row['other_count'],
                    avg_detections=float(row['avg_detections'] or 0),
                    avg_confidence=float(row['avg_confidence'] or 0),
                    avg_views=float(row['avg_views'] or 0)
                )
                for row in channel_results
            ]
            
            logger.info(f"Found visual content stats: {total_images} images across {total_channels} channels")
            
            return VisualContentStatsResponse(
                total_images=total_images,
                total_channels=total_channels,
                overall_promotional_pct=round(promotional_pct, 2),
                overall_product_display_pct=round(product_display_pct, 2),
                overall_lifestyle_pct=round(lifestyle_pct, 2),
                overall_other_pct=round(other_pct, 2),
                channels=channels
            )
            
    except psycopg2.Error as e:
        logger.error(f"Database error in get_visual_content_stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in get_visual_content_stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch visual content statistics"
        )


# ============================================================================
# Root Endpoint
# ============================================================================

@app.get(
    "/",
    tags=["System"],
    summary="API Root",
    description="API information and available endpoints"
)
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Medical Telegram Warehouse API",
        "version": "1.0.0",
        "description": "Analytical API for medical product data from Telegram channels",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "top_products": "/api/reports/top-products",
            "channel_activity": "/api/channels/{channel_name}/activity",
            "search_messages": "/api/search/messages",
            "visual_content": "/api/reports/visual-content"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
