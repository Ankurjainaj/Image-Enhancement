import io
import os
import time
import uuid
import logging
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Query, Form
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl, Field
import redis

from src.config import get_config, EnhancementMode, ProcessingStatus
from src.database import init_db, get_db, ImageRepository, JobRepository, ImageRecord
from src.enhancer import ImageEnhancer, EnhancementResult
from src.quality import QualityAssessor, QualityReport
from src.kafka_service import KafkaProducerService, ImageJob, create_image_jobs
from src.logging_config import setup_logging

# Initialize logging
setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)
config = get_config()


# Pydantic models for API
class EnhanceUrlRequest(BaseModel):
    """Request to enhance image from URL"""
    url: HttpUrl
    mode: EnhancementMode = EnhancementMode.AUTO
    target_size_kb: Optional[int] = Field(None, ge=50, le=2000)
    output_format: str = Field("JPEG", pattern="^(JPEG|PNG|WEBP)$")
    return_base64: bool = False


class EnhanceResponse(BaseModel):
    """Response from enhancement operation"""
    success: bool
    image_id: str
    original_url: Optional[str] = None
    enhanced_url: Optional[str] = None
    original_size_kb: float
    enhanced_size_kb: float
    size_reduction_percent: float
    quality_before: Optional[float] = None
    quality_after: Optional[float] = None
    quality_improvement: Optional[float] = None
    processing_time_ms: int
    enhancements_applied: List[str]
    dimensions: Dict[str, int]
    error: Optional[str] = None


class BatchJobRequest(BaseModel):
    """Request to create batch processing job"""
    image_urls: List[str]
    mode: EnhancementMode = EnhancementMode.AUTO
    priority: int = Field(5, ge=1, le=10)


class BatchJobResponse(BaseModel):
    """Response from batch job creation"""
    job_id: str
    total_images: int
    queued_count: int
    status: str


class JobStatusResponse(BaseModel):
    """Job status response"""
    job_id: str
    status: str
    total_images: int
    processed_count: int
    success_count: int
    failed_count: int
    progress_percent: float
    avg_processing_time_ms: Optional[float] = None
    estimated_completion: Optional[str] = None


class QualityAssessRequest(BaseModel):
    """Request to assess image quality"""
    url: HttpUrl
    include_brisque: bool = False


class ImportUrlsRequest(BaseModel):
    """Request to import CloudFront URLs"""
    urls: List[str]
    category: Optional[str] = None
    source_type: str = "cloudfront"


class StatsResponse(BaseModel):
    """Statistics response"""
    total_images: int
    processed_images: int
    pending_images: int
    avg_quality_score: Optional[float]
    avg_quality_improvement: Optional[float]
    avg_size_reduction: Optional[float]
    quality_distribution: Dict[str, int]


# Initialize services
enhancer = ImageEnhancer()
assessor = QualityAssessor()
kafka_producer = None
redis_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global kafka_producer, redis_client
    
    # Startup
    logger.info("Starting Image Enhancement API...")
    init_db()
    
    # Initialize Kafka producer
    if config.enable_kafka_pipeline:
        try:
            kafka_producer = KafkaProducerService()
            logger.info("Kafka producer initialized")
        except Exception as e:
            logger.warning(f"Kafka not available: {e}")
    
    # Initialize Redis
    try:
        redis_client = redis.Redis(
            host=config.redis.host,
            port=config.redis.port,
            db=config.redis.db,
            password=config.redis.password,
            decode_responses=True
        )
        redis_client.ping()
        logger.info("Redis connected")
    except Exception as e:
        logger.warning(f"Redis not available: {e}")
        redis_client = None
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    if kafka_producer:
        kafka_producer.close()


