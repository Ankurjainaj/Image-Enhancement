"""
Database models for Image Enhancement Pipeline
MySQL database with product/SKU-centric schema
Supports B2B marketplace image enhancement workflow
"""
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    create_engine, Column, String, Integer, Float, Boolean,
    DateTime, Text, JSON, ForeignKey, Index, BigInteger, SmallInteger
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv

from .config import get_config, ProcessingStatus, QCStatus, QualityTier

Base = declarative_base()

load_dotenv()
def generate_uuid() -> str:
    return str(uuid.uuid4())


# ==================== Core Entity Tables ====================

class ProductGroup(Base):
    """Product Group - represents a product category/group in the marketplace"""
    __tablename__ = "product_groups"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    product_group_id = Column(String(100), unique=True, nullable=False, index=True)
    
    name = Column(String(255), nullable=True)
    category = Column(String(100), nullable=True, index=True)
    sub_category = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    
    # Aggregate counts
    total_skus = Column(Integer, default=0)
    total_images = Column(Integer, default=0)
    enhanced_images = Column(Integer, default=0)
    pending_images = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    skus = relationship("SKU", back_populates="product_group", cascade="all, delete-orphan")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "product_group_id": self.product_group_id,
            "name": self.name,
            "category": self.category,
            "total_skus": self.total_skus,
            "total_images": self.total_images,
            "enhanced_images": self.enhanced_images,
        }


class SKU(Base):
    """SKU - represents a specific product SKU"""
    __tablename__ = "skus"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    sku_id = Column(String(100), unique=True, nullable=False, index=True)
    
    # Foreign key to product group
    product_group_ref = Column(String(36), ForeignKey("product_groups.id"), nullable=True)
    product_group = relationship("ProductGroup", back_populates="skus")
    
    # SKU info
    name = Column(String(255), nullable=True)
    brand = Column(String(100), nullable=True)
    manufacturer = Column(String(255), nullable=True)
    
    is_active = Column(Boolean, default=True)
    
    # Image counts
    total_images = Column(Integer, default=0)
    enhanced_images = Column(Integer, default=0)
    pending_images = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    images = relationship("ProductImage", back_populates="sku", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_skus_product_group", "product_group_ref"),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "sku_id": self.sku_id,
            "name": self.name,
            "brand": self.brand,
            "total_images": self.total_images,
            "enhanced_images": self.enhanced_images,
        }


