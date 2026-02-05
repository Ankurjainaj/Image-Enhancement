#!/bin/bash
# Test Upload with S3 & Database Persistence
# Run these commands to test the image upload flow

echo "================================"
echo "IMAGE UPLOAD API TEST SCRIPT"
echo "================================"
echo ""

# Configuration
API_URL="http://localhost:8000"
TEST_IMAGE="${1:-test_image.jpg}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if test image exists
if [ ! -f "$TEST_IMAGE" ]; then
    echo -e "${RED}✗ Test image not found: $TEST_IMAGE${NC}"
    echo ""
    echo "Usage: $0 [image_path]"
    echo "Example: $0 /path/to/photo.jpg"
    exit 1
fi

echo -e "${YELLOW}Test Image:${NC} $TEST_IMAGE"
echo -e "${YELLOW}API URL:${NC} $API_URL"
echo ""

# ============================================
# TEST 1: Upload with Default Settings
# ============================================
echo -e "${YELLOW}═══ TEST 1: Upload with Default Settings ═══${NC}"
echo ""
echo "Command:"
echo "curl -X POST \"$API_URL/api/v1/enhance/upload\" \\"
echo "  -F \"file=@$TEST_IMAGE\""
echo ""
echo "Response:"

RESPONSE=$(curl -s -X POST "$API_URL/api/v1/enhance/upload" \
  -F "file=@$TEST_IMAGE")

echo "$RESPONSE" | jq '.' 2>/dev/null || echo "$RESPONSE"

# Extract image_id from response
IMAGE_ID=$(echo "$RESPONSE" | jq -r '.image_id' 2>/dev/null)
DATABASE_ID=$(echo "$RESPONSE" | jq -r '.database_id' 2>/dev/null)

if [ "$IMAGE_ID" != "null" ] && [ -n "$IMAGE_ID" ]; then
    echo -e "${GREEN}✓ Upload successful!${NC}"
    echo -e "${GREEN}  Image ID: $IMAGE_ID${NC}"
    echo -e "${GREEN}  Database ID: $DATABASE_ID${NC}"
else
    echo -e "${RED}✗ Upload failed!${NC}"
    exit 1
fi

echo ""

# ============================================
# TEST 2: List All Uploaded Images
# ============================================
echo -e "${YELLOW}═══ TEST 2: List All Uploaded Images ═══${NC}"
echo ""
echo "Command:"
echo "curl \"$API_URL/api/v1/images?limit=10&status=COMPLETED\""
echo ""
echo "Response:"

curl -s "$API_URL/api/v1/images?limit=10&status=COMPLETED" | jq '.'

echo ""

# ============================================
# TEST 3: Get Specific Image Details
# ============================================
if [ -n "$DATABASE_ID" ] && [ "$DATABASE_ID" != "null" ]; then
    echo -e "${YELLOW}═══ TEST 3: Get Specific Image Details ═══${NC}"
    echo ""
    echo "Command:"
    echo "curl \"$API_URL/api/v1/images/$DATABASE_ID/enhancement-history\""
    echo ""
    echo "Response:"
    
    curl -s "$API_URL/api/v1/images/$DATABASE_ID/enhancement-history" | jq '.'
    
    echo ""
fi

# ============================================
# TEST 4: Upload with Different Enhancement Mode
# ============================================
echo -e "${YELLOW}═══ TEST 4: Upload with GEMINI Enhancement ═══${NC}"
echo ""
echo "Command:"
echo "curl -X POST \"$API_URL/api/v1/enhance/gemini\" \\"
echo "  -F \"file=@$TEST_IMAGE\""
echo ""
echo "Response:"

GEMINI_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/enhance/gemini" \
  -F "file=@$TEST_IMAGE")

echo "$GEMINI_RESPONSE" | jq '.' 2>/dev/null || echo "$GEMINI_RESPONSE"

echo ""

# ============================================
# TEST 5: Verify MySQL Records
# ============================================
echo -e "${YELLOW}═══ TEST 5: Verify MySQL Records ═══${NC}"
echo ""
echo "Command:"
echo "mysql -h localhost -u root -p image_enhancer -e 'SELECT sku_id, image_url, enhanced_image_url FROM product_images LIMIT 1\G'"
echo ""

if command -v mysql &> /dev/null; then
    echo "Response:"
    mysql -h localhost -u root -p"${MYSQL_PASSWORD}" image_enhancer -e \
        "SELECT id, sku_id, image_url, enhanced_image_url, status FROM product_images ORDER BY created_at DESC LIMIT 1\G" 2>/dev/null || echo "MySQL connection failed"
else
    echo -e "${YELLOW}⚠ MySQL client not found${NC}"
fi

