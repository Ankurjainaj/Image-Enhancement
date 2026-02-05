# Database Persistence Troubleshooting Guide

## Problem: Data Not Being Inserted to MySQL

### Root Causes and Solutions

#### 1. **S3 Bucket Not Configured** (Most Common)
The Gemini enhancement endpoint requires S3 to be configured to store images.

**Fix:**
```bash
# Set required S3 environment variables
export S3_BUCKET=your-aws-s3-bucket-name
export AWS_REGION=ap-south-1
export AWS_ACCESS_KEY_ID=your_aws_access_key
export AWS_SECRET_ACCESS_KEY=your_aws_secret_key
```

The API will return HTTP 503 if S3 bucket is not configured.

#### 2. **MySQL Not Running**
Check if MySQL service is running:

```bash
# macOS with Homebrew
brew services list | grep mysql

# Or check process
ps aux | grep mysqld
```

**Fix:** Start MySQL
```bash
# macOS
brew services start mysql
# or
/usr/local/mysql/support-files/mysql.server start

# Linux
sudo systemctl start mysql
```

#### 3. **Database Not Initialized**
Tables must be created before data can be inserted.

**Fix:** Initialize database
```bash
python3 -c "from src.database import init_db; init_db()"
```

Or use the initialization script:
```bash
bash init_database.sh
```

#### 4. **Incorrect MySQL Credentials**
Connection string might be using wrong credentials.

**Check and set:**
```bash
export MYSQL_HOST=localhost
export MYSQL_PORT=3306
export MYSQL_DATABASE=image_enhancer
export MYSQL_USER=root
export MYSQL_PASSWORD=your_password
```

Verify connection:
```bash
mysql -h $MYSQL_HOST -u $MYSQL_USER -p$MYSQL_PASSWORD -e "use $MYSQL_DATABASE; SHOW TABLES;"
```

#### 5. **Database Session Not Closing Properly**
If the session doesn't close, uncommitted changes might be lost.

**Status:** ✅ Fixed in latest code - now using try/finally blocks

#### 6. **Missing Table Columns**
The EnhancementHistory table was missing `original_s3_url` and `original_https_url` fields.

**Status:** ✅ Fixed - fields added to EnhancementHistory model

### Step-by-Step Diagnosis

1. **Check if database has tables:**
   ```bash
   mysql -h localhost -u root -p image_enhancer -e "SHOW TABLES;"
   ```
   
   Expected tables:
   - product_images
   - enhancement_history
   - skus
   - product_groups
   - image_metrics

2. **Test manual data insertion:**
   ```python
   from src.database import init_db, get_db, ProductImageRepository
   from src.config import ProcessingStatus
   from datetime import datetime
   
   init_db()  # Create tables if needed
   db = get_db()
   repo = ProductImageRepository(db)
   
   image = repo.create(
       sku_id="TEST_123",
       image_url="https://example.com/test.jpg",
       original_filename="test.jpg",
       original_size_bytes=50000,
       original_format="JPEG",
       status=ProcessingStatus.COMPLETED.value
   )
   
   print(f"Created image: {image.id}")
   db.close()
   ```

3. **Check API logs for errors:**
   When running uvicorn, look for error messages with `[GEMINI]` prefix:
   ```
   [GEMINI] File read: filename, size: X bytes
   [GEMINI] Database session created
   [GEMINI] S3 service initialized
   [GEMINI] Product image created with ID: xyz
   [GEMINI] Enhancement history created with ID: abc
   ```

4. **Test the Gemini enhancement endpoint:**
   
   Using curl:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/enhance/gemini" \
     -F "file=@test_image.jpg"
   ```
   
   Or use the Streamlit dashboard and check for errors.

### Environment Variable Checklist

Before running the application, verify all required variables are set:

```bash
# MySQL - REQUIRED
echo "MYSQL_HOST: $MYSQL_HOST"
echo "MYSQL_USER: $MYSQL_USER"
echo "MYSQL_DATABASE: $MYSQL_DATABASE"

# S3 - REQUIRED for Gemini enhancement
echo "S3_BUCKET: $S3_BUCKET"
echo "AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID:0:10}..." 
echo "AWS_SECRET_ACCESS_KEY: (set: $([[ -z \"$AWS_SECRET_ACCESS_KEY\" ]] && echo 'NO' || echo 'YES'))"

# Gemini - REQUIRED for Gemini enhancement
echo "GEMINI_API_KEY: ${GEMINI_API_KEY:0:10}..."
```

### Quick Start - Complete Setup

```bash
# 1. Set MySQL credentials
export MYSQL_HOST=localhost
export MYSQL_PORT=3306
export MYSQL_DATABASE=image_enhancer
export MYSQL_USER=root
export MYSQL_PASSWORD=root

# 2. Set S3 credentials  
export S3_BUCKET=my-bucket
export AWS_REGION=us-east-1
export AWS_ACCESS_KEY_ID=AKIA...
export AWS_SECRET_ACCESS_KEY=...

# 3. Set Gemini API key
export GEMINI_API_KEY=...

# 4. Initialize database
python3 -c "from src.database import init_db; init_db()"

# 5. Start API
uvicorn api.main:app --reload --port 8000

# 6. Start Dashboard (in another terminal)
streamlit run dashboard/app.py
```

### Verify Everything Works

1. Upload an image in the Streamlit dashboard
2. Check API console for `[GEMINI]` log lines
3. Verify data in MySQL:
   ```bash
   mysql -h localhost -u root -p image_enhancer << 'EOF'
   SELECT COUNT(*) as product_images FROM product_images;
   SELECT COUNT(*) as enhancements FROM enhancement_history;
   EOF
   ```

### Common Errors and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `S3 bucket not configured` | S3_BUCKET env var not set | `export S3_BUCKET=...` |
| `Access denied to S3 bucket` | Wrong AWS credentials | Verify AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY |
| `No tables in database` | Database not initialized | Run `init_db()` |
| `Can't connect to MySQL` | Service not running or wrong credentials | Check MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD |
| `Gemini enhancement failed` | API key not set or invalid | `export GEMINI_API_KEY=...` |

### Contact Support

If issues persist:
1. Review full error messages in console logs
2. Check that all environment variables are set correctly
3. Ensure MySQL and any external services (AWS, Google) are accessible
