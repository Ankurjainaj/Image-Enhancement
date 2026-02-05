-- Add processed column to product_images table
ALTER TABLE product_images 
ADD COLUMN processed TINYINT(1) DEFAULT 0 AFTER is_high_value;

-- Create index on processed column for faster queries
CREATE INDEX ix_product_images_processed ON product_images(processed);

-- Set processed=1 for already completed images
UPDATE product_images 
SET processed = 1 
WHERE status = 'completed';
