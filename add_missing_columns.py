#!/usr/bin/env python3
"""Add missing columns to enhancement_history table"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
load_dotenv()

import pymysql

conn = pymysql.connect(
    host=os.getenv('MYSQL_HOST'),
    port=int(os.getenv('MYSQL_PORT', 3306)),
    user=os.getenv('MYSQL_USER'),
    password=os.getenv('MYSQL_PASSWORD'),
    database=os.getenv('MYSQL_DATABASE')
)

cursor = conn.cursor()

try:
    cursor.execute("DESC enhancement_history")
    columns = [row[0] for row in cursor.fetchall()]
    
    missing_columns = []
    
    if 'original_s3_url' not in columns:
        missing_columns.append('original_s3_url')
    if 'original_https_url' not in columns:
        missing_columns.append('original_https_url')
    if 'enhanced_s3_url' not in columns:
        missing_columns.append('enhanced_s3_url')
    if 'enhanced_https_url' not in columns:
        missing_columns.append('enhanced_https_url')
    
    if missing_columns:
        print(f"Missing columns: {missing_columns}")
        print("Adding missing columns...")
        
        for col in missing_columns:
            cursor.execute(f"""
                ALTER TABLE enhancement_history 
                ADD COLUMN {col} VARCHAR(2048) NULL
            """)
        
        conn.commit()
        print("✓ Columns added successfully")
    else:
        print("✓ All required columns exist")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    cursor.close()
    conn.close()
