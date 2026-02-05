# Quick Start - Image Enhancement with S3 & Audit Trail

## One-Time Setup (First Time Only)

### 1. Set Environment Variables

Create a `.env` file in project root:

```bash
# MySQL Database
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=image_enhancer
MYSQL_USER=root
MYSQL_PASSWORD=root

# AWS S3
S3_BUCKET=pixel-lab-s3
AWS_REGION=ap-south-1
AWS_ACCESS_KEY_ID=YOUR_ACCESS_KEY
AWS_SECRET_ACCESS_KEY=YOUR_SECRET_KEY

# Google Gemini
GEMINI_API_KEY=YOUR_GEMINI_KEY

# Optional
CLOUDFRONT_DOMAIN=https://d123456.cloudfront.net
LOG_LEVEL=INFO
```

Then load it:
```bash
source .env
```

### 2. Start MySQL

```bash
# macOS
brew services start mysql
# or 
/usr/local/mysql/support-files/mysql.server start
```

Verify it's running:
```bash
mysql -h localhost -u root -p -e "SELECT 1;"
```

### 3. Initialize Database

```bash
python3 -c "from src.database import init_db; init_db()"
```

Or use the script:
```bash
bash init_database.sh
```

## Running the Application

### Terminal 1: Start API Server

```bash
uvicorn api.main:app --reload --port 8000
```

Watch for logs with `[GEMINI]` prefix - these show data persistence progress.

### Terminal 2: Start Dashboard

```bash
streamlit run dashboard/app.py
```

Opens at `http://localhost:8501`

## Using the Application

### Upload and Enhance Image

1. **Dashboard UI (Streamlit)**
   - Open `http://localhost:8501`
   - Go to "Upload & Enhance" tab
   - Check "🤖 Gemini AI Enhancement" checkbox
   - Upload image
   - Watch for enhanced result

2. **Monitor Data Storage**
   - API console will show `[GEMINI]` logs
   - S3 console will show uploaded images
   - Database will store records

### View Enhancement History

Retrieve all enhancements for an image:

```bash
curl http://localhost:8000/api/v1/images/IMAGE_ID/enhancement-history
```

Returns:
```json
{
  "image_id": 123,
  "filename": "product.jpg",
  "original_https_url": "https://...",
  "enhancements": [
    {
      "id": "abc123",
      "enhancement_sequence": 1,
      "enhancement_mode": "gemini",
      "quality_metadata": {
        "original_blur": 50,
        "enhanced_blur": 85,
        "improvement_percent": 70
      },
      "size_metadata": {
        "original_size_kb": 200,
        "enhanced_size_kb": 150,
        "reduction_percent": 25
      },
      "enhanced_https_url": "https://..."
    }
  ],
  "total_enhancements": 1
}
```

## Verify Data Persistence

### Check MySQL

```bash
# Connect to database
mysql -h localhost -u root -p image_enhancer

# View images
SELECT COUNT(*) as total_images FROM product_images;
SELECT * FROM product_images LIMIT 1\G

# View enhancement history
SELECT COUNT(*) as total_enhancements FROM enhancement_history;
SELECT * FROM enhancement_history LIMIT 1\G
```

### Check S3

```bash
# AWS CLI
aws s3 ls s3://my-image-bucket/originals/
aws s3 ls s3://my-image-bucket/enhanced/

# Or use AWS Console
# https://s3.console.aws.amazon.com/s3/buckets/
```

## Data Flow Diagram

```
User Upload Image
        ↓
    Streamlit UI
        ↓
API /api/v1/enhance/gemini
        ↓
    ┌───────────┬──────────┬────────────┐
    ↓           ↓          ↓            ↓
  Upload      Gemini    Assess    Upload
  Original   Enhance    Quality   Enhanced
    ↓           ↓          ↓            ↓
    └───────────┴──────────┴────────────┘
                 ↓
        Create ProductImage Record
                 ↓
        Create EnhancementHistory Record
        (with URLs + metadata)
                 ↓
        ┌─────────┴──────────┐
        ↓                    ↓
     MySQL              S3 Bucket
     (Metadata)        (Image Files)
```

## Troubleshooting

### "S3 storage not configured"
```bash
# Make sure S3_BUCKET is set
echo $S3_BUCKET

# If empty, set it
export S3_BUCKET=your-bucket-name
```

### "Can't connect to MySQL"
```bash
# Check MySQL is running
brew services list | grep mysql

# Start it
brew services start mysql

# Verify connection
mysql -h localhost -u root -p -e "SELECT 1;"
```

### "No tables in database"
```bash
# Initialize database
python3 -c "from src.database import init_db; init_db()"

# Verify tables exist
mysql -h localhost -u root -p image_enhancer -e "SHOW TABLES;"
```

### "No data being inserted"
1. Check API console for `[GEMINI]` logs
2. Check all environment variables: `env | grep -E "MYSQL|S3|GEMINI"`
3. Check MySQL error log: `/usr/local/mysql/data/mysqld.local.err`
4. See `DATABASE_TROUBLESHOOTING.md` for detailed debugging

## API Endpoints

### Enhance with Gemini
```
POST /api/v1/enhance/gemini
Content-Type: multipart/form-data

file: <image file>
enhancement_prompt: <optional custom prompt>
```

### Get Enhancement History
```
GET /api/v1/images/{image_id}/enhancement-history
```

Returns all enhancements for an image with metadata.

### Assess Quality
```
POST /api/v1/assess
Content-Type: application/json

{
  "url": "https://example.com/image.jpg",
  "include_brisque": false
}
```

## Files Modified

- `src/database.py` - Added EnhancementHistory fields and repository
- `src/gemini_service.py` - Added get_image_bytes() method
- `api/main.py` - Updated Gemini endpoint with S3 integration
- `src/s3_service.py` - S3 service for image uploads (already created)
- `src/config.py` - S3 configuration (already updated)

## Next Steps

1. ✅ Upload test image through dashboard
2. ✅ Verify `[GEMINI]` logs in API console
3. ✅ Check MySQL for ProductImage and EnhancementHistory records
4. ✅ Check S3 bucket for uploaded images
5. ✅ Call `/api/v1/images/{id}/enhancement-history` to view metadata

## Support

For issues:
1. Check `DATABASE_TROUBLESHOOTING.md`
2. Check `CHANGES_SUMMARY.md` for what was fixed
3. Review `ENV_SETUP.md` for configuration details
