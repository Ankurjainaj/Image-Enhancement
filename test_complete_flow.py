#!/usr/bin/env python3
"""
Test the complete upload flow: File Upload → S3 → Database
"""
import io
import sys
import json
import base64
import requests
from pathlib import Path
from PIL import Image

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

def create_test_image(width=200, height=200, color=(255, 100, 100)):
    """Create a simple test image"""
    img = Image.new('RGB', (width, height), color=color)
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)
    return img_bytes.getvalue()

def test_upload_flow():
    """Test complete upload flow"""
    print("\n" + "="*80)
    print("TESTING UPLOAD → S3 → DATABASE FLOW")
    print("="*80)
    
    # Step 1: Create test image
    print("\n[1] Creating test image...")
    test_image = create_test_image()
    print(f"✓ Test image created: {len(test_image)} bytes")
    
    # Step 2: Call API endpoint
    print("\n[2] Calling API endpoint: POST /api/v1/enhance/upload")
    try:
        response = requests.post(
            "http://localhost:8000/api/v1/enhance/upload",
            files={"file": ("test_image.jpg", test_image, "image/jpeg")},
            data={
                "mode": "auto",
                "target_size_kb": "500",
                "output_format": "JPEG"
            },
            timeout=300
        )
        
        print(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ API Response:")
            print(json.dumps(result, indent=2))
            
            # Step 3: Verify S3 URLs
            print("\n[3] Verifying S3 URLs...")
            if result.get('success'):
                original_url = result.get('original_url')
                enhanced_url = result.get('enhanced_url')
                database_id = result.get('database_id')
                
                print(f"✓ Database ID: {database_id}")
                print(f"✓ Original URL: {original_url}")
                print(f"✓ Enhanced URL: {enhanced_url}")
                
                # Try to fetch from URLs
                if original_url:
                    try:
                        orig_resp = requests.head(original_url, timeout=10)
                        print(f"✓ Original URL accessible (HTTP {orig_resp.status_code})")
                    except Exception as e:
                        print(f"✗ Original URL not accessible: {e}")
                
                if enhanced_url:
                    try:
                        enh_resp = requests.head(enhanced_url, timeout=10)
                        print(f"✓ Enhanced URL accessible (HTTP {enh_resp.status_code})")
                    except Exception as e:
                        print(f"✗ Enhanced URL not accessible: {e}")
                
                # Step 4: Verify database record
                print("\n[4] Verifying database record...")
                if database_id:
                    try:
                        from src.database import get_db, ImageRepository
                        db = get_db()
                        repo = ImageRepository(db)
                        record = repo.get_by_id(database_id)
                        db.close()
                        
                        if record:
                            print(f"✓ Database record found:")
                            print(f"  - ID: {record.id}")
                            print(f"  - SKU: {record.sku_id}")
                            print(f"  - Original Size: {record.original_size_bytes} bytes")
                            print(f"  - Enhanced Size: {record.enhanced_size_bytes} bytes")
                            print(f"  - Status: {record.status}")
                            print(f"  - Enhancement Mode: {record.enhancement_mode}")
                            print(f"  - Image URL: {record.image_url}")
                            print(f"  - Enhanced URL: {record.enhanced_image_url}")
                        else:
                            print(f"✗ Database record NOT found: {database_id}")
                    except Exception as e:
                        print(f"✗ Error checking database: {e}")
                        import traceback
                        traceback.print_exc()
            else:
                print(f"✗ API returned success=false: {result.get('error')}")
        else:
            print(f"✗ API Error ({response.status_code}):")
            print(response.text)
            
    except Exception as e:
        print(f"✗ Request failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80 + "\n")

if __name__ == "__main__":
    test_upload_flow()
