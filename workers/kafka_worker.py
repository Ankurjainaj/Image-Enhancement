"""
Kafka Worker for Image Enhancement
Consumes jobs from Kafka and processes images
"""
import os
import sys
import time
import logging
import signal
from pathlib import Path
from typing import Optional
from datetime import datetime

import httpx
import redis

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_config, ProcessingStatus
from src.database import init_db, get_db, ImageRepository, JobRepository
from src.enhancer import ImageEnhancer
from src.quality import QualityAssessor
from src.kafka_service import (
    KafkaConsumerService, KafkaProducerService,
    ImageJob, JobResult
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

config = get_config()


class ImageWorker:
    """
    Worker that processes image enhancement jobs from Kafka
    """
    
    def __init__(self, worker_id: Optional[str] = None):
        self.worker_id = worker_id or f"worker-{os.getpid()}"
        self.enhancer = ImageEnhancer()
        self.assessor = QualityAssessor()
        self.consumer = None
        self.producer = None
        self.redis_client = None
        self._running = False
        
    def setup(self):
        """Initialize connections"""
        logger.info(f"Starting worker: {self.worker_id}")
        
        # Initialize database
        init_db()
        
        # Initialize Kafka
        self.consumer = KafkaConsumerService(
            group_id=f"{config.kafka.consumer_group}"
        )
        self.consumer.subscribe()
        
        self.producer = KafkaProducerService()
        
        # Initialize Redis
        try:
            self.redis_client = redis.Redis(
                host=config.redis.host,
                port=config.redis.port,
                db=config.redis.db,
                password=config.redis.password,
                decode_responses=True
            )
            self.redis_client.ping()
            logger.info("Redis connected")
        except Exception as e:
            logger.warning(f"Redis not available: {e}")
            self.redis_client = None
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
    
    def _handle_signal(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self._running = False
        if self.consumer:
            self.consumer.stop()
    
    def fetch_image(self, url: str, timeout: float = 30.0) -> bytes:
        """Fetch image from URL"""
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.content
    
    def process_job(self, job: ImageJob) -> JobResult:
        """
        Process a single image enhancement job
        
        Args:
            job: ImageJob to process
        
        Returns:
            JobResult with processing results
        """
        start_time = time.time()
        result = JobResult(
            job_id=job.job_id,
            image_id=job.image_id,
            original_url=job.original_url,
            status=ProcessingStatus.PROCESSING.value
        )
        
        try:
            logger.info(f"Processing job {job.job_id}: {job.original_url}")
            
            # Update status in Redis
            self._update_status(job.job_id, "processing")
            
            # Fetch image
            image_bytes = self.fetch_image(job.original_url)
            result.original_size_bytes = len(image_bytes)
            
            # Assess quality before
            quality_before = self.assessor.quick_assess(image_bytes)
            result.quality_before = quality_before.get('blur_score', 0)
            
            # Enhance image
            enhancement_result = self.enhancer.enhance(
                image_bytes,
                mode=job.enhancement_mode,
                output_format="JPEG"
            )
            
            if not enhancement_result.success:
                raise Exception(enhancement_result.error)
            
            # Get enhanced bytes
            enhanced_bytes = self.enhancer.get_enhanced_bytes(
                enhancement_result,
                "JPEG",
                config.enhancement.target_max_size_kb
            )
            
            # Assess quality after
            quality_after = self.assessor.quick_assess(enhanced_bytes)
            result.quality_after = quality_after.get('blur_score', 0)
            
            # Save enhanced image
            storage_path = config.storage.local_storage_path / f"{job.image_id}.jpg"
            storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(storage_path, 'wb') as f:
                f.write(enhanced_bytes)
            
            # Update result
            result.status = ProcessingStatus.COMPLETED.value
            result.enhanced_path = str(storage_path)
            result.enhanced_size_bytes = len(enhanced_bytes)
            result.enhancements_applied = enhancement_result.enhancements_applied
            
            # Calculate improvements
            if result.quality_before and result.quality_before > 0:
                result.quality_improvement = (
                    (result.quality_after - result.quality_before) / result.quality_before * 100
                )
            
            if result.original_size_bytes > 0:
                result.size_reduction = (
                    (1 - result.enhanced_size_bytes / result.original_size_bytes) * 100
                )
            
            # Update database
            self._update_database(job, result)
            
            logger.info(
                f"Completed job {job.job_id}: "
                f"quality +{result.quality_improvement:.1f}%, "
                f"size -{result.size_reduction:.1f}%"
            )
            
        except httpx.HTTPError as e:
            result.status = ProcessingStatus.FAILED.value
            result.error = f"Failed to fetch image: {str(e)}"
            logger.error(f"Job {job.job_id} failed: {result.error}")
            
        except Exception as e:
            result.status = ProcessingStatus.FAILED.value
            result.error = str(e)
            logger.error(f"Job {job.job_id} failed: {result.error}")
        
        finally:
            result.processing_time_ms = int((time.time() - start_time) * 1000)
            self._update_status(job.job_id, result.status, result.processing_time_ms)
        
        return result
    
    def _update_status(self, job_id: str, status: str, processing_time: int = None):
        """Update job status in Redis"""
        if self.redis_client:
            try:
                key = f"{config.redis.job_status_prefix}{job_id}"
                data = {"status": status, "updated_at": datetime.utcnow().isoformat()}
                if processing_time:
                    data["processing_time_ms"] = processing_time
                self.redis_client.hset(key, mapping=data)
                self.redis_client.expire(key, config.redis.status_ttl)
            except Exception as e:
                logger.warning(f"Failed to update Redis: {e}")
    
    def _update_database(self, job: ImageJob, result: JobResult):
        """Update image record in database"""
        db = get_db()
        try:
            repo = ImageRepository(db)
            
            # Get or create image record
            image = repo.get_by_url(job.original_url)
            if image:
                repo.update_status(
                    image.id,
                    ProcessingStatus(result.status),
                    enhanced_local_path=result.enhanced_path,
                    enhanced_size_bytes=result.enhanced_size_bytes,
                    original_blur_score=result.quality_before,
                    enhanced_blur_score=result.quality_after,
                    quality_improvement=result.quality_improvement,
                    size_reduction=result.size_reduction,
                    processing_time_ms=result.processing_time_ms,
                    processed_at=datetime.utcnow()
                )
        finally:
            db.close()
    
    def run(self):
        """Start consuming and processing jobs"""
        self.setup()
        self._running = True
        
        logger.info(f"Worker {self.worker_id} started, waiting for jobs...")
        
        # Use the Kafka consumer's consume method with our processor
        self.consumer.consume(
            handler=self.process_job,
            batch_size=config.batch_size
        )
    
    def shutdown(self):
        """Clean shutdown"""
        logger.info(f"Shutting down worker {self.worker_id}")
        self._running = False
        
        if self.consumer:
            self.consumer.close()
        if self.producer:
            self.producer.close()


def main():
    """Entry point for worker"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Image Enhancement Worker')
    parser.add_argument('--worker-id', help='Unique worker identifier')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    worker = ImageWorker(worker_id=args.worker_id)
    
    try:
        worker.run()
    except KeyboardInterrupt:
        pass
    finally:
        worker.shutdown()


if __name__ == "__main__":
    main()