# Create FastAPI app
app = FastAPI(
    title="Image Enhancement API",
    description="Real-time image enhancement service for Medikabazaar",
    version="2.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def fetch_image_from_url(url: str, timeout: float = 30.0) -> bytes:
    """Fetch image from URL with validation"""
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(str(url))
        response.raise_for_status()
        
        # Validate content type
        content_type = response.headers.get('content-type', '').lower()
        if not content_type.startswith('image/'):
            raise HTTPException(
                400, 
                f"URL did not return an image. Content-Type: {content_type}. "
                f"This might be an HTML error page or invalid URL."
            )
        
        content = response.content
        
        # Validate minimum size (avoid empty or tiny responses)
        if len(content) < 100:
            raise HTTPException(400, f"Response too small ({len(content)} bytes). Not a valid image.")
        
        # Validate image magic bytes
        magic_bytes = content[:20]
        valid_signatures = [
            b'\xff\xd8\xff',  # JPEG
            b'\x89PNG',        # PNG
            b'GIF87a',         # GIF
            b'GIF89a',         # GIF
            b'RIFF',           # WEBP (starts with RIFF)
            b'BM',             # BMP
            b'II*\x00',        # TIFF (little-endian)
            b'MM\x00*',        # TIFF (big-endian)
        ]
        
        # Check for AVIF (special case - magic bytes are at offset 4-12)
        is_avif = b'ftypavif' in content[:20] or b'ftypavis' in content[:20]
        is_valid = is_avif or any(magic_bytes.startswith(sig) for sig in valid_signatures)
        if not is_valid:
            preview = magic_bytes.decode('utf-8', errors='ignore')[:50]
            raise HTTPException(
                400,
                f"Invalid image data. Content preview: '{preview}'. "
                f"The URL might be returning an error page or non-image content."
            )
        
        return content


def update_job_status(job_id: str, **kwargs):
    """Update job status in Redis and database"""
    if redis_client:
        key = f"{config.redis.job_status_prefix}{job_id}"
        redis_client.hset(key, mapping={k: str(v) for k, v in kwargs.items()})
        redis_client.expire(key, config.redis.status_ttl)
    
    # Also update database
    db = get_db()
    try:
        JobRepository(db).update_progress(job_id, **kwargs)
    finally:
        db.close()


# ==================== API Endpoints ====================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "kafka": kafka_producer is not None,
        "redis": redis_client is not None if redis_client else False
    }


