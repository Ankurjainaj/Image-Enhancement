#!/usr/bin/env python3
"""
Diagnostic script to test S3 connection
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Setup path
sys.path.insert(0, str(Path(__file__).parent))

load_dotenv()

print("="*80)
print("S3 CONNECTION DIAGNOSTIC")
print("="*80)

# 1. Check environment variables
print("\n[1] CHECKING ENVIRONMENT VARIABLES")
print("-"*80)

s3_config = {
    'S3_BUCKET': os.getenv('S3_BUCKET'),
    'AWS_REGION': os.getenv('AWS_REGION'),
    'AWS_ACCESS_KEY_ID': os.getenv('AWS_ACCESS_KEY_ID'),
    'AWS_SECRET_ACCESS_KEY': os.getenv('AWS_SECRET_ACCESS_KEY'),
}

for key, value in s3_config.items():
    if key in ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY']:
        display = f"{'SET' if value else 'NOT SET'} ({len(value) if value else 0} chars)"
    else:
        display = value or "NOT SET"
    status = "✓" if value else "✗"
    print(f"{status} {key}: {display}")

# Check if all required vars are set
missing = [k for k, v in s3_config.items() if not v]
if missing:
    print(f"\n✗ Missing environment variables: {', '.join(missing)}")
    sys.exit(1)

# 2. Test boto3 installation
print("\n[2] CHECKING BOTO3 INSTALLATION")
print("-"*80)

try:
    import boto3
    print(f"✓ boto3 installed: v{boto3.__version__}")
except ImportError:
    print("✗ boto3 not installed")
    sys.exit(1)

# 3. Test S3 connection
print("\n[3] TESTING S3 CONNECTION")
print("-"*80)

try:
    s3_client = boto3.client(
        's3',
        region_name=s3_config['AWS_REGION'],
        aws_access_key_id=s3_config['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=s3_config['AWS_SECRET_ACCESS_KEY']
    )
    print("✓ boto3 client created successfully")
except Exception as e:
    print(f"✗ Failed to create boto3 client: {e}")
    sys.exit(1)

# 4. Test bucket access
print("\n[4] TESTING BUCKET ACCESS")
print("-"*80)

try:
    response = s3_client.head_bucket(Bucket=s3_config['S3_BUCKET'])
    print(f"✓ Bucket '{s3_config['S3_BUCKET']}' is accessible")
    print(f"  Response Code: {response['ResponseMetadata']['HTTPStatusCode']}")
except Exception as e:
    error_code = str(e).split(':')[0] if ':' in str(e) else str(e)
    print(f"✗ Cannot access bucket: {e}")
    if '404' in str(e):
        print("  → Bucket does not exist")
    elif '403' in str(e):
        print("  → Access denied - check AWS credentials and permissions")
    sys.exit(1)

# 5. List objects in bucket
print("\n[5] LISTING BUCKET CONTENTS")
print("-"*80)

try:
    response = s3_client.list_objects_v2(
        Bucket=s3_config['S3_BUCKET'],
        MaxKeys=10
    )
    
    if 'Contents' in response:
        print(f"✓ Found {len(response['Contents'])} objects (showing first 10):")
        for obj in response['Contents']:
            size_kb = obj['Size'] / 1024
            print(f"  - {obj['Key']} ({size_kb:.2f} KB)")
    else:
        print("✓ Bucket is empty")
    
    print(f"\nTotal objects in bucket: {response.get('KeyCount', 0)}")
except Exception as e:
    print(f"✗ Failed to list objects: {e}")
    sys.exit(1)

# 6. Test upload capability
print("\n[6] TESTING UPLOAD CAPABILITY")
print("-"*80)

try:
    import io
    from PIL import Image
    
    # Create a test image
    img = Image.new('RGB', (10, 10), color='red')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)
    
    test_key = "diagnostic_test/s3_connection_test.jpg"
    
    s3_client.put_object(
        Bucket=s3_config['S3_BUCKET'],
        Key=test_key,
        Body=img_bytes.getvalue(),
        ContentType='image/jpeg'
    )
    print(f"✓ Successfully uploaded test file to: s3://{s3_config['S3_BUCKET']}/{test_key}")
    
    # Try to retrieve it
    response = s3_client.get_object(Bucket=s3_config['S3_BUCKET'], Key=test_key)
    print(f"✓ Successfully retrieved test file ({response['ContentLength']} bytes)")
    
    # Test HTTPS URL
    https_url = f"https://{s3_config['S3_BUCKET']}.s3.{s3_config['AWS_REGION']}.amazonaws.com/{test_key}"
    print(f"✓ HTTPS URL: {https_url}")
    
    # Clean up
    s3_client.delete_object(Bucket=s3_config['S3_BUCKET'], Key=test_key)
    print(f"✓ Cleaned up test file")
    
except Exception as e:
    print(f"✗ Upload test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 7. Test with S3Service class
print("\n[7] TESTING WITH S3SERVICE CLASS")
print("-"*80)

try:
    from src.config import get_config
    from src.s3_service import S3Service
    
    config = get_config()
    print(f"✓ Config loaded")
    print(f"  - Bucket: {config.storage.s3_bucket}")
    print(f"  - Region: {config.storage.s3_region}")
    print(f"  - CloudFront: {config.storage.cloudfront_domain or 'Not configured'}")
    
    s3_service = S3Service(
        bucket=config.storage.s3_bucket,
        region=config.storage.s3_region,
        endpoint_url=config.storage.s3_endpoint if config.storage.s3_endpoint else None,
        access_key=config.storage.s3_access_key,
        secret_key=config.storage.s3_secret_key
    )
    print(f"✓ S3Service initialized successfully")
    
    # Test upload with S3Service
    import io
    from PIL import Image
    
    img = Image.new('RGB', (20, 20), color='blue')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)
    
    test_key = "diagnostic_test/s3service_test.jpg"
    s3_url = s3_service.upload_image(img_bytes.getvalue(), test_key, "image/jpeg")
    print(f"✓ S3Service upload successful: {s3_url}")
    
    https_url = s3_service.get_https_url(test_key)
    print(f"✓ HTTPS URL from S3Service: {https_url}")
    
    # Cleanup
    s3_service.delete_image(test_key)
    print(f"✓ Cleaned up S3Service test file")
    
except Exception as e:
    print(f"✗ S3Service test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*80)
print("✅ ALL S3 CONNECTION TESTS PASSED")
print("="*80)
print("\nS3 is properly configured and accessible. The application can:")
print("  1. Connect to S3 bucket: pixel-lab-s3")
print("  2. Upload files to S3")
print("  3. Retrieve files from S3")
print("  4. Generate HTTPS URLs for CloudFront")
print("\n")
