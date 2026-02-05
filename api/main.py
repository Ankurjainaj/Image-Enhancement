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
from src.database import init_db, get_db, ImageRepository, JobRepository, ImageRecord, EnhancementHistoryRepository
from src.enhancer import ImageEnhancer, EnhancementResult
from src.quality import QualityAssessor, QualityReport
from src.kafka_service import KafkaProducerService, ImageJob, create_image_jobs
from src.logging_config import setup_logging
from src.gemini_service import GeminiService
from src.s3_service import S3Service

import boto3
from urllib.parse import urlparse
from botocore.exceptions import ClientError

# Initialize logging
setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)
config = get_config()

class CDNUpdateResponse(BaseModel):
    success: bool
    bucket: str
    key: str
    url: str
    cache_control: str
    message: str

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
    database_id: Optional[str] = None
    original_url: Optional[str] = None
    enhanced_url: Optional[str] = None
    original_size_kb: float
    enhanced_size_kb: float
    size_reduction_percent: float
    quality_before: Optional[float] = None
    quality_after: Optional[float] = None
    quality_improvement: Optional[float] = None
    processing_time_ms: int
    enhancement_mode: Optional[str] = None
    enhancements_applied: List[str] = []
    dimensions: Dict[str, int] = {}
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


class GeminiEnhanceRequest(BaseModel):
    """Request to enhance image using Gemini API"""
    enhancement_prompt: Optional[str] = Field(
        None,
        description="Custom prompt for Gemini enhancement. If not provided, uses default quality enhancement prompt"
    )


