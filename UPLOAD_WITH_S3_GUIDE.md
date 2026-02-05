# Upload with S3 & Database Persistence - Complete Guide

## Overview

When you upload an image through the Streamlit dashboard, the following happens:

1. **Original Image** → Uploaded to S3 (`uploads/original/` folder)
2. **Enhanced Image** → Uploaded to S3 (`uploads/enhanced/` folder)  
3. **Database Records Created**:
   - `product_images` table - Main image record with S3 URLs
   - `enhancement_history` table - Audit trail with metadata

## Data Flow Diagram

```
┌─────────────────┐
│ Upload via UI   │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│ Read File (bytes)       │
└────────┬────────────────┘
         │
         ├─► S3 Upload (Original) ──► S3://bucket/uploads/original/
         │                              Returns: s3_url, https_url
         │
         ├─► Assess Quality
         │   - Blur score
         │   - Dimensions
         │
         ├─► Enhance Image
         │   - Apply enhancement algorithm
         │   - Generate enhanced bytes
         │
         ├─► Assess Quality (Enhanced)
         │   - Blur score improvement
         │   - Size reduction %
         │
         ├─► S3 Upload (Enhanced) ──► S3://bucket/uploads/enhanced/
         │                              Returns: s3_url, https_url
         │
         ├─► Create ProductImage Record
         │   ├─ sku_id
         │   ├─ image_url (HTTPS)
         │   ├─ enhanced_image_url (HTTPS)
         │   ├─ original_size_bytes
         │   ├─ enhanced_size_bytes
         │   ├─ Status: COMPLETED
         │   └─ Processing metrics
         │
         ├─► Create EnhancementHistory Record
         │   ├─ product_image_id (foreign key)
         │   ├─ enhancement_sequence (1st, 2nd, etc)
         │   ├─ enhancement_mode (local, gemini, bedrock)
         │   ├─ original_s3_url
         │   ├─ original_https_url
         │   ├─ enhanced_s3_url
         │   ├─ enhanced_https_url
         │   ├─ quality_metadata (JSON)
         │   ├─ size_metadata (JSON)
         │   ├─ processing_time_ms
         │   └─ created_at timestamp
         │
         ▼
    Return Response with:
    - image_id (ProductImage ID)
    - database_id (ProductImage ID)
    - original_url (HTTPS URL)
    - enhanced_url (HTTPS URL)
    - quality improvements
    - processing time
```

## API Endpoint: Upload & Enhance

### Request

**POST** `/api/v1/enhance/upload`

```bash
curl -X POST "http://localhost:8000/api/v1/enhance/upload" \
  -F "file=@product_photo.jpg" \
  -F "mode=AUTO" \
  -F "target_size_kb=500" \
  -F "output_format=JPEG"
```

**Parameters:**
- `file` (required) - Image file to upload and enhance
- `mode` (optional) - Enhancement mode: AUTO, BACKGROUND_REMOVE, LIGHT_CORRECTION, UPSCALE_DENOISE, STANDARDIZE, SHARPEN, DENOISE, UPSCALE, OPTIMIZE, FULL (default: AUTO)
- `target_size_kb` (optional) - Target file size in KB (50-2000)
- `output_format` (optional) - JPEG, PNG, WEBP (default: JPEG)

### Response

```json
{
  "success": true,
  "image_id": "550e8400-e29b-41d4-a716-446655440000",
  "database_id": "550e8400-e29b-41d4-a716-446655440000",
  "original_url": "https://d123456.cloudfront.net/uploads/original/550e8400_photo.jpg",
  "enhanced_url": "https://d123456.cloudfront.net/uploads/enhanced/550e8400_photo.jpg",
  "original_size_kb": 850.5,
  "enhanced_size_kb": 425.3,
  "size_reduction_percent": 50.0,
  "quality_before": 85.5,
  "quality_after": 92.3,
  "processing_time_ms": 3456,
  "enhancement_mode": "AUTO"
}
```

## Database Tables

### product_images Table

Stores the main image record with URLs and metadata.

**Key Columns:**
```sql
id                      -- UUID primary key
sku_id                  -- Unique identifier (upload_UUID)
image_url               -- HTTPS URL to original image
enhanced_image_url      -- HTTPS URL to enhanced image
original_filename       -- Original filename
original_size_bytes     -- Original file size
enhanced_size_bytes     -- Enhanced file size
original_width          -- Original width
original_height         -- Original height
enhanced_width          -- Enhanced width
enhanced_height         -- Enhanced height
original_format         -- Format (JPEG, PNG, etc)
enhanced_format         -- Format of enhanced image
status                  -- COMPLETED, PENDING, FAILED
enhancement_mode        -- LOCAL, GEMINI, BEDROCK, etc
processing_time_ms      -- Time to process
processed_at            -- Timestamp
created_at              -- Created timestamp
updated_at              -- Last updated timestamp
```

