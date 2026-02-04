"""
CloudFront URL Importer
Import existing CloudFront image URLs into the database for processing
Supports: CSV, JSON, text files with product_group_id, sku_id, image_url
"""
import csv
import json
import sys
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_config, ProcessingStatus
from src.database import init_db, get_db, ProductImageRepository, SKURepository, ProductImage, SKU

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CloudFrontImporter:
    """Import CloudFront URLs into the database with SKU mapping"""
    
    def __init__(self):
        init_db()
        self.db = get_db()
        self.image_repo = ProductImageRepository(self.db)
        self.sku_repo = SKURepository(self.db)
        self.stats = {
            "total": 0,
            "imported": 0,
            "skipped": 0,
            "errors": 0,
            "skus_created": 0
        }
    
    def import_from_csv(
        self,
        csv_path: str,
        url_column: str = "image_url",
        sku_column: str = "sku_id",
        product_group_column: Optional[str] = "product_group_id",
        image_type_column: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Import URLs from CSV file
        
        Expected columns: sku_id, image_url, product_group_id (optional)
        
        Args:
            csv_path: Path to CSV file
            url_column: Column name containing image URLs
            sku_column: Column name containing SKU IDs
            product_group_column: Optional column for product group
            image_type_column: Optional column for image type (primary, side, etc.)
        
        Returns:
            Import statistics
        """
        path = Path(csv_path)
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        
        self.stats = {"total": 0, "imported": 0, "skipped": 0, "errors": 0, "skus_created": 0}
        
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            # Validate required columns
            if url_column not in reader.fieldnames:
                raise ValueError(f"URL column '{url_column}' not found. Available: {reader.fieldnames}")
            if sku_column not in reader.fieldnames:
                raise ValueError(f"SKU column '{sku_column}' not found. Available: {reader.fieldnames}")
            
            for row in reader:
                self.stats["total"] += 1
                
                try:
                    image_url = row[url_column].strip()
                    sku_id = row[sku_column].strip()
                    
                    if not image_url or not sku_id:
                        logger.warning(f"Row {self.stats['total']}: Missing URL or SKU ID")
                        self.stats["errors"] += 1
                        continue
                    
                    # Check if image already exists
                    existing = self.image_repo.get_by_url(image_url)
                    if existing:
                        self.stats["skipped"] += 1
                        continue
                    
                    # Get or create SKU
                    sku = self.sku_repo.get_by_sku_id(sku_id)
                    if not sku:
                        sku = self.sku_repo.create(sku_id=sku_id)
                        self.stats["skus_created"] += 1
                    
                    # Extract optional fields
                    product_group_id = None
                    if product_group_column and product_group_column in row:
                        product_group_id = row[product_group_column].strip() or None
                    
                    image_type = "primary"
                    if image_type_column and image_type_column in row:
                        image_type = row[image_type_column].strip() or "primary"
                    
                    # Create image record
                    self.image_repo.create(
                        sku_ref=sku.id,
                        product_group_id=product_group_id,
                        sku_id=sku_id,
                        image_url=image_url,
                        image_type=image_type,
                        status=ProcessingStatus.PENDING.value
                    )
                    self.stats["imported"] += 1
                    
                    if self.stats["imported"] % 100 == 0:
                        logger.info(f"Imported {self.stats['imported']} images...")
                    
                except Exception as e:
                    logger.error(f"Error importing row {self.stats['total']}: {e}")
                    self.stats["errors"] += 1
        
        # Update SKU image counts
        self._update_sku_counts()
        
        logger.info(f"CSV import complete: {self.stats}")
        return self.stats
    
    def import_from_json(self, json_path: str) -> Dict[str, Any]:
        """
        Import URLs from JSON file
        
        Expected format:
        [
            {"sku_id": "SKU001", "image_url": "https://...", "product_group_id": "PG001"},
            ...
        ]
        """
        path = Path(json_path)
        if not path.exists():
            raise FileNotFoundError(f"JSON file not found: {json_path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.stats = {"total": 0, "imported": 0, "skipped": 0, "errors": 0, "skus_created": 0}
        
        if isinstance(data, list):
            for item in data:
                self.stats["total"] += 1
                
                try:
                    if isinstance(item, dict):
                        image_url = item.get("image_url", "").strip()
                        sku_id = item.get("sku_id", "").strip()
                        product_group_id = item.get("product_group_id", "").strip() or None
                        image_type = item.get("image_type", "primary").strip()
                    else:
                        logger.warning(f"Invalid item format: {item}")
                        self.stats["errors"] += 1
                        continue
                    
                    if not image_url or not sku_id:
                        logger.warning(f"Missing URL or SKU ID: {item}")
                        self.stats["errors"] += 1
                        continue
                    
                    # Check if exists
                    existing = self.image_repo.get_by_url(image_url)
                    if existing:
                        self.stats["skipped"] += 1
                        continue
                    
                    # Get or create SKU
                    sku = self.sku_repo.get_by_sku_id(sku_id)
                    if not sku:
                        sku = self.sku_repo.create(sku_id=sku_id)
                        self.stats["skus_created"] += 1
                    
                    # Create image record
                    self.image_repo.create(
                        sku_ref=sku.id,
                        product_group_id=product_group_id,
                        sku_id=sku_id,
                        image_url=image_url,
                        image_type=image_type,
                        status=ProcessingStatus.PENDING.value
                    )
                    self.stats["imported"] += 1
                    
                except Exception as e:
                    logger.error(f"Error importing item: {e}")
                    self.stats["errors"] += 1
        
        self._update_sku_counts()
        logger.info(f"JSON import complete: {self.stats}")
        return self.stats
    
    def import_from_list(
        self,
        images: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Import from a list of dictionaries
        
        Args:
            images: List of dicts with keys: sku_id, image_url, product_group_id (optional)
        """
        self.stats = {"total": len(images), "imported": 0, "skipped": 0, "errors": 0, "skus_created": 0}
        
        for img_data in images:
            try:
                image_url = img_data.get("image_url", "").strip()
                sku_id = img_data.get("sku_id", "").strip()
                product_group_id = img_data.get("product_group_id", "").strip() or None
                image_type = img_data.get("image_type", "primary")
                
                if not image_url or not sku_id:
                    self.stats["errors"] += 1
                    continue
                
                # Check if exists
                existing = self.image_repo.get_by_url(image_url)
                if existing:
                    self.stats["skipped"] += 1
                    continue
                
                # Get or create SKU
                sku = self.sku_repo.get_by_sku_id(sku_id)
                if not sku:
                    sku = self.sku_repo.create(sku_id=sku_id)
                    self.stats["skus_created"] += 1
                
                # Create record
                self.image_repo.create(
                    sku_ref=sku.id,
                    product_group_id=product_group_id,
                    sku_id=sku_id,
                    image_url=image_url,
                    image_type=image_type,
                    status=ProcessingStatus.PENDING.value
                )
                self.stats["imported"] += 1
                
            except Exception as e:
                logger.error(f"Error importing {image_url}: {e}")
                self.stats["errors"] += 1
        
        self._update_sku_counts()
        logger.info(f"Import complete: {self.stats}")
        return self.stats
    
    def _update_sku_counts(self):
        """Update image counts for all affected SKUs"""
        try:
            skus = self.db.query(SKU).all()
            for sku in skus:
                self.sku_repo.update_image_counts(sku.sku_id)
        except Exception as e:
            logger.error(f"Error updating SKU counts: {e}")
    
    def generate_sample_csv(self, output_path: str = "sample_urls.csv"):
        """Generate sample CSV template with correct columns"""
        sample_data = [
            {
                "product_group_id": "PG-MEDICAL-001",
                "sku_id": "MED-SKU-001",
                "image_url": "https://d1234567890.cloudfront.net/products/med-001-primary.jpg",
                "image_type": "primary"
            },
            {
                "product_group_id": "PG-MEDICAL-001",
                "sku_id": "MED-SKU-001",
                "image_url": "https://d1234567890.cloudfront.net/products/med-001-side.jpg",
                "image_type": "side"
            },
            {
                "product_group_id": "PG-EQUIPMENT-002",
                "sku_id": "EQP-SKU-002",
                "image_url": "https://d1234567890.cloudfront.net/products/eqp-002-primary.jpg",
                "image_type": "primary"
            },
            {
                "product_group_id": "PG-CONSUMABLES-003",
                "sku_id": "CON-SKU-003",
                "image_url": "https://d1234567890.cloudfront.net/products/con-003-primary.jpg",
                "image_type": "primary"
            }
        ]
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["product_group_id", "sku_id", "image_url", "image_type"])
            writer.writeheader()
            writer.writerows(sample_data)
        
        logger.info(f"Sample CSV created: {output_path}")
        return output_path
    
    def close(self):
        """Close database connection"""
        self.db.close()


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Import CloudFront URLs into the image enhancement database'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # CSV import
    csv_parser = subparsers.add_parser('csv', help='Import from CSV file')
    csv_parser.add_argument('file', help='Path to CSV file')
    csv_parser.add_argument('--url-column', default='image_url', help='Column containing URLs')
    csv_parser.add_argument('--sku-column', default='sku_id', help='Column containing SKU IDs')
    csv_parser.add_argument('--product-group-column', default='product_group_id', help='Column containing product group')
    csv_parser.add_argument('--image-type-column', help='Column containing image type')
    
    # JSON import
    json_parser = subparsers.add_parser('json', help='Import from JSON file')
    json_parser.add_argument('file', help='Path to JSON file')
    
    # Generate sample
    sample_parser = subparsers.add_parser('sample', help='Generate sample CSV template')
    sample_parser.add_argument('--output', default='sample_urls.csv', help='Output file path')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    importer = CloudFrontImporter()
    
    try:
        if args.command == 'csv':
            stats = importer.import_from_csv(
                args.file,
                url_column=args.url_column,
                sku_column=args.sku_column,
                product_group_column=args.product_group_column,
                image_type_column=args.image_type_column
            )
        elif args.command == 'json':
            stats = importer.import_from_json(args.file)
        elif args.command == 'sample':
            importer.generate_sample_csv(args.output)
            print(f"Sample CSV created: {args.output}")
            return
        
        print("\n" + "="*50)
        print("IMPORT SUMMARY")
        print("="*50)
        print(f"Total records:  {stats['total']}")
        print(f"Imported:       {stats['imported']}")
        print(f"Skipped (dup):  {stats['skipped']}")
        print(f"Errors:         {stats['errors']}")
        print(f"SKUs created:   {stats['skus_created']}")
        print("="*50)
        
    finally:
        importer.close()


if __name__ == "__main__":
    main()
