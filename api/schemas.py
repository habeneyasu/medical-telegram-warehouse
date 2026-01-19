"""
Pydantic schemas for FastAPI request/response validation.

This module defines all data models used for API request validation
and response serialization.
"""

from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field, validator


# ============================================================================
# Common Models
# ============================================================================

class ErrorResponse(BaseModel):
    """Standard error response schema."""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    status_code: int = Field(..., description="HTTP status code")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "Resource not found",
                "detail": "Channel 'invalid_channel' does not exist",
                "status_code": 404
            }
        }


class HealthCheckResponse(BaseModel):
    """Health check response schema."""
    status: str = Field(..., description="Service status")
    database: str = Field(..., description="Database connection status")
    timestamp: datetime = Field(default_factory=datetime.now, description="Check timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "database": "connected",
                "timestamp": "2026-01-19T10:00:00"
            }
        }


# ============================================================================
# Top Products Endpoint
# ============================================================================

class ProductTerm(BaseModel):
    """Product term with frequency statistics."""
    term: str = Field(..., description="Product term or keyword")
    frequency: int = Field(..., description="Number of occurrences")
    percentage: float = Field(..., description="Percentage of total messages", ge=0, le=100)

    class Config:
        json_schema_extra = {
            "example": {
                "term": "paracetamol",
                "frequency": 45,
                "percentage": 12.5
            }
        }


class TopProductsResponse(BaseModel):
    """Response for top products endpoint."""
    limit: int = Field(..., description="Number of results returned")
    total_terms: int = Field(..., description="Total unique terms found")
    products: List[ProductTerm] = Field(..., description="List of top products")
    generated_at: datetime = Field(default_factory=datetime.now, description="Response generation timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "limit": 10,
                "total_terms": 150,
                "products": [
                    {
                        "term": "paracetamol",
                        "frequency": 45,
                        "percentage": 12.5
                    }
                ],
                "generated_at": "2026-01-19T10:00:00"
            }
        }


# ============================================================================
# Channel Activity Endpoint
# ============================================================================

class DailyActivity(BaseModel):
    """Daily posting activity statistics."""
    activity_date: date = Field(..., description="Date of activity", alias="date")
    message_count: int = Field(..., description="Number of messages posted", ge=0)
    total_views: int = Field(..., description="Total views for the day", ge=0)
    avg_views: float = Field(..., description="Average views per message", ge=0)
    total_forwards: int = Field(..., description="Total forwards for the day", ge=0)

    class Config:
        populate_by_name = True  # Allow both field name and alias
        json_schema_extra = {
            "example": {
                "date": "2026-01-19",
                "message_count": 15,
                "total_views": 4500,
                "avg_views": 300.0,
                "total_forwards": 23
            }
        }


class ChannelActivityResponse(BaseModel):
    """Response for channel activity endpoint."""
    channel_name: str = Field(..., description="Channel name")
    channel_type: Optional[str] = Field(None, description="Channel classification type")
    total_messages: int = Field(..., description="Total messages in channel", ge=0)
    total_views: int = Field(..., description="Total views across all messages", ge=0)
    avg_views: float = Field(..., description="Average views per message", ge=0)
    total_forwards: int = Field(..., description="Total forwards", ge=0)
    first_post_date: Optional[date] = Field(None, description="Date of first post")
    last_post_date: Optional[date] = Field(None, description="Date of last post")
    daily_activity: List[DailyActivity] = Field(..., description="Daily activity breakdown")
    generated_at: datetime = Field(default_factory=datetime.now, description="Response generation timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "channel_name": "CheMed123",
                "channel_type": "Medical",
                "total_messages": 1250,
                "total_views": 375000,
                "avg_views": 300.0,
                "total_forwards": 450,
                "first_post_date": "2025-01-01",
                "last_post_date": "2026-01-19",
                "daily_activity": [],
                "generated_at": "2026-01-19T10:00:00"
            }
        }