@app.post("/api/v1/enhance/upload", response_model=EnhanceResponse)
async def enhance_upload(
    file: UploadFile = File(...),
    mode: EnhancementMode = Form(EnhancementMode.AUTO),
    target_size_kb: Optional[int] = Form(None),
    output_format: str = Form("JPEG")
):
    """
    Enhance an uploaded image
    
    - Upload image file directly
    - Returns enhanced image as download or base64
    """
    start_time = time.time()
    image_id = str(uuid.uuid4())
    
    # Validate file type
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(400, "Invalid file type. Must be an image.")
    
    try:
        # Read uploaded file
        content = await file.read()
        original_size = len(content)
        
        # Assess quality before
        quality_before = assessor.quick_assess(content)
        
        # Enhance image
        result = enhancer.enhance(
            content,
            mode=mode,
            output_format=output_format,
            target_size_kb=target_size_kb
        )
        
        if not result.success:
            raise HTTPException(500, f"Enhancement failed: {result.error}")
        
        # Assess quality after
        enhanced_bytes = enhancer.get_enhanced_bytes(result, output_format, target_size_kb)
        quality_after = assessor.quick_assess(enhanced_bytes)
        
        # Save to database
        db = get_db()
        try:
            repo = ImageRepository(db)
            repo.create(
                id=image_id,
                original_url=f"upload://{file.filename}",
                original_filename=file.filename,
                original_width=result.original_dimensions[0],
                original_height=result.original_dimensions[1],
                original_size_bytes=original_size,
                enhanced_width=result.enhanced_dimensions[0],
                enhanced_height=result.enhanced_dimensions[1],
                enhanced_size_bytes=len(enhanced_bytes),
                original_quality_score=quality_before.get('blur_score'),
                status=ProcessingStatus.COMPLETED.value,
                processing_time_ms=result.processing_time_ms,
                enhancement_mode=mode.value
            )
        finally:
            db.close()
        
        processing_time = int((time.time() - start_time) * 1000)
        
        return EnhanceResponse(
            success=True,
            image_id=image_id,
            original_url=f"upload://{file.filename}",
            original_size_kb=round(original_size / 1024, 2),
            enhanced_size_kb=round(len(enhanced_bytes) / 1024, 2),
            size_reduction_percent=result.size_reduction_percent,
            quality_before=quality_before.get('blur_score'),
            quality_after=quality_after.get('blur_score'),
            processing_time_ms=processing_time,
            enhancements_applied=result.enhancements_applied,
            dimensions={
                "original_width": result.original_dimensions[0],
                "original_height": result.original_dimensions[1],
                "enhanced_width": result.enhanced_dimensions[0],
                "enhanced_height": result.enhanced_dimensions[1]
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Enhancement failed: {e}")
        raise HTTPException(500, str(e))


@app.post("/api/v1/enhance/url", response_model=EnhanceResponse)
async def enhance_url(request: EnhanceUrlRequest):
    """
    Enhance image from URL
    
    - Fetches image from provided URL
    - Returns enhancement results and optionally the enhanced image
    """
    start_time = time.time()
    image_id = str(uuid.uuid4())
    
    logger.info("=" * 80)
    logger.info(f"📥 API REQUEST | enhance/url | ID: {image_id}")
    logger.info(f"   URL: {request.url}")
    logger.info(f"   Mode: {request.mode.value}")
    logger.info(f"   Target Size: {request.target_size_kb}KB")
    logger.info(f"   Format: {request.output_format}")
    logger.info("-" * 80)
    
    try:
        # Fetch image
        logger.info(f"🌐 Fetching image from URL...")
        content = await fetch_image_from_url(str(request.url))
        original_size = len(content)
        logger.info(f"   ✅ Downloaded: {original_size/1024:.1f}KB")
        
        # Assess quality before
        quality_before = assessor.quick_assess(content)
        
        # Enhance image
        result = enhancer.enhance(
            content,
            mode=request.mode,
            output_format=request.output_format,
            target_size_kb=request.target_size_kb
        )
        
        if not result.success:
            raise HTTPException(500, f"Enhancement failed: {result.error}")
        
        # Get enhanced bytes
        enhanced_bytes = enhancer.get_enhanced_bytes(
            result, 
            request.output_format, 
            request.target_size_kb
        )
        
        # Assess quality after
        quality_after = assessor.quick_assess(enhanced_bytes)
        
        # Save to local storage
        storage_path = config.storage.local_storage_path / f"{image_id}.{request.output_format.lower()}"
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(storage_path, 'wb') as f:
            f.write(enhanced_bytes)
        
        # Calculate quality improvement
        blur_before = quality_before.get('blur_score', 0)
        blur_after = quality_after.get('blur_score', 0)
        improvement = ((blur_after - blur_before) / max(blur_before, 1)) * 100 if blur_before else None
        
        # Save to database
        db = get_db()
        try:
            repo = ImageRepository(db)
            repo.create(
                id=image_id,
                original_url=str(request.url),
                original_width=result.original_dimensions[0],
                original_height=result.original_dimensions[1],
                original_size_bytes=original_size,
                enhanced_local_path=str(storage_path),
                enhanced_width=result.enhanced_dimensions[0],
                enhanced_height=result.enhanced_dimensions[1],
                enhanced_size_bytes=len(enhanced_bytes),
                original_blur_score=blur_before,
                enhanced_blur_score=blur_after,
                quality_improvement=improvement,
                size_reduction=result.size_reduction_percent,
                status=ProcessingStatus.COMPLETED.value,
                processing_time_ms=result.processing_time_ms,
                enhancement_mode=request.mode.value
            )
        finally:
            db.close()
        
        processing_time = int((time.time() - start_time) * 1000)
        
        return EnhanceResponse(
            success=True,
            image_id=image_id,
            original_url=str(request.url),
            enhanced_url=f"/api/v1/images/{image_id}/enhanced",
            original_size_kb=round(original_size / 1024, 2),
            enhanced_size_kb=round(len(enhanced_bytes) / 1024, 2),
            size_reduction_percent=result.size_reduction_percent,
            quality_before=blur_before,
            quality_after=blur_after,
            quality_improvement=improvement,
            processing_time_ms=processing_time,
            enhancements_applied=result.enhancements_applied,
            dimensions={
                "original_width": result.original_dimensions[0],
                "original_height": result.original_dimensions[1],
                "enhanced_width": result.enhanced_dimensions[0],
                "enhanced_height": result.enhanced_dimensions[1]
            }
        )
        
    except httpx.HTTPError as e:
        raise HTTPException(400, f"Failed to fetch image from URL: {e}")
    except Exception as e:
        logger.error(f"Enhancement failed: {e}")
        raise HTTPException(500, str(e))


@app.get("/api/v1/images/{image_id}/enhanced")
async def get_enhanced_image(image_id: str):
    """Download enhanced image"""
    db = get_db()
    try:
        repo = ImageRepository(db)
        image = repo.get_by_id(image_id)
        
        if not image:
            raise HTTPException(404, "Image not found")
        
        if not image.enhanced_local_path:
            raise HTTPException(404, "Enhanced image not available")
        
        path = Path(image.enhanced_local_path)
        if not path.exists():
            raise HTTPException(404, "Enhanced image file not found")
        
        # Determine content type
        ext = path.suffix.lower()
        content_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.webp': 'image/webp'
        }
        content_type = content_types.get(ext, 'image/jpeg')
        
        return StreamingResponse(
            open(path, 'rb'),
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename={image_id}{ext}"
            }
        )
    finally:
        db.close()


