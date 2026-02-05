-- Add analysis metrics columns to product_images table
ALTER TABLE product_images 
ADD COLUMN analysis_blur_score FLOAT DEFAULT NULL,
ADD COLUMN analysis_brightness FLOAT DEFAULT NULL,
ADD COLUMN analysis_contrast FLOAT DEFAULT NULL,
ADD COLUMN analysis_noise FLOAT DEFAULT NULL,
ADD COLUMN analysis_bg_complexity FLOAT DEFAULT NULL,
ADD COLUMN analysis_metadata JSON DEFAULT NULL;
