# Quick Setup - pixel-lab-s3 Configuration

## Your S3 Bucket Details

```
Bucket Name: pixel-lab-s3
Region: ap-south-1
```

## Step-by-Step Setup

### 1. Set Environment Variables

Add these to your `.env` file or export them:

```bash
# MySQL Database
export MYSQL_HOST=localhost
export MYSQL_PORT=3306
export MYSQL_DATABASE=image_enhancer
export MYSQL_USER=root
export MYSQL_PASSWORD=root

# AWS S3 (pixel-lab-s3)
export S3_BUCKET=pixel-lab-s3
export AWS_REGION=ap-south-1
export AWS_ACCESS_KEY_ID=YOUR_ACCESS_KEY
export AWS_SECRET_ACCESS_KEY=YOUR_SECRET_KEY

# Optional: CloudFront CDN
export CLOUDFRONT_DOMAIN=https://d123456.cloudfront.net

# Optional: Gemini API
export GEMINI_API_KEY=YOUR_GEMINI_KEY
```

### 2. Verify Environment

```bash
# Check all variables are set
echo "S3_BUCKET=$S3_BUCKET"
echo "AWS_REGION=$AWS_REGION"
echo "MYSQL_DATABASE=$MYSQL_DATABASE"

# Should output:
# S3_BUCKET=pixel-lab-s3
# AWS_REGION=ap-south-1
# MYSQL_DATABASE=image_enhancer
```

### 3. Initialize Database

```bash
# Create database tables
python3 -c "from src.database import init_db; init_db()"

# Verify tables exist
mysql -h localhost -u root -p image_enhancer << 'EOF'
SHOW TABLES;
EOF
```

### 4. Start Services

```bash
# Terminal 1: Start API
cd /Users/ashish.verma/Downloads/Image-Enhancement
uvicorn api.main:app --reload --port 8000

# Terminal 2: Start Dashboard
cd /Users/ashish.verma/Downloads/Image-Enhancement
streamlit run dashboard/app.py
```

### 5. Upload Test Image

Open http://localhost:8501 and:
1. Go to **Upload & Enhance** tab
2. Upload an image
3. Watch the [UPLOAD] logs in API terminal

## Verify Everything Works

### Check S3 Bucket

```bash
# List uploaded files
aws s3 ls s3://pixel-lab-s3/uploads/original/
aws s3 ls s3://pixel-lab-s3/uploads/enhanced/

# Download an enhanced image
aws s3 cp s3://pixel-lab-s3/uploads/enhanced/550e8400_photo.jpg ./enhanced.jpg
```

### Check MySQL Database

```bash
# View all uploaded images
mysql -h localhost -u root -p image_enhancer << 'EOF'
SELECT sku_id, original_filename, image_url, enhanced_image_url, status 
FROM product_images 
ORDER BY created_at DESC 
LIMIT 5;
EOF

# View enhancement history
mysql -h localhost -u root -p image_enhancer << 'EOF'
SELECT product_image_id, enhancement_sequence, enhancement_mode, quality_metadata 
FROM enhancement_history 
LIMIT 5;
EOF
```

### Test API Endpoints

```bash
# Upload image via API
curl -X POST "http://localhost:8000/api/v1/enhance/upload" \
  -F "file=@test_image.jpg"

# List all images
curl "http://localhost:8000/api/v1/images?limit=10"

# Get enhancement history
curl "http://localhost:8000/api/v1/images/{image_id}/enhancement-history"
```

## Bucket Structure

After uploads, your `pixel-lab-s3` bucket will look like:

```
pixel-lab-s3/
├── uploads/
│   ├── original/
│   │   ├── 550e8400-e29b-41d4_photo.jpg
│   │   ├── 660f9511-a7b2-48c1_product.png
│   │   └── ... more originals
│   └── enhanced/
│       ├── 550e8400-e29b-41d4_photo.jpg
│       ├── 660f9511-a7b2-48c1_product.png
│       └── ... more enhanced
├── originals/  (for Gemini uploads)
│   └── ...
└── enhanced/   (for Gemini uploads)
    └── ...
```

## What Happens on Upload

1. **File Uploaded** → S3: `s3://pixel-lab-s3/uploads/original/{uuid}_{filename}`
2. **File Enhanced** → S3: `s3://pixel-lab-s3/uploads/enhanced/{uuid}_{filename}`
3. **Records Created** → MySQL:
   - `product_images` - Main image record
   - `enhancement_history` - Audit trail with metrics

## Data Flow Diagram

```
User Upload (Streamlit)
         ↓
    API /enhance/upload
         ↓
    ┌────────────────────┐
    │ Upload to S3       │
    │ (pixel-lab-s3)     │
    │ └─ originals/      │
    └────────────────────┘
         ↓
    ┌────────────────────┐
    │ Enhance Image      │
    │ (Quality Metrics)  │
    └────────────────────┘
         ↓
    ┌────────────────────┐
    │ Upload to S3       │
    │ (pixel-lab-s3)     │
    │ └─ enhanced/       │
    └────────────────────┘
         ↓
    ┌────────────────────────────┐
    │ Save to MySQL              │
    │ ├─ product_images          │
    │ └─ enhancement_history     │
    └────────────────────────────┘
         ↓
    Return S3 URLs & Metrics
```

## Troubleshooting

### S3 Upload Fails
```bash
# Verify bucket exists
aws s3 ls s3://pixel-lab-s3/

# Check AWS credentials
aws sts get-caller-identity
```

### Data Not in MySQL
```bash
# Check MySQL connection
mysql -h localhost -u root -p -e "SELECT 1"

# Check S3_BUCKET is set
echo $S3_BUCKET  # Should output: pixel-lab-s3

# Check database tables exist
mysql -h localhost -u root -p image_enhancer -e "SHOW TABLES"
```

### HTTPS URLs Not Working
```bash
# Test S3 URL directly
curl -I "https://d123456.cloudfront.net/uploads/original/550e8400_photo.jpg"

# Should return HTTP 200 OK
```

## Success Indicators

✅ See [UPLOAD] logs in API terminal
✅ Files appear in `s3://pixel-lab-s3/uploads/`
✅ Records in `product_images` table
✅ Records in `enhancement_history` table
✅ Quality metrics in `quality_metadata` JSON
✅ HTTPS URLs return 200 OK

## Key Commands

```bash
# View latest uploads
mysql -h localhost -u root -p image_enhancer \
  -e "SELECT * FROM product_images ORDER BY created_at DESC LIMIT 1\G"

# View enhancement history
mysql -h localhost -u root -p image_enhancer \
  -e "SELECT * FROM enhancement_history ORDER BY created_at DESC LIMIT 1\G"

# List S3 files
aws s3 ls s3://pixel-lab-s3/uploads/ --recursive

# Test API
curl http://localhost:8000/api/v1/images | jq '.total'
```

## Next Steps

1. ✅ Set S3_BUCKET=pixel-lab-s3 in environment
2. ✅ Verify AWS credentials work
3. ✅ Initialize MySQL database
4. ✅ Start API and Dashboard
5. ✅ Upload test image
6. ✅ Verify files in S3
7. ✅ Check MySQL records
8. ✅ Test API endpoints
