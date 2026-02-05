-- Insert test data for batch processing
-- These images will have processed=0 so they can be picked up by AUTO mode

INSERT INTO product_images (
    id,
    sku_id,
    image_url,
    status,
    processed,
    created_at
) VALUES 
(
    UUID(),
    'TEST-SKU-001',
    'https://images.unsplash.com/photo-1505740420928-5e560c06d30e',
    'pending',
    0,
    NOW()
),
(
    UUID(),
    'TEST-SKU-002',
    'https://images.unsplash.com/photo-1523275335684-37898b6baf30',
    'pending',
    0,
    NOW()
),
(
    UUID(),
    'TEST-SKU-003',
    'https://images.unsplash.com/photo-1572635196237-14b3f281503f',
    'pending',
    0,
    NOW()
);

-- Verify inserted data
SELECT id, sku_id, LEFT(image_url, 50) as url, status, processed 
FROM product_images 
WHERE processed = 0 
ORDER BY created_at DESC 
LIMIT 5;
