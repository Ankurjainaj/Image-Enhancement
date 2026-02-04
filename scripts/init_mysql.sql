-- =====================================================
-- Image Enhancement Pipeline - MySQL Database Setup
-- MedikaBazaar B2B Marketplace Image Enhancement
-- =====================================================
-- Run: mysql -u root -p < scripts/init_mysql.sql
-- =====================================================

-- Create database
CREATE DATABASE IF NOT EXISTS image_enhancer
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE image_enhancer;

-- =====================================================
-- Table: product_groups
-- =====================================================
CREATE TABLE IF NOT EXISTS product_groups (
    id VARCHAR(36) PRIMARY KEY,
    product_group_id VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255),
    category VARCHAR(100),
    sub_category VARCHAR(100),
    description TEXT,
    total_skus INT DEFAULT 0,
    total_images INT DEFAULT 0,
    enhanced_images INT DEFAULT 0,
    pending_images INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_product_group_id (product_group_id),
    INDEX idx_category (category)
) ENGINE=InnoDB;

-- =====================================================
-- Table: skus
-- =====================================================
CREATE TABLE IF NOT EXISTS skus (
    id VARCHAR(36) PRIMARY KEY,
    sku_id VARCHAR(100) NOT NULL UNIQUE,
    product_group_ref VARCHAR(36),
    name VARCHAR(255),
    brand VARCHAR(100),
    manufacturer VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    total_images INT DEFAULT 0,
    enhanced_images INT DEFAULT 0,
    pending_images INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_sku_id (sku_id),
    INDEX idx_product_group (product_group_ref),
    
    FOREIGN KEY (product_group_ref) REFERENCES product_groups(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- =====================================================
-- Table: product_images (MAIN TABLE)
-- Key fields: product_group_id, sku_id, image_url, enhanced_image_url
-- =====================================================
CREATE TABLE IF NOT EXISTS product_images (
    id VARCHAR(36) PRIMARY KEY,
    sku_ref VARCHAR(36),
    
    -- KEY BUSINESS FIELDS
    product_group_id VARCHAR(100),
    sku_id VARCHAR(100) NOT NULL,
    image_url VARCHAR(2048) NOT NULL,
    enhanced_image_url VARCHAR(2048),
    
    -- Local storage paths
    original_local_path VARCHAR(512),
    enhanced_local_path VARCHAR(512),
    
    -- Original image metadata
    original_filename VARCHAR(255),
    original_width INT,
    original_height INT,
    original_size_bytes BIGINT,
    original_format VARCHAR(20),
    original_dpi INT,
    
    -- Enhanced image metadata
    enhanced_width INT,
    enhanced_height INT,
    enhanced_size_bytes BIGINT,
    enhanced_format VARCHAR(20),
    enhanced_dpi INT,
    
    -- Image type/angle (multi-angle support)
    image_type VARCHAR(50) DEFAULT 'primary',
    image_sequence SMALLINT DEFAULT 1,
    
    -- Processing status
    status VARCHAR(20) DEFAULT 'pending',
    enhancement_mode VARCHAR(50),
    enhancements_applied JSON,
    
    processing_time_ms INT,
    processed_at DATETIME,
    error_message TEXT,
    retry_count SMALLINT DEFAULT 0,
    
    -- QC Status (Human-in-the-Loop)
    qc_status VARCHAR(20) DEFAULT 'pending',
    qc_score FLOAT,
    qc_reviewed_by VARCHAR(100),
    qc_reviewed_at DATETIME,
    qc_notes TEXT,
    
    -- Flags
    is_hero_image BOOLEAN DEFAULT FALSE,
    needs_background_removal BOOLEAN DEFAULT TRUE,
    background_removed BOOLEAN DEFAULT FALSE,
    needs_upscaling BOOLEAN DEFAULT FALSE,
    is_standardized BOOLEAN DEFAULT FALSE,
    is_high_value BOOLEAN DEFAULT FALSE,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_image_url (image_url(255)),
    INDEX idx_sku_id (sku_id),
    INDEX idx_product_group_id (product_group_id),
    INDEX idx_status (status),
    INDEX idx_qc_status (qc_status),
    INDEX idx_status_created (status, created_at),
    INDEX idx_sku_status (sku_id, status),
    
    FOREIGN KEY (sku_ref) REFERENCES skus(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- =====================================================
-- Table: image_metrics
-- =====================================================
CREATE TABLE IF NOT EXISTS image_metrics (
    id VARCHAR(36) PRIMARY KEY,
    image_id VARCHAR(36) NOT NULL UNIQUE,
    
    -- Original metrics
    original_blur_score FLOAT,
    original_brightness FLOAT,
    original_contrast FLOAT,
    original_noise_level FLOAT,
    original_edge_density FLOAT,
    original_brisque_score FLOAT,
    original_quality_score FLOAT,
    original_quality_tier VARCHAR(20),
    
    -- Enhanced metrics
    enhanced_blur_score FLOAT,
    enhanced_brightness FLOAT,
    enhanced_contrast FLOAT,
    enhanced_noise_level FLOAT,
    enhanced_edge_density FLOAT,
    enhanced_brisque_score FLOAT,
    enhanced_quality_score FLOAT,
    enhanced_quality_tier VARCHAR(20),
    
    -- Improvement metrics
    quality_improvement_percent FLOAT,
    size_reduction_percent FLOAT,
    sharpness_improvement_percent FLOAT,
    resolution_increase_percent FLOAT,
    
    -- Background analysis
    has_background BOOLEAN,
    background_complexity FLOAT,
    background_removed BOOLEAN DEFAULT FALSE,
    
    -- Light/Color metrics
    exposure_corrected BOOLEAN DEFAULT FALSE,
    color_balanced BOOLEAN DEFAULT FALSE,
    
    assessed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (image_id) REFERENCES product_images(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- =====================================================
-- Table: processing_jobs
-- =====================================================
CREATE TABLE IF NOT EXISTS processing_jobs (
    id VARCHAR(36) PRIMARY KEY,
    job_type VARCHAR(50) DEFAULT 'batch',
    enhancement_mode VARCHAR(50) DEFAULT 'auto',
    priority SMALLINT DEFAULT 5,
    
    product_group_id VARCHAR(100),
    sku_id VARCHAR(100),
    
    status VARCHAR(20) DEFAULT 'pending',
    total_images INT DEFAULT 0,
    processed_count INT DEFAULT 0,
    success_count INT DEFAULT 0,
    failed_count INT DEFAULT 0,
    skipped_count INT DEFAULT 0,
    
    auto_approved_count INT DEFAULT 0,
    needs_review_count INT DEFAULT 0,
    
    started_at DATETIME,
    completed_at DATETIME,
    
    avg_processing_time_ms FLOAT,
    avg_quality_improvement FLOAT,
    avg_size_reduction FLOAT,
    total_input_size_bytes BIGINT DEFAULT 0,
    total_output_size_bytes BIGINT DEFAULT 0,
    
    error_message TEXT,
    
    kafka_offset BIGINT,
    kafka_partition INT,
    
    created_by VARCHAR(100),
    job_metadata JSON,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_status (status),
    INDEX idx_product_group_id (product_group_id),
    INDEX idx_sku_id (sku_id)
) ENGINE=InnoDB;

-- =====================================================
-- Table: enhancement_configs
-- =====================================================
CREATE TABLE IF NOT EXISTS enhancement_configs (
    id VARCHAR(36) PRIMARY KEY,
    config_type VARCHAR(20) DEFAULT 'global',
    product_group_id VARCHAR(100),
    category VARCHAR(100),
    sku_id VARCHAR(100),
    
    -- Enhancement toggles (per MedikaBazaar requirements)
    enable_background_removal BOOLEAN DEFAULT TRUE,
    background_color VARCHAR(20) DEFAULT '#FFFFFF',
    
    enable_light_correction BOOLEAN DEFAULT TRUE,
    enable_color_balance BOOLEAN DEFAULT TRUE,
    
    enable_upscaling BOOLEAN DEFAULT TRUE,
    target_min_dimension INT DEFAULT 1500,
    max_upscale_factor FLOAT DEFAULT 2.0,
    target_dpi INT DEFAULT 300,
    
    enable_denoising BOOLEAN DEFAULT TRUE,
    denoise_strength INT DEFAULT 10,
    
    enable_sharpening BOOLEAN DEFAULT TRUE,
    sharpen_strength FLOAT DEFAULT 1.5,
    
    -- Standardization settings
    enable_standardization BOOLEAN DEFAULT TRUE,
    target_aspect_ratio VARCHAR(10) DEFAULT '1:1',
    target_width INT DEFAULT 1200,
    target_height INT DEFAULT 1200,
    padding_percent INT DEFAULT 5,
    
    -- Output settings
    output_format VARCHAR(10) DEFAULT 'JPEG',
    jpeg_quality INT DEFAULT 92,
    target_max_size_kb INT DEFAULT 500,
    
    -- QC settings (Human-in-the-Loop)
    auto_approve_threshold FLOAT DEFAULT 75.0,
    require_human_qc BOOLEAN DEFAULT FALSE,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_category (category),
    INDEX idx_product_group_id (product_group_id),
    INDEX idx_sku_id (sku_id)
) ENGINE=InnoDB;

-- =====================================================
-- Table: qc_review_logs
-- =====================================================
CREATE TABLE IF NOT EXISTS qc_review_logs (
    id VARCHAR(36) PRIMARY KEY,
    image_id VARCHAR(36) NOT NULL,
    
    reviewer_id VARCHAR(100) NOT NULL,
    reviewer_name VARCHAR(255),
    
    previous_status VARCHAR(20),
    new_status VARCHAR(20) NOT NULL,
    
    score FLOAT,
    notes TEXT,
    rejection_reason VARCHAR(255),
    
    reviewed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_image_id (image_id),
    INDEX idx_reviewer_id (reviewer_id),
    
    FOREIGN KEY (image_id) REFERENCES product_images(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- =====================================================
-- Insert default global enhancement config
-- =====================================================
INSERT INTO enhancement_configs (
    id, config_type, 
    enable_background_removal, background_color,
    enable_light_correction, enable_color_balance,
    enable_upscaling, target_min_dimension, target_dpi,
    enable_denoising, enable_sharpening,
    enable_standardization, target_aspect_ratio, target_width, target_height
) VALUES (
    UUID(), 'global',
    TRUE, '#FFFFFF',
    TRUE, TRUE,
    TRUE, 1500, 300,
    TRUE, TRUE,
    TRUE, '1:1', 1200, 1200
) ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP;

-- =====================================================
-- Useful Views
-- =====================================================

-- View: Image processing summary by SKU
CREATE OR REPLACE VIEW v_sku_image_summary AS
SELECT 
    s.sku_id,
    s.name AS sku_name,
    s.brand,
    pg.product_group_id,
    COUNT(pi.id) AS total_images,
    SUM(CASE WHEN pi.status = 'completed' THEN 1 ELSE 0 END) AS enhanced_count,
    SUM(CASE WHEN pi.status = 'pending' THEN 1 ELSE 0 END) AS pending_count,
    SUM(CASE WHEN pi.status = 'failed' THEN 1 ELSE 0 END) AS failed_count,
    SUM(CASE WHEN pi.qc_status = 'needs_review' THEN 1 ELSE 0 END) AS needs_qc_count,
    SUM(CASE WHEN pi.background_removed = TRUE THEN 1 ELSE 0 END) AS bg_removed_count,
    AVG(im.quality_improvement_percent) AS avg_quality_improvement,
    AVG(im.size_reduction_percent) AS avg_size_reduction
FROM skus s
LEFT JOIN product_groups pg ON s.product_group_ref = pg.id
LEFT JOIN product_images pi ON s.sku_id = pi.sku_id
LEFT JOIN image_metrics im ON pi.id = im.image_id
GROUP BY s.sku_id, s.name, s.brand, pg.product_group_id;

-- View: Daily processing stats
CREATE OR REPLACE VIEW v_daily_processing_stats AS
SELECT 
    DATE(processed_at) AS processing_date,
    COUNT(*) AS images_processed,
    AVG(processing_time_ms) AS avg_processing_time_ms,
    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS success_count,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_count,
    SUM(CASE WHEN background_removed = TRUE THEN 1 ELSE 0 END) AS bg_removed_count
FROM product_images
WHERE processed_at IS NOT NULL
GROUP BY DATE(processed_at)
ORDER BY processing_date DESC;

-- View: QC review queue
CREATE OR REPLACE VIEW v_qc_review_queue AS
SELECT 
    pi.id,
    pi.product_group_id,
    pi.sku_id,
    pi.image_url,
    pi.enhanced_image_url,
    pi.qc_status,
    pi.qc_score,
    pi.is_high_value,
    pi.background_removed,
    im.original_quality_score,
    im.enhanced_quality_score,
    im.quality_improvement_percent,
    pi.processed_at
FROM product_images pi
LEFT JOIN image_metrics im ON pi.id = im.image_id
WHERE pi.qc_status = 'needs_review'
ORDER BY pi.is_high_value DESC, pi.processed_at ASC;

-- View: Product group enhancement summary
CREATE OR REPLACE VIEW v_product_group_summary AS
SELECT 
    pg.product_group_id,
    pg.name,
    pg.category,
    COUNT(DISTINCT s.sku_id) AS total_skus,
    COUNT(pi.id) AS total_images,
    SUM(CASE WHEN pi.status = 'completed' THEN 1 ELSE 0 END) AS enhanced_count,
    ROUND(SUM(CASE WHEN pi.status = 'completed' THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(pi.id), 0), 2) AS completion_percent
FROM product_groups pg
LEFT JOIN skus s ON pg.id = s.product_group_ref
LEFT JOIN product_images pi ON s.sku_id = pi.sku_id
GROUP BY pg.product_group_id, pg.name, pg.category;

SELECT 'MedikaBazaar Image Enhancement Database initialized successfully!' AS status;
