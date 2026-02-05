#!/bin/bash
# Add processed column to product_images table

mysql -h localhost -u root -proot@123 image_enhancer << 'EOF'
-- Add processed column (ignore error if exists)
ALTER TABLE product_images ADD COLUMN processed TINYINT(1) DEFAULT 0 AFTER is_high_value;

-- Show unprocessed count
SELECT COUNT(*) as unprocessed_count FROM product_images WHERE processed = 0 OR processed IS NULL;

-- Show sample
SELECT id, sku_id, LEFT(image_url, 60) as image_url, status, IFNULL(processed, 0) as processed FROM product_images LIMIT 3;
EOF

echo "✓ Migration complete"