**Example Query:**
```sql
SELECT 
  id,
  sku_id,
  image_url,
  enhanced_image_url,
  original_size_bytes,
  enhanced_size_bytes,
  status,
  processed_at
FROM product_images
ORDER BY processed_at DESC
LIMIT 10;
```

### enhancement_history Table

Audit trail of each enhancement attempt with detailed metadata.

**Key Columns:**
```sql
id                          -- UUID primary key
product_image_id            -- Foreign key to product_images
enhancement_sequence        -- 1st, 2nd, 3rd enhancement
enhancement_mode            -- LOCAL, GEMINI, BEDROCK
original_s3_url             -- S3 path (s3://bucket/...)
original_https_url          -- HTTPS/CloudFront URL
enhanced_s3_url             -- S3 path (s3://bucket/...)
enhanced_https_url          -- HTTPS/CloudFront URL
original_size_bytes         -- Original size
enhanced_size_bytes         -- Enhanced size
original_quality_score      -- Quality metric before
enhanced_quality_score      -- Quality metric after
quality_metadata            -- JSON: blur scores, improvements
size_metadata               -- JSON: size reduction %
processing_time_ms          -- Processing duration
processing_status           -- completed, processing, failed
model_version               -- API version used
response_id                 -- External API response ID
created_at                  -- Timestamp
```

**Example Query - Get Enhancement History:**
```sql
SELECT 
  eh.enhancement_sequence,
  eh.enhancement_mode,
  eh.original_https_url,
  eh.enhanced_https_url,
  eh.quality_metadata,
  eh.size_metadata,
  eh.created_at
FROM enhancement_history eh
WHERE eh.product_image_id = 'IMAGE_ID'
ORDER BY eh.enhancement_sequence ASC;
```

## Using in Streamlit Dashboard

### Upload Tab

1. Click **Upload & Enhance** section
2. Select **📤 Upload** tab
3. Check **🤖 Gemini AI Enhancement** (optional)
4. Upload image
5. Watch progress in sidebar

The dashboard shows:
- Original image with quality metrics
- Enhanced image with improvements
- Side-by-side comparison
- Quality metrics (before/after)
- Size reduction percentage
- Download buttons with S3 URLs

### View Uploaded Images

Navigate to **📊 Dashboard** → **Image Gallery** to see all uploaded and enhanced images from the database.

Each image shows:
- Thumbnail
- Upload date/time
- Original filename
- Enhancement mode used
- Quality improvement
- Size reduction
- Direct links to S3 URLs

## Verifying Data Persistence

### 1. Check MySQL Database

```bash
# List all uploaded images
mysql -h localhost -u root -p image_enhancer << 'EOF'
SELECT 
  id,
  sku_id,
  original_filename,
  original_size_bytes,
  enhanced_size_bytes,
  status,
  processed_at
FROM product_images
ORDER BY processed_at DESC
LIMIT 5;
EOF
```

**Output Example:**
```
id                                    | sku_id              | original_filename | original_size_bytes | enhanced_size_bytes | status    | processed_at
--------------------------------------|---------------------|-------------------|--------------------|--------------------|-----------|---------
550e8400-e29b-41d4-a716-446655440000 | upload_550e8400     | photo.jpg         | 850000             | 425000             | COMPLETED | 2026-02-05 15:30:45
```

### 2. Check Enhancement History

```bash
mysql -h localhost -u root -p image_enhancer << 'EOF'
SELECT 
  id,
  product_image_id,
  enhancement_sequence,
  enhancement_mode,
  quality_metadata,
  size_metadata,
  created_at
FROM enhancement_history
ORDER BY created_at DESC
LIMIT 3;
EOF
```

### 3. Check S3 Bucket

```bash
# List uploaded original images
aws s3 ls s3://pixel-lab-s3/uploads/original/

# List enhanced images
aws s3 ls s3://pixel-lab-s3/uploads/enhanced/

# Download specific image
aws s3 cp s3://pixel-lab-s3/uploads/enhanced/IMAGE_ID.jpg ./
```

### 4. Verify HTTPS URLs Work

