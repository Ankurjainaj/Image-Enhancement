#!/usr/bin/env python3
"""
Diagnostic script to identify why S3 uploads and database records aren't working
"""
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Setup path
sys.path.insert(0, str(Path(__file__).parent))

load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

print("=" * 80)
print("IMAGE ENHANCEMENT DIAGNOSTIC")
print("=" * 80)

# 1. Check environment variables
print("\n[1] CHECKING ENVIRONMENT VARIABLES")
print("-" * 80)

env_vars = {
    'MySQL': ['MYSQL_HOST', 'MYSQL_PORT', 'MYSQL_DATABASE', 'MYSQL_USER', 'MYSQL_PASSWORD'],
    'S3': ['S3_BUCKET', 'AWS_REGION', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY'],
}

for section, vars_list in env_vars.items():
    print(f"\n{section}:")
    for var in vars_list:
        value = os.getenv(var)
        if var in ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'MYSQL_PASSWORD']:
            display = '***' if value else 'NOT SET'
        else:
            display = value or 'NOT SET'
        status = "✓" if value else "✗"
        print(f"  {status} {var}: {display}")

# 2. Check MySQL connection
print("\n\n[2] CHECKING MYSQL CONNECTION")
print("-" * 80)

try:
    from src.database import get_db, init_db
    print("✓ Database module imported successfully")
    
    # Try to connect
    db = get_db()
    if db:
        print("✓ Database connection successful")
        db.close()
    else:
        print("✗ Database connection failed - returned None")
except Exception as e:
    print(f"✗ Database connection failed: {e}")
    import traceback
    traceback.print_exc()

# 3. Check S3 connection
print("\n\n[3] CHECKING S3 CONNECTION")
print("-" * 80)

try:
    from src.config import get_config
    from src.s3_service import S3Service
    
    config = get_config()
    print(f"✓ Config loaded")
    print(f"  - S3 Bucket: {config.storage.s3_bucket}")
    print(f"  - S3 Region: {config.storage.s3_region}")
    print(f"  - CloudFront: {config.storage.cloudfront_domain or 'Not configured'}")
    
    # Try to initialize S3 service
    try:
        s3_service = S3Service(
            bucket=config.storage.s3_bucket,
            region=config.storage.s3_region,
            endpoint_url=config.storage.s3_endpoint if config.storage.s3_endpoint else None,
            access_key=config.storage.s3_access_key,
            secret_key=config.storage.s3_secret_key
        )
        print("✓ S3 connection successful")
    except Exception as e:
        print(f"✗ S3 connection failed: {e}")
        import traceback
        traceback.print_exc()

except Exception as e:
    print(f"✗ S3 setup failed: {e}")
    import traceback
    traceback.print_exc()

# 4. Check repositories
print("\n\n[4] CHECKING DATABASE REPOSITORIES")
print("-" * 80)

try:
    from src.database import ImageRepository, EnhancementHistoryRepository, get_db
    
    db = get_db()
    if db:
        try:
            img_repo = ImageRepository(db)
            print("✓ ImageRepository instantiated")
            
            hist_repo = EnhancementHistoryRepository(db)
            print("✓ EnhancementHistoryRepository instantiated")
            
            db.close()
        except Exception as e:
            print(f"✗ Repository instantiation failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("✗ Cannot create repositories - database connection failed")
        
except Exception as e:
    print(f"✗ Repository setup failed: {e}")
    import traceback
    traceback.print_exc()

# 5. Check image enhancer
print("\n\n[5] CHECKING IMAGE ENHANCER")
print("-" * 80)

try:
    from src.enhancer import ImageEnhancer
    
    enhancer = ImageEnhancer()
    print("✓ ImageEnhancer initialized")
except Exception as e:
    print(f"✗ ImageEnhancer initialization failed: {e}")
    import traceback
    traceback.print_exc()

# 6. Create a test image and try upload flow
print("\n\n[6] TESTING COMPLETE UPLOAD FLOW")
print("-" * 80)

try:
    from PIL import Image
    import io
    from src.config import EnhancementMode
    
    # Create a simple test image
    img = Image.new('RGB', (100, 100), color='red')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes = img_bytes.getvalue()
    print(f"✓ Created test image: {len(img_bytes)} bytes")
    
    # Try S3 upload
    try:
        config = get_config()
        s3_service = S3Service(
            bucket=config.storage.s3_bucket,
            region=config.storage.s3_region,
            endpoint_url=config.storage.s3_endpoint if config.storage.s3_endpoint else None,
            access_key=config.storage.s3_access_key,
            secret_key=config.storage.s3_secret_key
        )
        
        test_key = "test_uploads/diagnostic_test.jpg"
        s3_url = s3_service.upload_image(img_bytes, test_key, "image/jpeg")
        print(f"✓ S3 upload successful: {s3_url}")
        
        # Try database insert
        db = get_db()
        if db:
            img_repo = ImageRepository(db)
            product_image = img_repo.create(
                sku_id="test_sku_diagnostic",
                image_url="https://example.com/test.jpg",
                enhanced_image_url="https://example.com/test_enhanced.jpg",
                original_filename="test.jpg",
                original_width=100,
                original_height=100,
                original_size_bytes=len(img_bytes),
                enhanced_width=100,
                enhanced_height=100,
                enhanced_size_bytes=len(img_bytes),
                original_format="JPEG",
                enhanced_format="JPEG",
                status="completed"
            )
            print(f"✓ Database insert successful: ID = {product_image.id}")
            db.close()
        else:
            print("✗ Database connection failed for insert test")
            
    except Exception as e:
        print(f"✗ Upload flow test failed: {e}")
        import traceback
        traceback.print_exc()
        
except Exception as e:
    print(f"✗ Test setup failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("DIAGNOSTIC COMPLETE")
print("=" * 80)
