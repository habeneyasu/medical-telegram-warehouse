"""
Dagster pipeline for Medical Telegram Warehouse.

Orchestrates the complete ELT pipeline:
1. Scrape Telegram channels
2. Load raw data to PostgreSQL
3. Run YOLOv8 image detection
4. Load detection results to PostgreSQL
5. Transform data with dbt
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict

from dagster import (
    Config,
    Definitions,
    EnvVar,
    In,
    JobDefinition,
    OpExecutionContext,
    ScheduleDefinition,
    Field,
    job,
    op,
    schedule,
)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.database import test_connection
from src.logger_config import setup_logger

logger = setup_logger(__name__)


# Pipeline configuration schema
pipeline_config_schema = {
    "channels": Field(str, default_value="tikvahpharma", description="Comma-separated channel names"),
    "skip_scraping": Field(bool, default_value=False, description="Skip scraping if data already exists"),
}


@op(
    description="Scrape Telegram channels for messages and images",
    tags={"stage": "extract"},
    config_schema=pipeline_config_schema,
)
def scrape_telegram_data(context: OpExecutionContext) -> Dict[str, int]:
    """Scrape Telegram channels and download messages/images."""
    config = context.op_config
    
    if config.get("skip_scraping", False):
        context.log.info("Skipping scraping (skip_scraping=True)")
        return {"messages": 0, "images": 0}
    
    channels = config.get("channels", "tikvahpharma")
    context.log.info(f"Starting Telegram scraper for channels: {channels}")
    
    try:
        # Run scraper script
        script_path = Path(__file__).parent / "scripts" / "run_scraper.py"
        channels_list = [c.strip() for c in channels.split(",")]
        
        cmd = [sys.executable, str(script_path)] + channels_list
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).parent,
        )
        
        context.log.info(f"Scraper output: {result.stdout[-500:]}")  # Last 500 chars
        
        # Parse output to get counts (simplified)
        messages = result.stdout.count("Message saved") or 0
        images = result.stdout.count("Image downloaded") or 0
        
        context.log.info(f"✓ Scraping complete: {messages} messages, {images} images")
        return {"messages": messages, "images": images}
        
    except subprocess.CalledProcessError as e:
        context.log.error(f"Scraper failed: {e.stderr}")
        raise
    except Exception as e:
        context.log.error(f"Unexpected error in scraper: {e}", exc_info=True)
        raise


@op(
    description="Load raw JSON data to PostgreSQL",
    tags={"stage": "load"},
)
def load_raw_to_postgres(context: OpExecutionContext) -> Dict[str, int]:
    """Load scraped JSON files to PostgreSQL raw schema."""
    context.log.info("Loading raw data to PostgreSQL...")
    
    # Test database connection
    if not test_connection():
        raise Exception("Database connection failed")
    
    try:
        script_path = Path(__file__).parent / "scripts" / "load_raw_to_postgres.py"
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).parent,
        )
        
        context.log.info(f"Load output: {result.stdout[-500:]}")
        
        # Extract loaded count from output
        loaded_count = 0
        for line in result.stdout.split("\n"):
            if "rows loaded" in line.lower() or "inserted" in line.lower():
                try:
                    loaded_count = int(line.split()[0])
                    break
                except (ValueError, IndexError):
                    pass
        
        context.log.info(f"✓ Loaded {loaded_count} messages to PostgreSQL")
        return {"loaded_messages": loaded_count}
        
    except subprocess.CalledProcessError as e:
        context.log.error(f"Load failed: {e.stderr}")
        raise
    except Exception as e:
        context.log.error(f"Unexpected error loading data: {e}", exc_info=True)
        raise


@op(
    description="Run YOLOv8 image detection and classification",
    tags={"stage": "enrich"},
)
def run_yolo_enrichment(context: OpExecutionContext) -> Dict[str, int]:
    """Run YOLOv8 detection on scraped images."""
    context.log.info("Running YOLOv8 image detection...")
    
    try:
        script_path = Path(__file__).parent / "src" / "yolo_detect.py"
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).parent,
        )
        
        context.log.info(f"YOLO output: {result.stdout[-500:]}")
        
        # Extract detection count
        detected_count = 0
        for line in result.stdout.split("\n"):
            if "processed" in line.lower() or "detected" in line.lower():
                try:
                    detected_count = int(line.split()[0])
                    break
                except (ValueError, IndexError):
                    pass
        
        context.log.info(f"✓ YOLO detection complete: {detected_count} images processed")
        return {"detected_images": detected_count}
        
    except subprocess.CalledProcessError as e:
        context.log.error(f"YOLO detection failed: {e.stderr}")
        raise
    except Exception as e:
        context.log.error(f"Unexpected error in YOLO: {e}", exc_info=True)
        raise


@op(
    description="Load YOLO detection results to PostgreSQL",
    tags={"stage": "load"},
    ins={"yolo_result": In()},  # Dependency on YOLO op
)
def load_detections_to_postgres(context: OpExecutionContext, yolo_result: Dict[str, int]) -> Dict[str, int]:
    """Load YOLO detection results from CSV to PostgreSQL."""
    context.log.info("Loading detection results to PostgreSQL...")
    
    csv_path = Path(__file__).parent / "data" / "processed" / "image_detections.csv"
    if not csv_path.exists():
        context.log.warning("No detection CSV found, skipping...")
        return {"loaded_detections": 0}
    
    try:
        script_path = Path(__file__).parent / "scripts" / "load_detections_to_postgres.py"
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).parent,
        )
        
        context.log.info(f"Load detections output: {result.stdout[-500:]}")
        
        # Extract loaded count
        loaded_count = 0
        for line in result.stdout.split("\n"):
            if "rows loaded" in line.lower() or "inserted" in line.lower():
                try:
                    loaded_count = int(line.split()[0])
                    break
                except (ValueError, IndexError):
                    pass
        
        context.log.info(f"✓ Loaded {loaded_count} detection results")
        return {"loaded_detections": loaded_count}
        
    except subprocess.CalledProcessError as e:
        context.log.error(f"Load detections failed: {e.stderr}")
        raise
    except Exception as e:
        context.log.error(f"Unexpected error loading detections: {e}", exc_info=True)
        raise


@op(
    description="Run dbt transformations to create star schema",
    tags={"stage": "transform"},
    ins={"load_result": In(), "detections_result": In()},  # Dependencies
)
def run_dbt_transformations(
    context: OpExecutionContext,
    load_result: Dict[str, int],
    detections_result: Dict[str, int],
) -> Dict[str, str]:
    """Execute dbt models to transform data into star schema."""
    context.log.info("Running dbt transformations...")
    
    dbt_project_dir = Path(__file__).parent / "medical_warehouse"
    
    try:
        # Install dbt packages
        context.log.info("Installing dbt packages...")
        deps_result = subprocess.run(
            ["bash", "scripts/run_dbt.sh", "deps"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).parent,
        )
        context.log.info("✓ dbt packages installed")
        
        # Run dbt models
        context.log.info("Running dbt models...")
        run_result = subprocess.run(
            ["bash", "scripts/run_dbt.sh", "run"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).parent,
        )
        
        # Extract model count from output
        models_run = run_result.stdout.count("OK created") or 0
        
        # Run dbt tests
        context.log.info("Running dbt tests...")
        test_result = subprocess.run(
            ["bash", "scripts/run_dbt.sh", "test"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).parent,
        )
        
        tests_passed = test_result.stdout.count("PASS") or 0
        
        context.log.info(f"✓ dbt complete: {models_run} models, {tests_passed} tests passed")
        return {
            "models_run": str(models_run),
            "tests_passed": str(tests_passed),
            "status": "success",
        }
        
    except subprocess.CalledProcessError as e:
        context.log.error(f"dbt failed: {e.stderr}")
        raise
    except Exception as e:
        context.log.error(f"Unexpected error in dbt: {e}", exc_info=True)
        raise


@job(
    description="Complete ELT pipeline for Medical Telegram Warehouse",
    tags={"pipeline": "medical_telegram_warehouse"},
)
def medical_telegram_pipeline():
    """
    Main pipeline job orchestrating the complete data pipeline.
    
    Execution order:
    1. Scrape Telegram channels
    2. Load raw data to PostgreSQL (depends on scraping)
    3. Run YOLOv8 image detection (depends on scraping)
    4. Load detection results to PostgreSQL (depends on YOLO)
    5. Transform data with dbt (depends on all previous steps)
    """
    # Extract
    scrape_result = scrape_telegram_data()
    
    # Load raw data (depends on scraping)
    load_result = load_raw_to_postgres()
    
    # Enrich with YOLO (depends on scraping for images)
    yolo_result = run_yolo_enrichment()
    
    # Load detections (depends on YOLO)
    detections_result = load_detections_to_postgres(yolo_result)
    
    # Transform (depends on both load operations)
    dbt_result = run_dbt_transformations(load_result, detections_result)


@schedule(
    job=medical_telegram_pipeline,
    cron_schedule="0 2 * * *",  # Daily at 2 AM
    description="Daily pipeline run at 2 AM",
)
def daily_pipeline_schedule(context):
    """Schedule pipeline to run daily at 2 AM."""
    return {
        "ops": {
            "scrape_telegram_data": {
                "config": {
                    "channels": os.getenv("PIPELINE_CHANNELS", "tikvahpharma"),
                    "skip_scraping": False,
                }
            }
        }
    }


defs = Definitions(
    jobs=[medical_telegram_pipeline],
    schedules=[daily_pipeline_schedule],
)