class ProductImage(Base):
    """
    Product Image - MAIN ENTITY for image enhancement
    
    Key fields:
    - product_group_id: Product group identifier
    - sku_id: SKU identifier
    - image_url: Original CloudFront/source URL
    - enhanced_image_url: Enhanced image URL
    """
    __tablename__ = "product_images"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    
    # Foreign key to SKU
    sku_ref = Column(String(36), ForeignKey("skus.id"), nullable=True)
    sku = relationship("SKU", back_populates="images")
    
    # ========== KEY BUSINESS FIELDS ==========
    product_group_id = Column(String(100), nullable=True, index=True)
    sku_id = Column(String(100), nullable=False, index=True)
    image_url = Column(String(2048), nullable=False, index=True)           # Original URL
    enhanced_image_url = Column(String(2048), nullable=True)               # Enhanced URL
    # ==========================================
    
    # Local storage paths
    original_local_path = Column(String(512), nullable=True)
    enhanced_local_path = Column(String(512), nullable=True)
    
    # Original image metadata
    original_filename = Column(String(255), nullable=True)
    original_width = Column(Integer, nullable=True)
    original_height = Column(Integer, nullable=True)
    original_size_bytes = Column(BigInteger, nullable=True)
    original_format = Column(String(20), nullable=True)
    original_dpi = Column(Integer, nullable=True)
    
    # Enhanced image metadata
    enhanced_width = Column(Integer, nullable=True)
    enhanced_height = Column(Integer, nullable=True)
    enhanced_size_bytes = Column(BigInteger, nullable=True)
    enhanced_format = Column(String(20), nullable=True)
    enhanced_dpi = Column(Integer, nullable=True)
    
    # Image type/angle (multi-angle support from requirements)
    image_type = Column(String(50), default="primary")  # primary, front, side, back, detail, lifestyle
    image_sequence = Column(SmallInteger, default=1)
    
    # Processing status
    status = Column(String(20), default=ProcessingStatus.PENDING.value, index=True)
    enhancement_mode = Column(String(50), nullable=True)
    enhancements_applied = Column(JSON, nullable=True)  # ["bg_removal", "upscale", "denoise", "standardize"]
    
    processing_time_ms = Column(Integer, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(SmallInteger, default=0)
    
    # QC Status (Human-in-the-Loop from requirements)
    qc_status = Column(String(20), default=QCStatus.PENDING.value, index=True)
    qc_score = Column(Float, nullable=True)  # Auto-generated 0-100 score
    qc_reviewed_by = Column(String(100), nullable=True)
    qc_reviewed_at = Column(DateTime, nullable=True)
    qc_notes = Column(Text, nullable=True)
    
    # Flags
    is_hero_image = Column(Boolean, default=False)
    needs_background_removal = Column(Boolean, default=True)
    background_removed = Column(Boolean, default=False)
    needs_upscaling = Column(Boolean, default=False)
    is_standardized = Column(Boolean, default=False)
    is_high_value = Column(Boolean, default=False)  # Requires human QC
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    metrics = relationship("ImageMetrics", back_populates="image", uselist=False, cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_product_images_status_created", "status", "created_at"),
        Index("ix_product_images_sku_status", "sku_id", "status"),
        Index("ix_product_images_qc_status", "qc_status"),
        Index("ix_product_images_product_group", "product_group_id"),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "product_group_id": self.product_group_id,
            "sku_id": self.sku_id,
            "image_url": self.image_url,
            "enhanced_image_url": self.enhanced_image_url,
            "status": self.status,
            "qc_status": self.qc_status,
            "image_type": self.image_type,
            "original_size_kb": round(self.original_size_bytes / 1024, 2) if self.original_size_bytes else None,
            "enhanced_size_kb": round(self.enhanced_size_bytes / 1024, 2) if self.enhanced_size_bytes else None,
            "processing_time_ms": self.processing_time_ms,
            "enhancements_applied": self.enhancements_applied,
            "background_removed": self.background_removed,
            "is_standardized": self.is_standardized,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
        }


# ==================== Metrics Tables ====================

class ImageMetrics(Base):
    """
    Image Metrics - stores quality metrics for before/after comparison
    Separate table for analytics and reporting
    """
    __tablename__ = "image_metrics"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    
    image_id = Column(String(36), ForeignKey("product_images.id"), unique=True, nullable=False)
    image = relationship("ProductImage", back_populates="metrics")
    
    # Original image metrics
    original_blur_score = Column(Float, nullable=True)
    original_brightness = Column(Float, nullable=True)
    original_contrast = Column(Float, nullable=True)
    original_noise_level = Column(Float, nullable=True)
    original_edge_density = Column(Float, nullable=True)
    original_brisque_score = Column(Float, nullable=True)
    original_quality_score = Column(Float, nullable=True)  # Composite 0-100
    original_quality_tier = Column(String(20), nullable=True)
    
    # Enhanced image metrics
    enhanced_blur_score = Column(Float, nullable=True)
    enhanced_brightness = Column(Float, nullable=True)
    enhanced_contrast = Column(Float, nullable=True)
    enhanced_noise_level = Column(Float, nullable=True)
    enhanced_edge_density = Column(Float, nullable=True)
    enhanced_brisque_score = Column(Float, nullable=True)
    enhanced_quality_score = Column(Float, nullable=True)
    enhanced_quality_tier = Column(String(20), nullable=True)
    
    # Improvement metrics
    quality_improvement_percent = Column(Float, nullable=True)
    size_reduction_percent = Column(Float, nullable=True)
    sharpness_improvement_percent = Column(Float, nullable=True)
    resolution_increase_percent = Column(Float, nullable=True)
    
    # Background analysis (per requirements)
    has_background = Column(Boolean, nullable=True)
    background_complexity = Column(Float, nullable=True)  # 0-1
    background_removed = Column(Boolean, default=False)
    
    # Light/Color metrics (per requirements)
    exposure_corrected = Column(Boolean, default=False)
    color_balanced = Column(Boolean, default=False)
    
    assessed_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "image_id": self.image_id,
            "original_quality_score": self.original_quality_score,
            "enhanced_quality_score": self.enhanced_quality_score,
            "quality_improvement_percent": self.quality_improvement_percent,
            "size_reduction_percent": self.size_reduction_percent,
            "sharpness_improvement_percent": self.sharpness_improvement_percent,
            "background_removed": self.background_removed,
        }


