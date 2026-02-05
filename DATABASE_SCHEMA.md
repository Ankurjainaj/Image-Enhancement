# Database Tables - Quick Reference

## product_images Table

Stores the main product image record with URLs and metadata.

### Table Structure

```sql
CREATE TABLE product_images (
  id VARCHAR(36) PRIMARY KEY,
  sku_ref VARCHAR(36),
  product_group_id VARCHAR(100),
  sku_id VARCHAR(100) NOT NULL UNIQUE,
  
  -- Original Image URLs
  image_url VARCHAR(2048) NOT NULL,           -- HTTPS URL
  original_local_path VARCHAR(512),
  
  -- Enhanced Image URLs
  enhanced_image_url VARCHAR(2048),           -- HTTPS URL
  enhanced_local_path VARCHAR(512),
  
  -- Original Image Metadata
  original_filename VARCHAR(255),
  original_width INT,
  original_height INT,
  original_size_bytes BIGINT,
  original_format VARCHAR(20),
  original_dpi INT,
  
  -- Enhanced Image Metadata
  enhanced_width INT,
  enhanced_height INT,
  enhanced_size_bytes BIGINT,
  enhanced_format VARCHAR(20),
  enhanced_dpi INT,
  
  -- Image Properties
  image_type VARCHAR(50),
  image_sequence SMALLINT,
  
  -- Processing
  status VARCHAR(20),
  enhancement_mode VARCHAR(50),
  enhancements_applied JSON,
  processing_time_ms INT,
  processed_at DATETIME,
  error_message TEXT,
  
  -- Timestamps
  created_at DATETIME,
  updated_at DATETIME,
  
  -- Indexes
  INDEX ix_sku_id (sku_id),
  INDEX ix_status (status),
  INDEX ix_created_at (created_at)
);
```

### Key Fields Explained

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Unique identifier (auto-generated) |
| `sku_id` | string | Unique product identifier (e.g., "upload_550e8400") |
| `image_url` | string | HTTPS URL to original image (from CloudFront or S3) |
| `enhanced_image_url` | string | HTTPS URL to enhanced image |
| `original_filename` | string | Original uploaded filename |
| `original_size_bytes` | bigint | Size of original image in bytes |
| `enhanced_size_bytes` | bigint | Size of enhanced image in bytes |
| `status` | string | PENDING, PROCESSING, COMPLETED, FAILED |
| `enhancement_mode` | string | AUTO, GEMINI, LOCAL, BEDROCK, etc |
| `processing_time_ms` | int | Time to process in milliseconds |
| `enhancements_applied` | JSON | List of enhancements applied |

### Example Data

```sql
INSERT INTO product_images VALUES (
  '550e8400-e29b-41d4-a716-446655440000',  -- id
  NULL,                                     -- sku_ref
  NULL,                                     -- product_group_id
  'upload_550e8400',                        -- sku_id
  'https://d123456.cloudfront.net/uploads/original/550e8400_photo.jpg',  -- image_url
  NULL,                                     -- original_local_path
  'https://d123456.cloudfront.net/uploads/enhanced/550e8400_photo.jpg',  -- enhanced_image_url
  NULL,                                     -- enhanced_local_path
  'photo.jpg',                              -- original_filename
  1200,                                     -- original_width
  900,                                      -- original_height
  850000,                                   -- original_size_bytes
  'JPEG',                                   -- original_format
  300,                                      -- original_dpi
  1200,                                     -- enhanced_width
  900,                                      -- enhanced_height
  425000,                                   -- enhanced_size_bytes
  'JPEG',                                   -- enhanced_format
  300,                                      -- enhanced_dpi
  'primary',                                -- image_type
  1,                                        -- image_sequence
  'COMPLETED',                              -- status
  'AUTO',                                   -- enhancement_mode
  '["brightness_correction", "upscale"]',   -- enhancements_applied
  3456,                                     -- processing_time_ms
  '2026-02-05 15:30:45',                    -- processed_at
  NULL,                                     -- error_message
  '2026-02-05 15:30:12',                    -- created_at
  '2026-02-05 15:30:45'                     -- updated_at
);
```

---

## enhancement_history Table

Audit trail of each enhancement attempt with complete metadata.

### Table Structure

