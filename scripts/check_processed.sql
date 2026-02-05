-- Check if processed column exists and add if not
SET @col_exists = (
    SELECT COUNT(*) 
    FROM information_schema.COLUMNS 
    WHERE TABLE_SCHEMA = DATABASE() 
    AND TABLE_NAME = 'product_images' 
    AND COLUMN_NAME = 'processed'
);

-- Add column if it doesn't exist
SET @sql = IF(@col_exists = 0, 
    'ALTER TABLE product_images ADD COLUMN processed TINYINT(1) DEFAULT 0 AFTER is_high_value',
    'SELECT "Column already exists" as message'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Add index if column was just created
SET @sql = IF(@col_exists = 0, 
    'CREATE INDEX ix_product_images_processed ON product_images(processed)',
    'SELECT "Index already exists" as message'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Show unprocessed count
SELECT COUNT(*) as unprocessed_count FROM product_images WHERE processed = 0 OR processed IS NULL;

-- Show sample records
SELECT id, sku_id, LEFT(image_url, 50) as image_url, status, processed FROM product_images LIMIT 5;