@app.post("/api/v1/assess", response_model=Dict[str, Any])
async def assess_quality(request: QualityAssessRequest):
    """Assess image quality from URL"""
    try:
        content = await fetch_image_from_url(str(request.url))
        
        if request.include_brisque:
            report = assessor.assess(content, include_brisque=True)
            return report.to_dict()
        else:
            return assessor.quick_assess(content)
            
    except httpx.HTTPError as e:
        raise HTTPException(400, f"Failed to fetch image: {e}")
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/v1/batch", response_model=BatchJobResponse)
async def create_batch_job(
    request: BatchJobRequest,
    background_tasks: BackgroundTasks
):
    """
    Create a batch enhancement job
    
    - Queues images for processing via Kafka
    - Returns job ID for tracking
    """
    if not kafka_producer:
        raise HTTPException(503, "Kafka not available. Batch processing disabled.")
    
    job_id = str(uuid.uuid4())
    
    # Create database job record
    db = get_db()
    try:
        job_repo = JobRepository(db)
        job_repo.create(
            id=job_id,
            job_type="batch",
            enhancement_mode=request.mode.value,
            priority=request.priority,
            total_images=len(request.image_urls),
            status=ProcessingStatus.QUEUED.value
        )
        
        # Create image records
        image_repo = ImageRepository(db)
        for url in request.image_urls:
            image_repo.create(
                original_url=url,
                status=ProcessingStatus.QUEUED.value
            )
    finally:
        db.close()
    
    # Create and queue Kafka jobs
    jobs = create_image_jobs(
        [{"url": url, "id": str(uuid.uuid4())} for url in request.image_urls],
        enhancement_mode=request.mode.value
    )
    
    queued = kafka_producer.publish_batch(jobs)
    
    # Update job status in Redis
    if redis_client:
        redis_client.hset(
            f"{config.redis.job_status_prefix}{job_id}",
            mapping={
                "status": ProcessingStatus.QUEUED.value,
                "total": len(request.image_urls),
                "queued": queued,
                "processed": 0
            }
        )
    
    return BatchJobResponse(
        job_id=job_id,
        total_images=len(request.image_urls),
        queued_count=queued,
        status=ProcessingStatus.QUEUED.value
    )


@app.get("/api/v1/batch/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Get batch job status"""
    # Try Redis first (faster)
    if redis_client:
        key = f"{config.redis.job_status_prefix}{job_id}"
        data = redis_client.hgetall(key)
        if data:
            return JobStatusResponse(
                job_id=job_id,
                status=data.get('status', 'unknown'),
                total_images=int(data.get('total', 0)),
                processed_count=int(data.get('processed', 0)),
                success_count=int(data.get('success', 0)),
                failed_count=int(data.get('failed', 0)),
                progress_percent=float(data.get('progress', 0)),
                avg_processing_time_ms=float(data.get('avg_time')) if data.get('avg_time') else None
            )
    
    # Fallback to database
    db = get_db()
    try:
        job = JobRepository(db).get_by_id(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        
        return JobStatusResponse(
            job_id=job_id,
            status=job.status,
            total_images=job.total_images,
            processed_count=job.processed_count,
            success_count=job.success_count,
            failed_count=job.failed_count,
            progress_percent=job.progress_percentage,
            avg_processing_time_ms=job.avg_processing_time_ms
        )
    finally:
        db.close()


@app.post("/api/v1/import", response_model=Dict[str, Any])
async def import_cloudfront_urls(request: ImportUrlsRequest):
    """
    Import CloudFront URLs into database for batch processing
    
    - Accepts list of image URLs
    - Stores in database for later processing
    """
    db = get_db()
    try:
        repo = ImageRepository(db)
        
        images_data = [
            {
                "original_url": url,
                "cloudfront_url": url,
                "source_type": request.source_type,
                "category": request.category,
                "status": ProcessingStatus.PENDING.value
            }
            for url in request.urls
        ]
        
        created = repo.bulk_create(images_data)
        
        return {
            "success": True,
            "total_submitted": len(request.urls),
            "imported": created,
            "skipped": len(request.urls) - created,
            "message": f"Imported {created} new images"
        }
    finally:
        db.close()


@app.get("/api/v1/stats", response_model=StatsResponse)
async def get_statistics():
    """Get overall statistics"""
    db = get_db()
    try:
        stats = ImageRepository(db).get_statistics()
        
        return StatsResponse(
            total_images=stats['total_images'],
            processed_images=stats['status_counts'].get('completed', 0),
            pending_images=stats['status_counts'].get('pending', 0),
            avg_quality_score=stats['avg_quality_score'],
            avg_quality_improvement=stats['avg_quality_improvement'],
            avg_size_reduction=stats['avg_size_reduction'],
            quality_distribution=stats['quality_distribution']
        )
    finally:
        db.close()


@app.get("/api/v1/images")
async def list_images(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """List images with optional filtering"""
    db = get_db()
    try:
        query = db.query(ImageRecord)
        
        if status:
            query = query.filter(ImageRecord.status == status)
        
        total = query.count()
        images = query.offset(offset).limit(limit).all()
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "images": [img.to_dict() for img in images]
        }
    finally:
        db.close()


# Run with: uvicorn src.api:app --reload --port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api:app",
        host=config.api.host,
        port=config.api.port,
        reload=True
    )