class GeminiEnhanceResponse(BaseModel):
    """Response from Gemini enhancement"""
    success: bool
    enhanced_image_base64: Optional[str] = None
    processing_time_ms: int
    model_version: Optional[str] = None
    response_id: Optional[str] = None
    usage_metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


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
s3_service = None
kafka_producer = None
redis_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global kafka_producer, redis_client
    
    # Startup
    logger.info("=" * 60)
    logger.info("🚀 Starting Image Enhancement API...")
    logger.info("=" * 60)
    
    init_db()
    logger.info("✅ Database initialized")
    
    # Initialize S3 Service
    global s3_service
    try:
        s3_service = S3Service(
            bucket=config.storage.s3_bucket,
            region=config.storage.s3_region,
            endpoint_url=config.storage.s3_endpoint if config.storage.s3_endpoint else None,
            access_key=config.storage.s3_access_key,
            secret_key=config.storage.s3_secret_key
        )
        if s3_service.is_available():
            logger.info(f"✅ S3 Storage available: {config.storage.s3_bucket}")
    except Exception as e:
        logger.warning(f"⚠️ S3 Storage validation failed: {e}")
    
    # Initialize Kafka producer
    if config.enable_kafka_pipeline:
        try:
            kafka_producer = KafkaProducerService()
            logger.info("✅ Kafka producer initialized")
        except Exception as e:
            logger.warning(f"⚠️ Kafka not available: {e}")
    
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
        logger.info("✅ Redis connected")
    except Exception as e:
        logger.warning(f"⚠️ Redis not available: {e}")
        redis_client = None
    
    logger.info("=" * 60)
    logger.info("🎉 API Ready!")
    logger.info("=" * 60)
    
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
        "services": {
            "kafka": kafka_producer is not None,
            "redis": redis_client is not None if redis_client else False,
            "s3": s3_service.is_available() if s3_service else False,
            "bedrock": config.hybrid.enable_bedrock
        },
        "config": {
            "s3_bucket": config.storage.s3_bucket,
            "s3_region": config.storage.s3_region,
            "bedrock_region": config.hybrid.bedrock_region
        }
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
    
    - Upload image file to S3
    - Save record with URLs to database
    - Returns enhanced image as download or base64
    """
    start_time = time.time()
    image_id = str(uuid.uuid4())
    
    logger.info("=" * 80)
    logger.info(f"📥 API REQUEST | enhance/upload | ID: {image_id}")
    logger.info(f"   Filename: {file.filename}")
    logger.info(f"   Mode: {mode.value}")
    logger.info(f"   Target Size: {target_size_kb}KB")
    logger.info(f"   Format: {output_format}")
    logger.info("-" * 80)
    db = None
    
    # Validate file type
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(400, "Invalid file type. Must be an image.")
    
    try:
        # Read uploaded file
        content = await file.read()
        original_size = len(content)
        logger.info(f"   📦 Original size: {original_size/1024:.1f}KB")
        mime_type = file.content_type
        
        logger.info(f"[UPLOAD] File received: {file.filename}, size: {original_size} bytes")
        
        db = get_db()
        image_repo = ImageRepository(db)
        
        # Upload original image to S3
        original_key = f"uploads/original/{image_id}_{file.filename}"
        original_s3_url = s3_service.upload_image(
            content,
            original_key,
            mime_type,
            metadata={
                "filename": file.filename,
                "source": "upload",
                "type": "original"
            }
        )
        original_https_url = s3_service.get_https_url(original_key, cloudfront_domain=None)
        logger.info(f"[UPLOAD] Original uploaded to S3: {original_key}")
        
        # Assess quality before
        quality_before = assessor.quick_assess(content)
        logger.info(f"   📊 Original quality - Blur: {quality_before.get('blur_score', 0):.1f}")
        
        # Enhance image
        logger.info(f"   ⚙️ Enhancing...")
        result = enhancer.enhance(
            content,
            mode=mode,
            output_format=output_format,
            target_size_kb=target_size_kb
        )
        
        if not result.success:
            raise HTTPException(500, f"Enhancement failed: {result.error}")
        
        # Get enhanced bytes
        enhanced_bytes = enhancer.get_enhanced_bytes(result, output_format, target_size_kb)
        logger.info(f"   ✅ Enhanced size: {len(enhanced_bytes)/1024:.1f}KB")
        
        # Assess quality after
        quality_after = assessor.quick_assess(enhanced_bytes)
        logger.info(f"   📊 Enhanced quality - Blur: {quality_after.get('blur_score', 0):.1f}")
        # Upload enhanced image to S3
        enhanced_key = f"uploads/enhanced/{image_id}_{file.filename}"
        enhanced_s3_url = s3_service.upload_image(
            enhanced_bytes,
            enhanced_key,
            mime_type,
            metadata={
                "filename": file.filename,
                "source": "upload",
                "type": "enhanced",
                "mode": mode.value
            }
        )
        enhanced_https_url = s3_service.get_https_url(enhanced_key, cloudfront_domain=None)
        logger.info(f"[UPLOAD] Enhanced uploaded to S3: {enhanced_key}")

        # Calculate quality improvement
        blur_before = quality_before.get('blur_score', 0)
        blur_after = quality_after.get('blur_score', 0)
        improvement = ((blur_after - blur_before) / max(blur_before, 1)) * 100 if blur_before else None
        
        # Save to database with S3 URLs
        product_image = image_repo.create(
            sku_id=f"upload_{image_id}",
            image_url=original_https_url,
            enhanced_image_url=enhanced_https_url,
            original_filename=file.filename,
            original_width=result.original_dimensions[0],
            original_height=result.original_dimensions[1],
            original_size_bytes=original_size,
            enhanced_width=result.enhanced_dimensions[0],
            enhanced_height=result.enhanced_dimensions[1],
            enhanced_size_bytes=len(enhanced_bytes),
            original_format=mime_type.split('/')[-1].upper(),
            enhanced_format=output_format,
            status=ProcessingStatus.COMPLETED.value,
            processing_time_ms=result.processing_time_ms,
            enhancement_mode=mode.value,
            processed_at=datetime.utcnow(),
            enhancements_applied=result.enhancements_applied if hasattr(result, 'enhancements_applied') else None
        )
        logger.info(f"[UPLOAD] Database record created: {product_image.id}")
        
        # Create enhancement history record
        history_repo = EnhancementHistoryRepository(db)
        history = history_repo.create(
            product_image_id=product_image.id,
            enhancement_sequence=1,
            enhancement_mode=mode.value,
            original_s3_url=original_s3_url,
            original_https_url=original_https_url,
            enhanced_s3_url=enhanced_s3_url,
            enhanced_https_url=enhanced_https_url,
            original_size_bytes=original_size,
            enhanced_size_bytes=len(enhanced_bytes),
            original_quality_score=quality_before.get('blur', 0),
            enhanced_quality_score=quality_after.get('blur', 0),
            quality_metadata={
                "original_blur": quality_before.get('blur', 0),
                "enhanced_blur": quality_after.get('blur', 0),
                "improvement_percent": (
                    ((quality_after.get('blur', 0) - quality_before.get('blur', 0)) / 
                     max(quality_before.get('blur', 1), 1)) * 100
                ) if quality_before.get('blur', 0) > 0 else 0
            },
            size_metadata={
                "original_size_kb": original_size / 1024,
                "enhanced_size_kb": len(enhanced_bytes) / 1024,
                "reduction_percent": (
                    ((original_size - len(enhanced_bytes)) / original_size * 100) if original_size > 0 else 0
                )
            },
            processing_time_ms=int((time.time() - start_time) * 1000),
            processing_status="completed"
        )
        logger.info(f"[UPLOAD] Enhancement history created: {history.id}")
        
        processing_time = int((time.time() - start_time) * 1000)
        
        logger.info("=" * 80)
        logger.info(f"✅ ENHANCEMENT COMPLETE | ID: {image_id}")
        logger.info(f"   Total time: {processing_time}ms")
        logger.info(f"   Size reduction: {result.size_reduction_percent:.1f}%")
        logger.info(f"   Quality improvement: {improvement:.1f}%" if improvement else "   Quality: N/A")
        logger.info("=" * 80)
        
        return EnhanceResponse(
            success=True,
            image_id=product_image.id,
            original_url=original_https_url,
            enhanced_url=enhanced_https_url,
            original_size_kb=round(original_size / 1024, 2),
            enhanced_size_kb=round(len(enhanced_bytes) / 1024, 2),
            size_reduction_percent=result.size_reduction_percent,
            quality_before=quality_before.get('blur'),
            quality_after=quality_after.get('blur'),
            processing_time_ms=processing_time,
            enhancement_mode=mode.value,
            database_id=product_image.id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[UPLOAD] Enhancement failed: {e}", exc_info=True)
        if db:
            try:
                db.close()
            except:
                pass
        raise HTTPException(500, str(e))
    finally:
        if db:
            try:
                db.close()
            except:
                pass


@app.post("/api/v1/enhance/url", response_model=EnhanceResponse)
async def enhance_url(request: EnhanceUrlRequest):
    """
    Enhance image from URL
    
    - Fetches image from provided URL
    - Uploads to S3 (original & enhanced)
    - Saves records to database
    - Returns URLs and database ID
    """
    start_time = time.time()
    image_id = str(uuid.uuid4())
    db = None
    
    logger.info("=" * 80)
    logger.info(f"📥 API REQUEST | enhance/url | ID: {image_id}")
    logger.info(f"   URL: {request.url}")
    logger.info(f"   Mode: {request.mode.value}")
    logger.info("-" * 80)
    
    try:
        # Fetch image from URL
        logger.info(f"🌐 Fetching image from URL...")
        content = await fetch_image_from_url(str(request.url))
        original_size = len(content)
        logger.info(f"   ✅ Downloaded: {original_size/1024:.1f}KB")
        
        # Extract filename from URL
        filename = str(request.url).split('/')[-1] or f"image_{image_id}.jpg"
        mime_type = "image/jpeg"  # Default
        
        # Assess quality before
        quality_before = assessor.quick_assess(content)
        logger.info(f"   📊 Original quality - Blur: {quality_before.get('blur_score', 0):.1f}")
        
        # Enhance image
        logger.info(f"   ⚙️ Enhancing...")
        result = enhancer.enhance(
            content,
            mode=request.mode,
            output_format=request.output_format,
            target_size_kb=request.target_size_kb
        )
        
        if not result.success:
            raise HTTPException(500, f"Enhancement failed: {result.error}")
        
        # Get enhanced bytes - THIS IS CRITICAL: must get bytes from result
        enhanced_bytes = enhancer.get_enhanced_bytes(
            result, 
            request.output_format, 
            request.target_size_kb
        )
        logger.info(f"   ✅ Enhanced size: {len(enhanced_bytes)/1024:.1f}KB")
        
        # Assess quality after
        quality_after = assessor.quick_assess(enhanced_bytes)
        

        
        db = get_db()
        image_repo = ImageRepository(db)
        
        # Upload original image to S3
        original_key = f"uploads/original/{image_id}_{filename}"
        original_s3_url = s3_service.upload_image(
            content,
            original_key,
            mime_type,
            metadata={
                "filename": filename,
                "source": "url",
                "type": "original",
                "original_url": str(request.url)
            }
        )
        original_https_url = s3_service.get_https_url(original_key, cloudfront_domain=None)
        logger.info(f"[URL-ENHANCE] Original uploaded to S3: {original_key}")
        
        # Upload enhanced image to S3
        enhanced_key = f"uploads/enhanced/{image_id}_{filename}"
        enhanced_s3_url = s3_service.upload_image(
            enhanced_bytes,
            enhanced_key,
            mime_type,
            metadata={
                "filename": filename,
                "source": "url",
                "type": "enhanced",
                "mode": request.mode.value
            }
        )
        enhanced_https_url = s3_service.get_https_url(enhanced_key, cloudfront_domain=None)
        logger.info(f"[URL-ENHANCE] Enhanced uploaded to S3: {enhanced_key}")
        
        # Save to database with S3 URLs
        product_image = image_repo.create(
            sku_id=f"url_{image_id}",
            image_url=original_https_url,
            enhanced_image_url=enhanced_https_url,
            original_filename=filename,
            original_width=result.original_dimensions[0],
            original_height=result.original_dimensions[1],
            original_size_bytes=original_size,
            enhanced_width=result.enhanced_dimensions[0],
            enhanced_height=result.enhanced_dimensions[1],
            enhanced_size_bytes=len(enhanced_bytes),
            original_format=mime_type.split('/')[-1].upper(),
            enhanced_format=request.output_format,
            status=ProcessingStatus.COMPLETED.value,
            processing_time_ms=result.processing_time_ms,
            enhancement_mode=request.mode.value,
            processed_at=datetime.utcnow(),
            enhancements_applied=result.enhancements_applied if hasattr(result, 'enhancements_applied') else None
        )
        logger.info(f"[URL-ENHANCE] Database record created: {product_image.id}")
        
        # Create enhancement history record
        history_repo = EnhancementHistoryRepository(db)
        history = history_repo.create(
            product_image_id=product_image.id,
            enhancement_sequence=1,
            enhancement_mode=request.mode.value,
            original_s3_url=original_s3_url,
            original_https_url=original_https_url,
            enhanced_s3_url=enhanced_s3_url,
            enhanced_https_url=enhanced_https_url,
            original_size_bytes=original_size,
            enhanced_size_bytes=len(enhanced_bytes),
            original_quality_score=quality_before.get('blur', 0),
            enhanced_quality_score=quality_after.get('blur', 0),
            quality_metadata={
                "original_blur": quality_before.get('blur', 0),
                "enhanced_blur": quality_after.get('blur', 0),
                "improvement_percent": (
                    ((quality_after.get('blur', 0) - quality_before.get('blur', 0)) / 
                     max(quality_before.get('blur', 1), 1)) * 100
                ) if quality_before.get('blur', 0) > 0 else 0
            },
            size_metadata={
                "original_size_kb": original_size / 1024,
                "enhanced_size_kb": len(enhanced_bytes) / 1024,
                "reduction_percent": (
                    ((original_size - len(enhanced_bytes)) / original_size * 100) if original_size > 0 else 0
                )
            },
            processing_time_ms=int((time.time() - start_time) * 1000),
            processing_status="completed"
        )
        logger.info(f"[URL-ENHANCE] Enhancement history created: {history.id}")
        
        processing_time = int((time.time() - start_time) * 1000)
        
        logger.info("=" * 80)
        logger.info(f"✅ ENHANCEMENT COMPLETE | ID: {image_id}")
        logger.info(f"   Total time: {processing_time}ms")
        logger.info(f"   Size reduction: {result.size_reduction_percent:.1f}%")
        logger.info(f"   Quality improvement: {improvement:.1f}%" if improvement else "   Quality: N/A")
        logger.info("=" * 80)
        
        return EnhanceResponse(
            image_id=product_image.id,
            database_id=product_image.id,
            original_url=original_https_url,
            enhanced_url=enhanced_https_url,
            original_size_kb=round(original_size / 1024, 2),
            enhanced_size_kb=round(len(enhanced_bytes) / 1024, 2),
            size_reduction_percent=result.size_reduction_percent,
            quality_before=quality_before.get('blur'),
            quality_after=quality_after.get('blur'),
            processing_time_ms=processing_time,
            enhancement_mode=request.mode.value
        )
    except HTTPException:
        logger.error(f"❌ Failed to fetch image: {e}")
        raise
    except Exception as e:
        logger.error(f"[URL-ENHANCE] Enhancement failed: {e}", exc_info=True)
        if db:
            try:
                db.close()
            except:
                pass
        raise HTTPException(500, str(e))
    finally:
        if db:
            try:
                db.close()
            except:
                pass


@app.get("/api/v1/images/{image_id}/enhanced")
async def get_enhanced_image(image_id: str):
    """Download enhanced image"""
    db = get_db()
    try:
        repo = ImageRepository(db)
        image = repo.get_by_id(image_id)
        
        if not image:
            raise HTTPException(404, "Image not found")
        
        # If we have an S3 URL, redirect to it
        if image.enhanced_image_url:
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url=image.enhanced_image_url)
        
        # Fallback to local path
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


class EnhancementHistoryItem(BaseModel):
    """Enhancement history item in response"""
    id: int
    enhancement_sequence: int
    enhancement_mode: str
    enhanced_https_url: str
    enhanced_s3_url: str
    quality_metadata: Dict[str, Any]
    size_metadata: Dict[str, Any]
    model_version: str
    processing_time_ms: int
    created_at: datetime


class EnhancementHistoryResponse(BaseModel):
    """Response with enhancement history for an image"""
    image_id: int
    filename: str
    original_https_url: str
    enhancements: List[EnhancementHistoryItem]
    total_enhancements: int


@app.get("/api/v1/images/{image_id}/enhancement-history", response_model=EnhancementHistoryResponse)
async def get_enhancement_history(image_id: int):
    """Get complete enhancement history for an image with all metadata"""
    db = get_db()
    try:
        image_repo = ImageRepository(db)
        history_repo = EnhancementHistoryRepository(db)
        
        image = image_repo.get_by_id(str(image_id))
        if not image:
            raise HTTPException(404, "Image not found")
        
        enhancements = history_repo.get_by_product_image_id(image_id)
        
        enhancement_items = [
            EnhancementHistoryItem(
                id=e.id,
                enhancement_sequence=e.enhancement_sequence,
                enhancement_mode=e.enhancement_mode,
                enhanced_https_url=e.enhanced_https_url,
                enhanced_s3_url=e.enhanced_s3_url,
                quality_metadata=e.quality_metadata,
                size_metadata=e.size_metadata,
                model_version=e.model_version,
                processing_time_ms=e.processing_time_ms,
                created_at=e.created_at
            )
            for e in enhancements
        ]
        
        return EnhancementHistoryResponse(
            image_id=image_id,
            filename=image.filename,
            original_https_url=image.https_url or image.s3_url,
            enhancements=enhancement_items,
            total_enhancements=len(enhancement_items)
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


@app.post("/api/v1/enhance/gemini", response_model=GeminiEnhanceResponse)
async def enhance_gemini(
    file: UploadFile = File(...),
    enhancement_prompt: Optional[str] = Form(None)
):
    """
    Enhance an uploaded image using Google Gemini API
    
    - Upload image file to S3
    - Gemini will process and enhance the image based on the prompt
    - Store enhanced image to S3
    - Track enhancement in audit trail with metadata
    """
    if not config.api.enable_gemini:
        raise HTTPException(
            503,
            "Gemini API is not enabled. Please set GEMINI_API_KEY environment variable."
        )
    
    start_time = time.time()
    db = None
    
    # Validate file type
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(400, "Invalid file type. Must be an image.")
    
    try:
        # Read uploaded file
        content = await file.read()
        
        db = get_db()
        
        # Check S3 configuration
        if not config.storage.s3_bucket:
            logger.warning("[GEMINI] S3 bucket not configured, skipping S3 upload")
            raise HTTPException(503, "S3 storage not configured. Set S3_BUCKET environment variable.")
        
        # Initialize services
        s3_service = S3Service(
            bucket=config.storage.s3_bucket,
            region=config.storage.s3_region,
            endpoint_url=config.storage.s3_endpoint if config.storage.s3_endpoint else None,
            access_key=config.storage.s3_access_key,
            secret_key=config.storage.s3_secret_key
        )
        gemini_service = GeminiService(config.api.gemini_api_key)
        
        logger.info(f"[GEMINI] Services initialized successfully")
        
        # Generate S3 keys
        original_key = f"originals/{uuid.uuid4()}_{file.filename}"
        enhanced_key = f"enhanced/{uuid.uuid4()}_{file.filename}"
        
        # Get file size and type
        file_size_kb = len(content) / 1024
        mime_type = file.content_type
        
        # Upload original to S3
        original_s3_url = s3_service.upload_image(
            content,
            original_key,
            mime_type,
            metadata={
                "filename": file.filename,
                "source": "upload",
                "type": "original"
            }
        )
        original_https_url = s3_service.get_https_url(original_key, config.storage.cloudfront_domain)
        
        # Enhance using Gemini
        result = gemini_service.enhance_image(content, enhancement_prompt=enhancement_prompt)
        
        if not result.success:
            raise HTTPException(500, f"Gemini enhancement failed: {result.error}")
        
        # Decode enhanced image from base64
        enhanced_image_bytes = result.get_image_bytes()
        enhanced_size_kb = len(enhanced_image_bytes) / 1024
        
        # Upload enhanced to S3
        enhanced_s3_url = s3_service.upload_image(
            enhanced_image_bytes,
            enhanced_key,
            mime_type,
            metadata={
                "filename": file.filename,
                "source": "gemini",
                "type": "enhanced",
                "original_key": original_key,
                "model": result.model_version
            }
        )
        enhanced_https_url = s3_service.get_https_url(enhanced_key, config.storage.cloudfront_domain)
        
        processing_time = int((time.time() - start_time) * 1000)
        
        # Assess quality of both images
        quality_assessor = QualityAssessor()
        original_quality = quality_assessor.quick_assess(content)
        enhanced_quality = quality_assessor.quick_assess(enhanced_image_bytes)
        
        # Create or get product image record
        image_repo = ImageRepository(db)
        logger.info("[GEMINI] Creating product image record...")
        product_image = image_repo.create(
            sku_id=f"upload_{uuid.uuid4()}",
            image_url=original_https_url,
            enhanced_image_url=enhanced_https_url,
            original_filename=file.filename,
            original_size_bytes=len(content),
            enhanced_size_bytes=len(enhanced_image_bytes),
            original_format=mime_type.split('/')[-1].upper(),
            enhanced_format=mime_type.split('/')[-1].upper(),
            enhancement_mode="gemini",
            status=ProcessingStatus.COMPLETED.value,
            processed_at=datetime.utcnow(),
            processing_time_ms=processing_time
        )
        logger.info(f"[GEMINI] Product image created with ID: {product_image.id}")
        
        # Get enhancement sequence number
        history_repo = EnhancementHistoryRepository(db)
        latest = history_repo.get_latest_enhancement(product_image.id)
        sequence = (latest.enhancement_sequence + 1) if latest else 1
        
        # Store enhancement history with metadata
        quality_metadata = {
            "original_blur": original_quality.get('blur', 0),
            "enhanced_blur": enhanced_quality.get('blur', 0),
            "improvement_percent": (
                ((enhanced_quality.get('blur', 0) - original_quality.get('blur', 0)) / 
                 max(original_quality.get('blur', 1), 1)) * 100
            ) if original_quality.get('blur', 0) > 0 else 0
        }
        
        size_metadata = {
            "original_size_kb": file_size_kb,
            "enhanced_size_kb": enhanced_size_kb,
            "reduction_percent": (
                ((file_size_kb - enhanced_size_kb) / file_size_kb * 100) if file_size_kb > 0 else 0
            )
        }
        
        enhancement_history = history_repo.create(
            product_image_id=product_image.id,
            enhancement_sequence=sequence,
            enhancement_mode="gemini",
            original_s3_url=original_s3_url,
            original_https_url=original_https_url,
            enhanced_s3_url=enhanced_s3_url,
            enhanced_https_url=enhanced_https_url,
            quality_metadata=quality_metadata,
            size_metadata=size_metadata,
            model_version=result.model_version,
            response_id=result.response_id,
            processing_time_ms=processing_time,
            processing_status="completed"
        )
        logger.info(f"[GEMINI] Enhancement history created with ID: {enhancement_history.id}")
        
        return GeminiEnhanceResponse(
            success=True,
            enhanced_image_base64=result.enhanced_image_base64,
            processing_time_ms=processing_time,
            model_version=result.model_version,
            response_id=result.response_id,
            usage_metadata=result.usage_metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Gemini enhancement failed: {e}", exc_info=True)
        db.close() if db else None
        raise HTTPException(500, str(e))
    finally:
        if db:
            try:
                db.close()
            except:
                pass



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
                image_url=url,
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
                "image_url": url,
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
            avg_quality_score=stats.get('avg_quality_score'),
            avg_quality_improvement=stats.get('avg_quality_improvement'),
            avg_size_reduction=stats.get('avg_size_reduction'),
            quality_distribution=stats.get('quality_distribution', {})
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

@app.post("/api/v1/tools/update-cdn-image", response_model=CDNUpdateResponse)
async def update_cdn_image(
    file: UploadFile = File(...),
    target_url: str = Form(..., description="The full S3/CDN URL to overwrite")
):
    """
    Overwrite an existing S3 image and update Cache-Control headers.
    Target Bucket: catalystproduction-innew
    Cache-Control: max-age=120 (2 minutes)
    """
    TARGET_BUCKET = config.storage.catalyst_bucket
    
    # 1. Parse the Key from the URL
    try:
        parsed_url = urlparse(target_url)
        # Remove the leading slash from the path to get the S3 Key
        # Ex: /media/public/image.jpg -> media/public/image.jpg
        object_key = parsed_url.path.lstrip('/')
        
        if not object_key:
            raise HTTPException(400, "Could not extract valid object key from URL")
            
        logger.info(f"🔄 CDN Update Request for Key: {object_key}")
    except Exception as e:
        raise HTTPException(400, f"Invalid URL format: {str(e)}")

    # 2. Validate File
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(400, "Invalid file type. Must be an image.")

    try:
        content = await file.read()
        aws_access = config.storage.catalyst_s3_access_key
        aws_secret = config.storage.catalyst_s3_secret_key
        
        # 3. Upload with specific Cache-Control
        # We access the boto3 client directly to pass specific ExtraArgs
        # If s3_service is initialized, we use its client, otherwise we use config
        
        if aws_access and aws_secret and "placeholder" not in aws_access:
            logger.info("🔑 Using credentials from Config/Env")
            s3_client = boto3.client(
                's3',
                aws_access_key_id=aws_access,
                aws_secret_access_key=aws_secret,
                region_name="ap-south-1"
            )
        else:
            logger.info("🔑 Using Default/CLI credentials")
            s3_client = boto3.client('s3', region_name="ap-south-1")

        # DEBUG: Verify who we are logged in as
        try:
            sts = boto3.client(
                'sts', 
                aws_access_key_id=aws_access if aws_access else None,
                aws_secret_access_key=aws_secret if aws_secret else None
            )
            identity = sts.get_caller_identity()
            logger.info(f"🕵️ Authenticated as: {identity['Arn']}")
        except Exception as e:
            logger.warning(f"⚠️ Could not verify identity: {e}")

        # 4. Upload
        s3_client.put_object(
            Bucket=TARGET_BUCKET,
            Key=object_key,
            Body=content,
            ContentType=file.content_type,
            CacheControl='max-age=120' 
            # ACL removed to prevent 403 on buckets with Block Public Access
        )
        
        logger.info(f"✅ Successfully overwrote {object_key} with 2-min cache")
        
        return CDNUpdateResponse(
            success=True,
            bucket=TARGET_BUCKET,
            key=object_key,
            url=target_url,
            cache_control="max-age=120",
            message="Image updated successfully. CDN should refresh within 2 minutes."
        )

    except ClientError as e:
        logger.error(f"❌ S3 Upload Error: {e}")
        raise HTTPException(500, f"AWS S3 Error: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Update Failed: {e}")
        raise HTTPException(500, f"Update failed: {str(e)}")