# ==================== Processing Tables ====================

class ProcessingJob(Base):
    """Processing Job - tracks batch processing jobs"""
    __tablename__ = "processing_jobs"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    
    job_type = Column(String(50), default="batch")  # batch, single, realtime
    enhancement_mode = Column(String(50), default="auto")
    priority = Column(SmallInteger, default=5)
    
    # Scope
    product_group_id = Column(String(100), nullable=True, index=True)
    sku_id = Column(String(100), nullable=True, index=True)
    
    # Progress
    status = Column(String(20), default=ProcessingStatus.PENDING.value, index=True)
    total_images = Column(Integer, default=0)
    processed_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)
    
    # QC stats
    auto_approved_count = Column(Integer, default=0)
    needs_review_count = Column(Integer, default=0)
    
    # Timing
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Statistics
    avg_processing_time_ms = Column(Float, nullable=True)
    avg_quality_improvement = Column(Float, nullable=True)
    avg_size_reduction = Column(Float, nullable=True)
    total_input_size_bytes = Column(BigInteger, default=0)
    total_output_size_bytes = Column(BigInteger, default=0)
    
    error_message = Column(Text, nullable=True)
    
    # Kafka tracking
    kafka_offset = Column(BigInteger, nullable=True)
    kafka_partition = Column(Integer, nullable=True)
    
    created_by = Column(String(100), nullable=True)
    job_metadata = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def progress_percentage(self) -> float:
        if self.total_images == 0:
            return 0.0
        return round((self.processed_count / self.total_images) * 100, 2)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "job_type": self.job_type,
            "status": self.status,
            "product_group_id": self.product_group_id,
            "sku_id": self.sku_id,
            "total_images": self.total_images,
            "processed_count": self.processed_count,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "progress_percentage": self.progress_percentage,
            "avg_quality_improvement": self.avg_quality_improvement,
        }


class EnhancementConfig(Base):
    """Enhancement Configuration - per category/SKU settings"""
    __tablename__ = "enhancement_configs"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    
    config_type = Column(String(20), default="global")  # global, category, product_group, sku
    product_group_id = Column(String(100), nullable=True, index=True)
    category = Column(String(100), nullable=True, index=True)
    sku_id = Column(String(100), nullable=True, index=True)
    
    # Enhancement toggles (per MedikaBazaar requirements)
    enable_background_removal = Column(Boolean, default=True)
    background_color = Column(String(20), default="#FFFFFF")
    
    enable_light_correction = Column(Boolean, default=True)
    enable_color_balance = Column(Boolean, default=True)
    
    enable_upscaling = Column(Boolean, default=True)
    target_min_dimension = Column(Integer, default=1500)
    max_upscale_factor = Column(Float, default=2.0)
    target_dpi = Column(Integer, default=300)
    
    enable_denoising = Column(Boolean, default=True)
    denoise_strength = Column(Integer, default=10)
    
    enable_sharpening = Column(Boolean, default=True)
    sharpen_strength = Column(Float, default=1.5)
    
    # Standardization settings (per requirements)
    enable_standardization = Column(Boolean, default=True)
    target_aspect_ratio = Column(String(10), default="1:1")
    target_width = Column(Integer, default=1200)
    target_height = Column(Integer, default=1200)
    padding_percent = Column(Integer, default=5)
    
    # Output settings
    output_format = Column(String(10), default="JPEG")
    jpeg_quality = Column(Integer, default=92)
    target_max_size_kb = Column(Integer, default=500)
    
    # QC settings (Human-in-the-Loop)
    auto_approve_threshold = Column(Float, default=75.0)
    require_human_qc = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class QCReviewLog(Base):
    """QC Review Log - tracks human QC reviews"""
    __tablename__ = "qc_review_logs"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    
    image_id = Column(String(36), ForeignKey("product_images.id"), nullable=False, index=True)
    
    reviewer_id = Column(String(100), nullable=False)
    reviewer_name = Column(String(255), nullable=True)
    
    previous_status = Column(String(20), nullable=True)
    new_status = Column(String(20), nullable=False)
    
    score = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    rejection_reason = Column(String(255), nullable=True)
    
    reviewed_at = Column(DateTime, default=datetime.utcnow)


