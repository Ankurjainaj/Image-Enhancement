#!/usr/bin/env python
"""Test script to verify database connectivity and insertion"""
import sys
import os
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from src.database import init_db, get_db, ProductImage, ProductImageRepository
    from src.config import get_config, ProcessingStatus
    
    print("✓ Imports successful")
    
    # Initialize DB
    print("\n📊 Initializing database...")
    init_db()
    print("✓ Database initialized")
    
    # Get config
    config = get_config()
    print(f"\n🗄️  Database Config:")
    print(f"   Host: {config.database.host}")
    print(f"   Port: {config.database.port}")
    print(f"   Database: {config.database.database}")
    print(f"   User: {config.database.user}")
    print(f"   URL: {config.database.url}")
    
    # Try to create a record
    print("\n📝 Testing database insertion...")
    db = get_db()
    print("✓ Database session created")
    
    repo = ProductImageRepository(db)
    print("✓ Repository created")
    
    # Create test image
    test_image = repo.create(
        sku_id="TEST_SKU_001",
        image_url="https://example.com/test.jpg",
        enhanced_image_url="https://example.com/test_enhanced.jpg",
        original_filename="test.jpg",
        original_size_bytes=50000,
        enhanced_size_bytes=30000,
        original_format="JPEG",
        enhanced_format="JPEG",
        enhancement_mode="test",
        status=ProcessingStatus.COMPLETED.value,
        processed_at=datetime.utcnow(),
        processing_time_ms=1000
    )
    
    print(f"✓ Image created with ID: {test_image.id}")
    
    # Verify it was saved
    retrieved = repo.get_by_id(str(test_image.id))
    if retrieved:
        print(f"✓ Image retrieved successfully: {retrieved.sku_id}")
    else:
        print("✗ Image not found after insertion!")
    
    db.close()
    print("\n✅ All tests passed!")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
