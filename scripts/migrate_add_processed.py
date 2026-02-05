#!/usr/bin/env python3
"""
Migration script to add 'processed' column to product_images table
"""
from sqlalchemy import text
from src.database import get_db

def add_processed_column():
    db = get_db()
    try:
        # Check if column exists
        result = db.execute(text("""
            SELECT COUNT(*) as count 
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'product_images' 
            AND COLUMN_NAME = 'processed'
        """))
        exists = result.fetchone()[0] > 0
        
        if exists:
            print("✓ Column 'processed' already exists")
            return
        
        print("Adding 'processed' column to product_images table...")
        
        # Add column
        db.execute(text("""
            ALTER TABLE product_images 
            ADD COLUMN processed TINYINT(1) DEFAULT 0 AFTER is_high_value
        """))
        
        # Create index
        db.execute(text("""
            CREATE INDEX ix_product_images_processed ON product_images(processed)
        """))
        
        # Set processed=1 for already completed images
        db.execute(text("""
            UPDATE product_images 
            SET processed = 1 
            WHERE status = 'completed'
        """))
        
        db.commit()
        print("✓ Migration completed successfully")
        print("  - Added 'processed' column")
        print("  - Created index on 'processed'")
        print("  - Updated existing completed images")
        
    except Exception as e:
        db.rollback()
        print(f"✗ Migration failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    add_processed_column()
