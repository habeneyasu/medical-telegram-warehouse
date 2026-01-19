#!/usr/bin/env python3
"""
YOLOv8 Object Detection for Telegram Images.

This script:
1. Uses YOLOv8n (nano) model for efficient processing on standard laptops
2. Scans images downloaded in Task 1
3. Runs detection on each image
4. Records detected objects with confidence scores
5. Classifies images based on detected objects
6. Saves results to CSV file
"""

import csv
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ultralytics import YOLO

from src.logger_config import setup_logger

# Setup logger
logger = setup_logger(__name__, log_file="yolo_detect.log")

# Image directory from Task 1
IMAGES_DIR = Path("data/raw/images")
OUTPUT_CSV = Path("data/processed/image_detections.csv")


def load_yolo_model():
    """Load YOLOv8n (nano) model - efficient for standard laptops."""
    logger.info("Loading YOLOv8n model (yolov8n.pt)...")
    try:
        model = YOLO("yolov8n.pt")  # Nano model - fastest and smallest
        logger.info("✓ YOLOv8n model loaded successfully")
        return model
    except FileNotFoundError as e:
        logger.error(f"YOLOv8 model file not found: {e}")
        logger.error("The model will be downloaded automatically on first run")
        raise
    except Exception as e:
        logger.error(f"Error loading YOLOv8 model: {e}", exc_info=True)
        logger.error("Make sure ultralytics is installed: pip install ultralytics")
        raise


def extract_channel_and_message_id(image_path: Path) -> Optional[tuple]:
    """
    Extract channel name and message_id from image path.
    
    Expected structure: data/raw/images/{channel_name}/{message_id}.jpg
    """
    try:
        # Get relative path from IMAGES_DIR
        rel_path = image_path.relative_to(IMAGES_DIR)
        parts = rel_path.parts
        
        if len(parts) >= 2:
            channel_name = parts[0]
            message_id_str = parts[1].replace('.jpg', '').replace('.jpeg', '').replace('.png', '')
            message_id = int(message_id_str)
            return channel_name, message_id
    except (ValueError, IndexError) as e:
        logger.warning(f"Could not parse path {image_path}: {e}")
    
    return None


def classify_image(detected_classes: Set[str]) -> str:
    """
    Classify image based on detected objects.
    
    Classification scheme:
    - promotional: Contains person + product (someone showing/holding item)
    - product_display: Contains bottle/container, no person
    - lifestyle: Contains person, no product
    - other: Neither detected
    
    Args:
        detected_classes: Set of detected class names (lowercase)
    
    Returns:
        Classification category string
    """
    # Person-related classes
    person_classes = {'person', 'people', 'man', 'woman', 'child', 'boy', 'girl'}
    
    # Product-related classes (bottles, containers, medical items)
    product_classes = {
        'bottle', 'container', 'cup', 'bowl', 'vase', 'jar',
        'potted plant', 'plant', 'book', 'cell phone', 'laptop',
        'handbag', 'backpack', 'suitcase', 'bag'
    }
    
    # Medical/pharmaceutical related (if detected)
    medical_classes = {
        'pills', 'medicine', 'tablet', 'capsule'  # These may not be in COCO, but we check anyway
    }
    
    has_person = any(cls in detected_classes for cls in person_classes)
    has_product = any(cls in detected_classes for cls in product_classes) or any(cls in detected_classes for cls in medical_classes)
    
    # Classification logic
    if has_person and has_product:
        return 'promotional'
    elif has_product and not has_person:
        return 'product_display'
    elif has_person and not has_product:
        return 'lifestyle'
    else:
        return 'other'