# ==================== Database Session Management ====================

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        config = get_config()
        
        _engine = create_engine(
            config.database.url,
            echo=config.database.echo,
            poolclass=QueuePool,
            pool_size=config.database.pool_size,
            max_overflow=config.database.max_overflow,
            pool_recycle=config.database.pool_recycle,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False
        )
    return _SessionLocal


def get_db() -> Session:
    """Get a database session"""
    SessionLocal = get_session_factory()
    return SessionLocal()


def init_db():
    """Initialize database tables"""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully")


def get_db_session():
    """Context manager for database sessions"""
    db = get_db()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ==================== Repository Classes ====================

class ProductImageRepository:
    """Repository for product image operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, **kwargs) -> ProductImage:
        image = ProductImage(**kwargs)
        self.db.add(image)
        self.db.commit()
        self.db.refresh(image)
        return image
    
    def get_by_id(self, image_id: str) -> Optional[ProductImage]:
        return self.db.query(ProductImage).filter(ProductImage.id == image_id).first()
    
    def get_by_url(self, url: str) -> Optional[ProductImage]:
        return self.db.query(ProductImage).filter(ProductImage.image_url == url).first()
    
    def get_by_sku(self, sku_id: str, limit: int = 100) -> List[ProductImage]:
        return self.db.query(ProductImage).filter(
            ProductImage.sku_id == sku_id
        ).limit(limit).all()
    
    def get_by_product_group(self, product_group_id: str, limit: int = 1000) -> List[ProductImage]:
        return self.db.query(ProductImage).filter(
            ProductImage.product_group_id == product_group_id
        ).limit(limit).all()
    
    def get_pending(self, limit: int = 100) -> List[ProductImage]:
        return self.db.query(ProductImage).filter(
            ProductImage.status == ProcessingStatus.PENDING.value
        ).order_by(ProductImage.created_at).limit(limit).all()
    
    def get_needs_qc_review(self, limit: int = 100) -> List[ProductImage]:
        return self.db.query(ProductImage).filter(
            ProductImage.qc_status == QCStatus.NEEDS_REVIEW.value
        ).order_by(ProductImage.processed_at).limit(limit).all()
    
    def update_status(self, image_id: str, status: ProcessingStatus, **kwargs):
        self.db.query(ProductImage).filter(ProductImage.id == image_id).update({
            "status": status.value,
            "updated_at": datetime.utcnow(),
            **kwargs
        })
        self.db.commit()
    
    def update_enhanced(
        self,
        image_id: str,
        enhanced_url: str,
        enhanced_path: str = None,
        **metrics
    ):
        """Update image after enhancement"""
        update_data = {
            "enhanced_image_url": enhanced_url,
            "enhanced_local_path": enhanced_path,
            "status": ProcessingStatus.COMPLETED.value,
            "processed_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        update_data.update(metrics)
        
        self.db.query(ProductImage).filter(ProductImage.id == image_id).update(update_data)
        self.db.commit()
    
    def update_qc_status(self, image_id: str, qc_status: QCStatus, reviewer: str = None, notes: str = None):
        self.db.query(ProductImage).filter(ProductImage.id == image_id).update({
            "qc_status": qc_status.value,
            "qc_reviewed_by": reviewer,
            "qc_reviewed_at": datetime.utcnow() if reviewer else None,
            "qc_notes": notes,
            "updated_at": datetime.utcnow(),
        })
        self.db.commit()
    
    def bulk_create(self, images: List[Dict]) -> int:
        """Bulk insert images, skip duplicates"""
        created = 0
        for img_data in images:
            existing = self.get_by_url(img_data.get("image_url", ""))
            if not existing:
                self.db.add(ProductImage(**img_data))
                created += 1
        self.db.commit()
        return created
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get overall statistics"""
        from sqlalchemy import func
        
        total = self.db.query(ProductImage).count()
        
        status_counts = {}
        for status in ProcessingStatus:
            count = self.db.query(ProductImage).filter(
                ProductImage.status == status.value
            ).count()
            status_counts[status.value] = count
        
        qc_counts = {}
        for qc in QCStatus:
            count = self.db.query(ProductImage).filter(
                ProductImage.qc_status == qc.value
            ).count()
            qc_counts[qc.value] = count
        
        avg_improvement = self.db.query(func.avg(ImageMetrics.quality_improvement_percent)).scalar()
        avg_size_reduction = self.db.query(func.avg(ImageMetrics.size_reduction_percent)).scalar()
        
        return {
            "total_images": total,
            "status_counts": status_counts,
            "qc_counts": qc_counts,
            "avg_quality_improvement": round(avg_improvement, 2) if avg_improvement else None,
            "avg_size_reduction": round(avg_size_reduction, 2) if avg_size_reduction else None,
        }


