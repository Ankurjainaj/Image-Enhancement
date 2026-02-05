# Environment Configuration Guide

## Database Configuration
Set these environment variables for MySQL database connection:

```bash
# MySQL Connection
export MYSQL_HOST=localhost
export MYSQL_PORT=3306
export MYSQL_DATABASE=image_enhancer
export MYSQL_USER=root
export MYSQL_PASSWORD=your_password
```

## S3 Configuration (Required for Gemini Enhancement)
Set these environment variables for AWS S3:

```bash
# AWS S3 Configuration
export S3_BUCKET=your-bucket-name
export AWS_REGION=ap-south-1
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key

# Optional: CloudFront Domain (if using CDN)
export CLOUDFRONT_DOMAIN=https://d123456.cloudfront.net
```

## Gemini API Configuration
Set this environment variable for Google Gemini:

```bash
# Gemini API Key
export GEMINI_API_KEY=your_gemini_api_key
```

## Database Initialization

Before running the application, initialize the database tables:

```python
from src.database import init_db
init_db()
```

Or via shell:
```bash
python -c "from src.database import init_db; init_db()"
```

## Troubleshooting

### Data Not Being Inserted
1. **Check MySQL Connection**: Verify MySQL is running and credentials are correct
   ```bash
   mysql -h localhost -u root -p
   ```

2. **Check S3 Configuration**: Ensure S3_BUCKET environment variable is set
   ```bash
   echo $S3_BUCKET
   ```

3. **Check Database Tables**: Verify tables are created
   ```bash
   mysql -h localhost -u root -p image_enhancer -e "SHOW TABLES;"
   ```

4. **Review API Logs**: The API logs will show detailed errors if data insertion fails
   - Check console output from uvicorn
   - Look for [GEMINI] prefixed log lines for debugging

### S3 Upload Failing
- Verify AWS credentials have S3 permissions
- Check that bucket exists and is accessible
- Verify bucket name is correct (case-sensitive)

### Gemini Enhancement Not Working
- Ensure GEMINI_API_KEY is set
- Verify API key is valid and has appropriate permissions
- Check network connectivity

## Example .env File

Create a `.env` file in the project root:

```
# MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=image_enhancer
MYSQL_USER=root
MYSQL_PASSWORD=root

# AWS S3
S3_BUCKET=pixel-lab-s3
AWS_REGION=ap-south-1
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
CLOUDFRONT_DOMAIN=https://d123456.cloudfront.net

# Gemini API
GEMINI_API_KEY=your_gemini_api_key_here

# Optional
LOG_LEVEL=INFO
USE_S3_ONLY=true
```

Then load it in your shell:
```bash
source .env
```