def process_image(model: YOLO, image_path: Path) -> Optional[Dict]:
    """
    Process a single image with YOLOv8 and return detection results.
    
    Returns:
        Dictionary with detection results or None if error
    """
    try:
        # Run inference
        results = model(image_path, verbose=False)
        
        detected_classes = set()
        all_detections = []
        max_confidence = 0.0
        
        # Extract detections from results
        for result in results:
            boxes = result.boxes
            
            for box in boxes:
                # Get class name, confidence, and bounding box
                class_id = int(box.cls[0])
                class_name = model.names[class_id].lower()  # Lowercase for classification
                confidence = float(box.conf[0])
                
                detected_classes.add(class_name)
                max_confidence = max(max_confidence, confidence)
                
                # Get bounding box coordinates (x1, y1, x2, y2)
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                
                all_detections.append({
                    'class_name': model.names[class_id],  # Original case for CSV
                    'confidence': confidence,
                    'bbox_x1': round(x1, 2),
                    'bbox_y1': round(y1, 2),
                    'bbox_x2': round(x2, 2),
                    'bbox_y2': round(y2, 2)
                })
        
        # Extract channel and message_id from path
        channel_message = extract_channel_and_message_id(image_path)
        if not channel_message:
            return None
        
        channel_name, message_id = channel_message
        
        # Classify image
        image_category = classify_image(detected_classes)
        
        # Create comma-separated list of detected classes
        detected_classes_str = ', '.join(sorted([d['class_name'] for d in all_detections]))
        
        return {
            'image_path': str(image_path),
            'channel_name': channel_name,
            'message_id': message_id,
            'detected_classes': detected_classes_str,
            'total_detections': len(all_detections),
            'max_confidence': round(max_confidence, 4) if all_detections else 0.0,
            'image_category': image_category,
            'processed_at': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error processing {image_path}: {e}", exc_info=True)
        return None


def process_channel_images(model: YOLO, channel_dir: Path) -> List[Dict]:
    """Process all images in a channel directory."""
    channel_name = channel_dir.name
    image_files = list(channel_dir.glob("*.jpg")) + list(channel_dir.glob("*.jpeg")) + list(channel_dir.glob("*.png"))
    
    if not image_files:
        logger.debug(f"No images found in {channel_name}")
        return []
    
    logger.info(f"Processing {len(image_files)} images in {channel_name}...")
    
    results = []
    processed = 0
    errors = 0
    
    for image_path in image_files:
        try:
            result = process_image(model, image_path)
            
            if result:
                results.append(result)
                processed += 1
                
                # Progress indicator every 50 images
                if processed % 50 == 0:
                    logger.debug(f"Processed {processed}/{len(image_files)} images in {channel_name}...")
            else:
                errors += 1
        except Exception as e:
            logger.error(f"Unexpected error processing {image_path}: {e}", exc_info=True)
            errors += 1
    
    logger.info(f"✓ Processed {processed}/{len(image_files)} images in {channel_name} (errors: {errors})")
    
    return results


def save_to_csv(results: List[Dict], output_file: Path):
    """Save detection results to CSV file."""
    if not results:
        logger.warning("No results to save")
        return False
    
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # CSV columns
        fieldnames = [
            'message_id',
            'channel_name',
            'image_path',
            'detected_classes',
            'total_detections',
            'max_confidence',
            'image_category',
            'processed_at'
        ]
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in results:
                # Only write the fields we want in CSV
                row = {field: result.get(field, '') for field in fieldnames}
                writer.writerow(row)
        
        logger.info(f"✓ Saved {len(results)} detection results to {output_file}")
        return True
    except PermissionError as e:
        logger.error(f"Permission denied writing to {output_file}: {e}")
        return False
    except Exception as e:
        logger.error(f"Error saving CSV file: {e}", exc_info=True)
        return False


def main():
    """Main function to run image detection on all scraped images."""
    logger.info("="*60)
    logger.info("YOLOv8 Image Detection - Medical Telegram Warehouse")
    logger.info("="*60)
    
    try:
        # Check images directory
        if not IMAGES_DIR.exists():
            logger.error(f"Images directory not found: {IMAGES_DIR}")
            sys.exit(1)
        
        # Load YOLOv8n model
        try:
            model = load_yolo_model()
        except Exception as e:
            logger.error("Failed to load YOLOv8 model")
            sys.exit(1)
        
        # Find all channel directories
        channel_dirs = [d for d in IMAGES_DIR.iterdir() if d.is_dir()]
        
        if not channel_dirs:
            logger.warning(f"No channel directories found in {IMAGES_DIR}")
            sys.exit(0)
        
        logger.info(f"Found {len(channel_dirs)} channel directories")
        logger.info("-"*60)
        
        all_results = []
        
        # Process each channel
        for channel_dir in sorted(channel_dirs):
            logger.info(f"Processing channel: {channel_dir.name}")
            channel_results = process_channel_images(model, channel_dir)
            all_results.extend(channel_results)
        
        # Save results to CSV
        if all_results:
            if save_to_csv(all_results, OUTPUT_CSV):
                logger.info("="*60)
                logger.info("Detection Summary")
                logger.info("="*60)
                logger.info(f"Total images processed: {len(all_results)}")
                
                # Count by category
                category_counts = {}
                for result in all_results:
                    category = result['image_category']
                    category_counts[category] = category_counts.get(category, 0) + 1
                
                logger.info("\nImage Classification Breakdown:")
                for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
                    percentage = (count / len(all_results)) * 100
                    logger.info(f"  {category}: {count} ({percentage:.1f}%)")
                
                # Count unique objects detected
                all_classes = set()
                for result in all_results:
                    if result['detected_classes']:
                        classes = [c.strip() for c in result['detected_classes'].split(',')]
                        all_classes.update(classes)
                
                logger.info(f"\nUnique object classes detected: {len(all_classes)}")
                logger.info(f"Top 10 detected objects:")
                
                # Count object frequencies
                class_counts = {}
                for result in all_results:
                    if result['detected_classes']:
                        classes = [c.strip() for c in result['detected_classes'].split(',')]
                        for class_name in classes:
                            class_counts[class_name] = class_counts.get(class_name, 0) + 1
                
                # Sort by frequency
                sorted_classes = sorted(class_counts.items(), key=lambda x: x[1], reverse=True)
                for class_name, count in sorted_classes[:10]:
                    logger.info(f"  {class_name}: {count}")
                
                logger.info("="*60)
                logger.info(f"✓ Detection complete! Results saved to {OUTPUT_CSV}")
            else:
                logger.error("Failed to save results to CSV")
                sys.exit(1)
        else:
            logger.warning("No images were processed")
            
    except KeyboardInterrupt:
        logger.warning("Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