```sql
CREATE TABLE enhancement_history (
  id VARCHAR(36) PRIMARY KEY,
  product_image_id VARCHAR(36) NOT NULL,
  
  -- Enhancement Tracking
  enhancement_sequence INT NOT NULL,
  enhancement_mode VARCHAR(50) NOT NULL,
  enhancement_prompt TEXT,
  
  -- Original Image URLs & Metadata
  original_s3_url VARCHAR(2048),            -- s3://bucket/path
  original_https_url VARCHAR(2048),         -- HTTPS URL
  original_size_bytes BIGINT,
  original_quality_score FLOAT,
  original_blur_score FLOAT,
  original_width INT,
  original_height INT,
  original_format VARCHAR(20),
  
  -- Enhanced Image URLs & Metadata
  enhanced_s3_url VARCHAR(2048),            -- s3://bucket/path
  enhanced_https_url VARCHAR(2048),         -- HTTPS URL
  enhanced_size_bytes BIGINT,
  enhanced_quality_score FLOAT,
  enhanced_blur_score FLOAT,
  enhanced_width INT,
  enhanced_height INT,
  enhanced_format VARCHAR(20),
  
  -- Metadata
  enhancements_applied JSON,
  quality_metadata JSON,                    -- {original_blur, enhanced_blur, improvement_percent}
  size_metadata JSON,                       -- {original_size_kb, enhanced_size_kb, reduction_percent}
  
  -- Processing Details
  processing_time_ms INT,
  processing_status VARCHAR(20),
  error_message TEXT,
  
  -- API/Service Info
  api_endpoint VARCHAR(255),
  model_version VARCHAR(100),
  response_id VARCHAR(100),
  
  -- User Info
  user_id VARCHAR(100),
  request_ip VARCHAR(45),
  user_agent VARCHAR(500),
  
  -- Timestamps
  created_at DATETIME,
  
  -- Indexes
  INDEX ix_product_image_id (product_image_id),
  INDEX ix_created_at (created_at),
  INDEX ix_status (processing_status),
  INDEX ix_mode (enhancement_mode),
  FOREIGN KEY (product_image_id) REFERENCES product_images(id)
);
```

### Key Fields Explained