# ============================================================================
# Message Search Endpoint
# ============================================================================

class MessageSearchResult(BaseModel):
    """Individual message search result."""
    message_id: int = Field(..., description="Message identifier")
    channel_name: str = Field(..., description="Channel where message was posted")
    message_text: str = Field(..., description="Message content (truncated if long)")
    message_date: datetime = Field(..., description="When message was posted")
    view_count: int = Field(..., description="Number of views", ge=0)
    forward_count: int = Field(..., description="Number of forwards", ge=0)
    has_image: bool = Field(..., description="Whether message contains image")
    relevance_score: Optional[float] = Field(None, description="Search relevance score", ge=0, le=1)

    class Config:
        json_schema_extra = {
            "example": {
                "message_id": 12345,
                "channel_name": "CheMed123",
                "message_text": "New paracetamol 500mg available...",
                "message_date": "2026-01-19T10:00:00",
                "view_count": 450,
                "forward_count": 12,
                "has_image": True,
                "relevance_score": 0.95
            }
        }


class MessageSearchResponse(BaseModel):
    """Response for message search endpoint."""
    query: str = Field(..., description="Search query used")
    limit: int = Field(..., description="Maximum results requested")
    total_found: int = Field(..., description="Total messages matching query", ge=0)
    results: List[MessageSearchResult] = Field(..., description="Search results")
    generated_at: datetime = Field(default_factory=datetime.now, description="Response generation timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "paracetamol",
                "limit": 20,
                "total_found": 45,
                "results": [],
                "generated_at": "2026-01-19T10:00:00"
            }
        }


# ============================================================================
# Visual Content Stats Endpoint
# ============================================================================

class ChannelVisualStats(BaseModel):
    """Visual content statistics for a channel."""
    channel_name: str = Field(..., description="Channel name")
    total_images: int = Field(..., description="Total images with detections", ge=0)
    promotional_count: int = Field(..., description="Number of promotional images", ge=0)
    product_display_count: int = Field(..., description="Number of product display images", ge=0)
    lifestyle_count: int = Field(..., description="Number of lifestyle images", ge=0)
    other_count: int = Field(..., description="Number of other category images", ge=0)
    avg_detections: float = Field(..., description="Average objects detected per image", ge=0)
    avg_confidence: float = Field(..., description="Average confidence score", ge=0, le=1)
    avg_views: float = Field(..., description="Average views for images", ge=0)

    class Config:
        json_schema_extra = {
            "example": {
                "channel_name": "CheMed123",
                "total_images": 850,
                "promotional_count": 320,
                "product_display_count": 280,
                "lifestyle_count": 150,
                "other_count": 100,
                "avg_detections": 3.5,
                "avg_confidence": 0.85,
                "avg_views": 450.0
            }
        }


class VisualContentStatsResponse(BaseModel):
    """Response for visual content statistics endpoint."""
    total_images: int = Field(..., description="Total images across all channels", ge=0)
    total_channels: int = Field(..., description="Number of channels with images", ge=0)
    overall_promotional_pct: float = Field(..., description="Overall promotional percentage", ge=0, le=100)
    overall_product_display_pct: float = Field(..., description="Overall product display percentage", ge=0, le=100)
    overall_lifestyle_pct: float = Field(..., description="Overall lifestyle percentage", ge=0, le=100)
    overall_other_pct: float = Field(..., description="Overall other category percentage", ge=0, le=100)
    channels: List[ChannelVisualStats] = Field(..., description="Per-channel statistics")
    generated_at: datetime = Field(default_factory=datetime.now, description="Response generation timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "total_images": 2500,
                "total_channels": 3,
                "overall_promotional_pct": 38.5,
                "overall_product_display_pct": 32.0,
                "overall_lifestyle_pct": 18.5,
                "overall_other_pct": 11.0,
                "channels": [],
                "generated_at": "2026-01-19T10:00:00"
            }
        }