class SKURepository:
    """Repository for SKU operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, **kwargs) -> SKU:
        sku = SKU(**kwargs)
        self.db.add(sku)
        self.db.commit()
        self.db.refresh(sku)
        return sku
    
    def get_by_sku_id(self, sku_id: str) -> Optional[SKU]:
        return self.db.query(SKU).filter(SKU.sku_id == sku_id).first()
    
    def get_or_create(self, sku_id: str, **kwargs) -> SKU:
        existing = self.get_by_sku_id(sku_id)
        if existing:
            return existing
        return self.create(sku_id=sku_id, **kwargs)
    
    def update_image_counts(self, sku_id: str):
        """Update image counts for a SKU"""
        sku = self.get_by_sku_id(sku_id)
        if sku:
            total = self.db.query(ProductImage).filter(ProductImage.sku_id == sku_id).count()
            enhanced = self.db.query(ProductImage).filter(
                ProductImage.sku_id == sku_id,
                ProductImage.status == ProcessingStatus.COMPLETED.value
            ).count()
            pending = self.db.query(ProductImage).filter(
                ProductImage.sku_id == sku_id,
                ProductImage.status == ProcessingStatus.PENDING.value
            ).count()
            
            self.db.query(SKU).filter(SKU.sku_id == sku_id).update({
                "total_images": total,
                "enhanced_images": enhanced,
                "pending_images": pending
            })
            self.db.commit()


class ProductGroupRepository:
    """Repository for product group operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, **kwargs) -> ProductGroup:
        pg = ProductGroup(**kwargs)
        self.db.add(pg)
        self.db.commit()
        self.db.refresh(pg)
        return pg
    
    def get_by_id(self, product_group_id: str) -> Optional[ProductGroup]:
        return self.db.query(ProductGroup).filter(
            ProductGroup.product_group_id == product_group_id
        ).first()
    
    def get_or_create(self, product_group_id: str, **kwargs) -> ProductGroup:
        existing = self.get_by_id(product_group_id)
        if existing:
            return existing
        return self.create(product_group_id=product_group_id, **kwargs)


class JobRepository:
    """Repository for processing jobs"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, **kwargs) -> ProcessingJob:
        job = ProcessingJob(**kwargs)
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job
    
    def get_by_id(self, job_id: str) -> Optional[ProcessingJob]:
        return self.db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    
    def update_progress(self, job_id: str, **kwargs):
        self.db.query(ProcessingJob).filter(ProcessingJob.id == job_id).update({
            "updated_at": datetime.utcnow(),
            **kwargs
        })
        self.db.commit()


class ImageMetricsRepository:
    """Repository for image metrics"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, **kwargs) -> ImageMetrics:
        metrics = ImageMetrics(**kwargs)
        self.db.add(metrics)
        self.db.commit()
        self.db.refresh(metrics)
        return metrics
    
    def get_by_image_id(self, image_id: str) -> Optional[ImageMetrics]:
        return self.db.query(ImageMetrics).filter(ImageMetrics.image_id == image_id).first()
    
    def upsert(self, image_id: str, **kwargs) -> ImageMetrics:
        existing = self.get_by_image_id(image_id)
        if existing:
            self.db.query(ImageMetrics).filter(ImageMetrics.image_id == image_id).update({
                "assessed_at": datetime.utcnow(),
                **kwargs
            })
            self.db.commit()
            self.db.refresh(existing)
            return existing
        return self.create(image_id=image_id, **kwargs)


# Backward compatibility aliases
ImageRepository = ProductImageRepository
ImageRecord = ProductImage


if __name__ == "__main__":
    init_db()