| Field | Type | Description |
|-------|------|-------------|
| `product_image_id` | UUID | Foreign key linking to product_images |
| `enhancement_sequence` | int | 1 = 1st enhancement, 2 = 2nd, etc |
| `enhancement_mode` | string | LOCAL, GEMINI, BEDROCK |
| `original_s3_url` | string | S3 path (s3://bucket/key) |
| `original_https_url` | string | HTTPS URL for download |
| `enhanced_s3_url` | string | S3 path of enhanced (s3://bucket/key) |
| `enhanced_https_url` | string | HTTPS URL for download |
| `quality_metadata` | JSON | Quality scores and improvement % |
| `size_metadata` | JSON | Size reduction metrics |
| `model_version` | string | API version (e.g., gemini-pro-vision) |
| `processing_status` | string | completed, processing, failed |

### Example Data

```sql
INSERT INTO enhancement_history VALUES (
  'abc123-def456-ghi789',                   -- id
  '550e8400-e29b-41d4-a716-446655440000',   -- product_image_id
  1,                                        -- enhancement_sequence
  'LOCAL',                                  -- enhancement_mode
  NULL,                                     -- enhancement_prompt
  's3://pixel-lab-s3/uploads/original/550e8400_photo.jpg',  -- original_s3_url
  'https://d123456.cloudfront.net/uploads/original/550e8400_photo.jpg',  -- original_https_url
  850000,                                   -- original_size_bytes
  85.5,                                     -- original_quality_score
  85.5,                                     -- original_blur_score
  1200,                                     -- original_width
  900,                                      -- original_height
  'JPEG',                                   -- original_format
  's3://pixel-lab-s3/uploads/enhanced/550e8400_photo.jpg',  -- enhanced_s3_url
  'https://d123456.cloudfront.net/uploads/enhanced/550e8400_photo.jpg',  -- enhanced_https_url
  425000,                                   -- enhanced_size_bytes
  92.3,                                     -- enhanced_quality_score
  92.3,                                     -- enhanced_blur_score
  1200,                                     -- enhanced_width
  900,                                      -- enhanced_height
  'JPEG',                                   -- enhanced_format
  '["brightness_correction", "upscale"]',   -- enhancements_applied
  '{"original_blur": 85.5, "enhanced_blur": 92.3, "improvement_percent": 7.8}',  -- quality_metadata
  '{"original_size_kb": 850.0, "enhanced_size_kb": 425.0, "reduction_percent": 50.0}',  -- size_metadata
  3456,                                     -- processing_time_ms
  'completed',                              -- processing_status
  NULL,                                     -- error_message
  'http://localhost:8000/api/v1/enhance/upload',  -- api_endpoint
  'enhanced-v1.0',                          -- model_version
  'resp_xyz789',                            -- response_id
  NULL,                                     -- user_id
  '192.168.1.100',                          -- request_ip
  'Mozilla/5.0...',                         -- user_agent
  '2026-02-05 15:30:45'                     -- created_at
);
```

---

## Useful Queries

### Get All Uploaded Images

```sql
SELECT 
  id,
  sku_id,
  original_filename,
  ROUND(original_size_bytes / 1024, 2) as original_size_kb,
  ROUND(enhanced_size_bytes / 1024, 2) as enhanced_size_kb,
  ROUND((1 - enhanced_size_bytes / original_size_bytes) * 100, 1) as reduction_percent,
  enhancement_mode,
  status,
  processed_at
FROM product_images
ORDER BY processed_at DESC
LIMIT 20;
```

### Get Enhancement History for One Image

```sql
SELECT 
  eh.enhancement_sequence,
  eh.enhancement_mode,
  JSON_EXTRACT(eh.quality_metadata, '$.improvement_percent') as blur_improvement,
  JSON_EXTRACT(eh.size_metadata, '$.reduction_percent') as size_reduction,
  eh.processing_time_ms,
  eh.created_at
FROM enhancement_history eh
WHERE eh.product_image_id = '550e8400-e29b-41d4-a716-446655440000'
ORDER BY eh.enhancement_sequence ASC;
```

### Get Statistics

```sql
SELECT 
  enhancement_mode,
  COUNT(*) as total_images,
  AVG(processing_time_ms) as avg_processing_ms,
  AVG((1 - enhanced_size_bytes / original_size_bytes) * 100) as avg_size_reduction,
  DATE(processed_at) as date
FROM product_images
WHERE status = 'COMPLETED'
GROUP BY enhancement_mode, DATE(processed_at)
ORDER BY date DESC;
```

### Find Large Files

```sql
SELECT 
  sku_id,
  original_filename,
  ROUND(original_size_bytes / (1024 * 1024), 2) as size_mb,
  enhancement_mode,
  created_at
FROM product_images
WHERE original_size_bytes > 10485760  -- > 10 MB
ORDER BY original_size_bytes DESC;
```

### Recent Uploads (Last 24 Hours)

```sql
SELECT 
  sku_id,
  original_filename,
  enhancement_mode,
  processing_time_ms,
  created_at
FROM product_images
WHERE created_at > DATE_SUB(NOW(), INTERVAL 24 HOUR)
ORDER BY created_at DESC;
```

---

## Import/Export

### Backup Tables

```bash
# Backup product_images
mysqldump -h localhost -u root -p image_enhancer product_images > product_images_backup.sql

# Backup enhancement_history
mysqldump -h localhost -u root -p image_enhancer enhancement_history > enhancement_history_backup.sql
```

### Export as CSV

```bash
mysql -h localhost -u root -p image_enhancer -e \
  "SELECT * FROM product_images" \
  --output-format=CSV > images_export.csv

mysql -h localhost -u root -p image_enhancer -e \
  "SELECT * FROM enhancement_history" \
  --output-format=CSV > history_export.csv
```

---

## Relationship Diagram

```
product_images (1) ───── (N) enhancement_history
         │                        │
         ├─ id (PK)              ├─ product_image_id (FK)
         ├─ sku_id               ├─ enhancement_sequence
         ├─ image_url            ├─ original_s3_url
         ├─ enhanced_image_url   ├─ enhanced_s3_url
         ├─ status               ├─ quality_metadata
         └─ created_at           ├─ size_metadata
                                 └─ created_at
```

One ProductImage can have multiple EnhancementHistory records (for multiple enhancements).
