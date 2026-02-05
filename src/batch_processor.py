"""
Batch Processing Service for Image Enhancement
Handles async batch processing of images
"""
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any
import httpx

from .database import get_db, ProductImageRepository, JobRepository, ProcessingStatus, ProductImage
from .config import get_config

logger = logging.getLogger(__name__)
config = get_config()


async def process_batch_async(job_id: str, image_ids: List[str], mode: str = "auto", batch_size: int = 10):
    """Process batch of images asynchronously in smaller batches"""
    db = get_db()
    try:
        job_repo = JobRepository(db)
        image_repo = ProductImageRepository(db)
        
        # Update job status to processing
        job_repo.update_progress(job_id, status=ProcessingStatus.PROCESSING.value, started_at=datetime.utcnow())
        
        success_count = 0
        failed_count = 0
        
        # Process in batches to reduce load
        async with httpx.AsyncClient(timeout=300.0) as client:
            for i in range(0, len(image_ids), batch_size):
                batch = image_ids[i:i + batch_size]
                
                for image_id in batch:
                    try:
                        image = image_repo.get_by_id(image_id)
                        if not image or not image.image_url:
                            failed_count += 1
                            continue
                        
                        # Skip if already processing or completed
                        if image.status in [ProcessingStatus.PROCESSING.value, ProcessingStatus.COMPLETED.value]:
                            continue
                        
                        # Mark as processing
                        image_repo.update_status(image_id, ProcessingStatus.PROCESSING)
                        
                        # Call enhancement API with existing SKU_ID and image_id
                        response = await client.post(
                            f"http://localhost:{config.api.port}/api/v1/enhance/url",
                            json={
                                "url": image.image_url, 
                                "mode": mode, 
                                "output_format": "JPEG",
                                "sku_id": image.sku_id,
                                "image_id": image_id
                            }
                        )
                        
                        if response.status_code == 200:
                            success_count += 1
                        else:
                            failed_count += 1
                            image_repo.update_status(image_id, ProcessingStatus.FAILED, error_message=response.text)
                            
                    except Exception as e:
                        logger.error(f"Error processing image {image_id}: {e}")
                        failed_count += 1
                        try:
                            image_repo.update_status(image_id, ProcessingStatus.FAILED, error_message=str(e))
                        except:
                            pass
                    
                    # Update progress
                    processed = success_count + failed_count
                    job_repo.update_progress(
                        job_id,
                        processed_count=processed,
                        success_count=success_count,
                        failed_count=failed_count
                    )
                
                # Small delay between batches to reduce load
                if i + batch_size < len(image_ids):
                    await asyncio.sleep(2)
        
        # Mark job as completed
        job_repo.update_progress(
            job_id,
            status=ProcessingStatus.COMPLETED.value,
            completed_at=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Batch job {job_id} failed: {e}")
        job_repo.update_progress(job_id, status=ProcessingStatus.FAILED.value, error_message=str(e))
    finally:
        db.close()