Open in browser or curl:
```bash
curl -I "https://d123456.cloudfront.net/uploads/original/550e8400_photo.jpg"
curl -I "https://d123456.cloudfront.net/uploads/enhanced/550e8400_photo.jpg"
```

Should return HTTP 200 OK.

## API Endpoints for Uploaded Images

### List All Images

**GET** `/api/v1/images?limit=50&offset=0&status=COMPLETED`

```bash
curl "http://localhost:8000/api/v1/images?status=COMPLETED&limit=10"
```

Response:
```json
{
  "total": 42,
  "limit": 10,
  "offset": 0,
  "images": [
    {
      "id": "550e8400...",
      "sku_id": "upload_550e8400",
      "image_url": "https://...",
      "enhanced_image_url": "https://...",
      "original_size_kb": 850.5,
      "enhanced_size_kb": 425.3,
      "status": "COMPLETED"
    }
  ]
}
```

### Get Enhancement History for Image

**GET** `/api/v1/images/{image_id}/enhancement-history`

```bash
curl "http://localhost:8000/api/v1/images/550e8400-e29b-41d4-a716-446655440000/enhancement-history"
```

Response:
```json
{
  "image_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "photo.jpg",
  "original_https_url": "https://...",
  "enhancements": [
    {
      "id": "abc123",
      "enhancement_sequence": 1,
      "enhancement_mode": "AUTO",
      "quality_metadata": {
        "original_blur": 85.5,
        "enhanced_blur": 92.3,
        "improvement_percent": 7.8
      },
      "size_metadata": {
        "original_size_kb": 850.5,
        "enhanced_size_kb": 425.3,
        "reduction_percent": 50.0
      },
      "enhanced_https_url": "https://..."
    }
  ]
}
```

## Configuration Requirements

### Environment Variables

```bash
# MySQL Database
export MYSQL_HOST=localhost
export MYSQL_PORT=3306
export MYSQL_DATABASE=image_enhancer
export MYSQL_USER=root
export MYSQL_PASSWORD=your_password

# AWS S3
export S3_BUCKET=pixel-lab-s3
export AWS_REGION=ap-south-1
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret

# Optional: CloudFront CDN
export CLOUDFRONT_DOMAIN=https://d123456.cloudfront.net

# Optional: Gemini (for Gemini enhancement)
export GEMINI_API_KEY=your_key
```

## S3 Bucket Structure

After uploads, your S3 bucket will look like:

```
pixel-lab-s3/
├── uploads/
│   ├── original/
│   │   ├── 550e8400_photo.jpg
│   │   ├── 660f9511_product.png
│   │   └── ...
│   ├── enhanced/
│   │   ├── 550e8400_photo.jpg
│   │   ├── 660f9511_product.png
│   │   └── ...
├── originals/  (Gemini uploads)
│   └── ...
├── enhanced/   (Gemini uploads)
│   └── ...
```

## File Size Limits

- Max upload size: 50 MB (configurable)
- Target file size: 50 KB - 2 MB
- Recommended: 500 KB

## Troubleshooting

### Images Not Appearing in Database

1. Check MySQL is running:
   ```bash
   ps aux | grep mysqld
   ```

2. Verify S3_BUCKET is set:
   ```bash
   echo $S3_BUCKET
   ```

3. Check API logs for [UPLOAD] messages:
   ```
   [UPLOAD] File received: photo.jpg, size: 850000 bytes
   [UPLOAD] Original uploaded to S3: uploads/original/...
   [UPLOAD] Enhanced uploaded to S3: uploads/enhanced/...
   [UPLOAD] Database record created: 550e8400...
   [UPLOAD] Enhancement history created: abc123...
   ```

### S3 Upload Failing

- Verify AWS credentials are correct
- Check S3 bucket exists and is accessible
- Ensure bucket name is correct (case-sensitive)
- Check AWS IAM permissions for s3:PutObject

### HTTPS URLs Not Working

- Verify CloudFront is configured (if using CDN)
- Check CloudFront domain is correct
- Verify CloudFront distribution includes S3 bucket as origin

## Performance Notes

- Average upload/enhance/persist time: 2-5 seconds per image
- Database queries are indexed for fast retrieval
- S3 uploads use server-side encryption (AES256)
- HTTPS URLs are cached via CloudFront CDN

## Next Steps

1. ✅ Upload test image via dashboard
2. ✅ Check `/api/v1/images` endpoint for your upload
3. ✅ Verify S3 bucket contains both original and enhanced
4. ✅ View enhancement history via `/api/v1/images/{id}/enhancement-history`
5. ✅ Monitor MySQL for growing records