echo ""

# ============================================
# TEST 6: Verify S3 Files
# ============================================
echo -e "${YELLOW}═══ TEST 6: Verify S3 Files ═══${NC}"
echo ""
echo "Command:"
echo "aws s3 ls s3://\$S3_BUCKET/uploads/"
echo ""

if command -v aws &> /dev/null; then
    echo "Response:"
    echo "Original images:"
    aws s3 ls "s3://pixel-lab-s3/uploads/original/" 2>/dev/null || echo "S3 access failed"
    echo ""
    echo "Enhanced images:"
    aws s3 ls "s3://pixel-lab-s3/uploads/enhanced/" 2>/dev/null || echo "S3 access failed"
else
    echo -e "${YELLOW}⚠ AWS CLI not found${NC}"
fi

echo ""

# ============================================
# TEST 7: Test Enhancement History
# ============================================
if [ -n "$DATABASE_ID" ] && [ "$DATABASE_ID" != "null" ]; then
    echo -e "${YELLOW}═══ TEST 7: Get Enhancement History ═══${NC}"
    echo ""
    echo "Command:"
    echo "curl \"$API_URL/api/v1/images/$DATABASE_ID/enhancement-history\""
    echo ""
    echo "Response:"
    
    HISTORY=$(curl -s "$API_URL/api/v1/images/$DATABASE_ID/enhancement-history")
    echo "$HISTORY" | jq '.enhancements[0] | {enhancement_sequence, enhancement_mode, quality_metadata, size_metadata, created_at}' 2>/dev/null || echo "$HISTORY"
    
    echo ""
fi

# ============================================
# Summary
# ============================================
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ ALL TESTS COMPLETED${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo ""
echo "Summary:"
echo -e "  Image ID: ${GREEN}$IMAGE_ID${NC}"
echo -e "  Database ID: ${GREEN}$DATABASE_ID${NC}"
echo ""
echo "Next steps:"
echo "  1. Check MySQL: SELECT * FROM product_images WHERE id='$DATABASE_ID'"
echo "  2. Check S3: aws s3 ls s3://\$S3_BUCKET/uploads/"
echo "  3. Download: aws s3 cp s3://\$S3_BUCKET/uploads/enhanced/..."
echo "  4. Get History: curl $API_URL/api/v1/images/$DATABASE_ID/enhancement-history"
echo ""

# ============================================
# Additional Test Commands (reference)
# ============================================
cat << 'EOF'
════════════════════════════════════════
ADDITIONAL TEST COMMANDS (Copy & Paste)
════════════════════════════════════════

# Upload with specific enhancement mode
curl -X POST "http://localhost:8000/api/v1/enhance/upload" \
  -F "file=@test_image.jpg" \
  -F "mode=AUTO" \
  -F "target_size_kb=500" \
  -F "output_format=JPEG"

# List images with pagination
curl "http://localhost:8000/api/v1/images?limit=50&offset=0&status=COMPLETED"

# List images in processing
curl "http://localhost:8000/api/v1/images?status=PROCESSING"

# List failed images
curl "http://localhost:8000/api/v1/images?status=FAILED"

# Get full image record
curl "http://localhost:8000/api/v1/images/IMAGE_ID/enhancement-history" | jq '.'

# Download enhanced image
curl "http://localhost:8000/api/v1/images/IMAGE_ID/enhanced" -o enhanced.jpg

# Test Gemini enhancement
curl -X POST "http://localhost:8000/api/v1/enhance/gemini" \
  -F "file=@test_image.jpg" \
  -F "enhancement_prompt=enhance the quality"

# MySQL Queries
mysql -h localhost -u root -p image_enhancer << EOF
  -- View all uploaded images
  SELECT sku_id, original_filename, image_url, enhanced_image_url 
  FROM product_images LIMIT 10;
  
  -- View enhancement history
  SELECT enhancement_sequence, enhancement_mode, quality_metadata 
  FROM enhancement_history 
  WHERE product_image_id='IMAGE_ID';
  
  -- Get stats
  SELECT COUNT(*) as total, status, enhancement_mode 
  FROM product_images 
  GROUP BY status, enhancement_mode;
EOF

# AWS S3 Commands
aws s3 ls s3://pixel-lab-s3/uploads/original/
aws s3 ls s3://pixel-lab-s3/uploads/enhanced/
aws s3 cp s3://pixel-lab-s3/uploads/enhanced/file.jpg ./
aws s3api head-object --bucket pixel-lab-s3 --key uploads/enhanced/file.jpg

# Verify HTTPS URLs
curl -I "https://d123456.cloudfront.net/uploads/enhanced/image.jpg"

════════════════════════════════════════
EOF

exit 0
