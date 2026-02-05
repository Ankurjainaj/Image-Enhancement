"""
Configuration settings for Image Enhancement Pipeline
Updated for MySQL and MedikaBazaar requirements
"""
import os
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv()

class EnhancementMode(str, Enum):
    """Enhancement modes based on MedikaBazaar requirements"""
    AUTO = "auto"                       # Automatically detect and apply best enhancements
    BACKGROUND_REMOVE = "bg_remove"     # Remove and replace background with white
    LIGHT_CORRECTION = "light_correct"  # Fix exposure, brightness, color balance
    UPSCALE_DENOISE = "upscale_denoise" # Super resolution + noise removal
    STANDARDIZE = "standardize"         # Uniform sizing, aspect ratio, padding
    SHARPEN = "sharpen"                 # Focus on sharpening for text clarity
    DENOISE = "denoise"                 # Noise removal only
    UPSCALE = "upscale"                 # Upscaling only
    OPTIMIZE = "optimize"               # Optimize file size while maintaining quality
    FULL = "full"                       # Apply all enhancements (full pipeline)


class QualityTier(str, Enum):
    """Quality tier classifications"""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    VERY_POOR = "very_poor"


class ProcessingStatus(str, Enum):
    """Processing status for images"""
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class QCStatus(str, Enum):
    """Human-in-the-loop QC status"""
    PENDING = "pending"
    AUTO_APPROVED = "auto_approved"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    REWORK = "rework"


class ImageType(str, Enum):
    """Type of product image"""
    PRIMARY = "primary"
    FRONT = "front"
    SIDE = "side"
    BACK = "back"
    DETAIL = "detail"
    LIFESTYLE = "lifestyle"
    THUMBNAIL = "thumbnail"


@dataclass
class QualityThresholds:
    """Thresholds for quality assessment"""
    brisque_excellent: float = 25.0
    brisque_good: float = 40.0
    brisque_acceptable: float = 50.0
    brisque_poor: float = 60.0
    
    blur_excellent: float = 300.0
    blur_acceptable: float = 100.0
    blur_poor: float = 50.0
    
    resolution_excellent: int = 1500
    resolution_good: int = 1000
    resolution_acceptable: int = 800
    resolution_poor: int = 500
    
    size_max_target: int = 500
    size_warning: int = 1000
    
    # QC auto-approve threshold (0-100)
    qc_auto_approve: float = 75.0


@dataclass
class StandardizationParams:
    """Parameters for image standardization (MedikaBazaar requirements)"""
    target_width: int = 1200
    target_height: int = 1200
    min_dimension: int = 1000
    max_dimension: int = 2000
    
    maintain_aspect_ratio: bool = True
    padding_percent: int = 5
    padding_color: tuple = (255, 255, 255)
    background_color: tuple = (255, 255, 255)
    
    target_dpi: int = 300
    
    thumbnail_width: int = 150
    thumbnail_height: int = 150


@dataclass
class EnhancementParams:
    """Parameters for image enhancement operations"""
    # Sharpening
    sharpen_strength: float = 1.5
    sharpen_radius: float = 1.0
    sharpen_threshold: int = 3
    
    # Denoising (bilateral filter)
    denoise_strength: int = 10
    denoise_sigma_color: int = 20
    denoise_sigma_space: int = 10
    
    # Contrast enhancement (CLAHE)
    clahe_clip_limit: float = 2.0
    clahe_grid_size: tuple = (8, 8)
    
    # Upscaling
    upscale_factor: float = 2.0
    upscale_max_dimension: int = 4096
    
    # Output quality
    jpeg_quality: int = 92
    png_compression: int = 6
    webp_quality: int = 90
    
    # Optimization
    target_max_size_kb: int = 500
    progressive_jpeg: bool = True
    min_quality: int = 60
    
    # Light/Color correction
    auto_white_balance: bool = True
    gamma_correction: float = 1.0
    saturation_boost: float = 1.05
    
    # Background removal
    bg_removal_enabled: bool = True
    bg_replacement_color: tuple = (255, 255, 255)


@dataclass
class KafkaConfig:
    """Kafka configuration"""
    bootstrap_servers: str = field(
        default_factory=lambda: os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    )
    
    jobs_topic: str = "image-enhancement-jobs"
    results_topic: str = "image-enhancement-results"
    dlq_topic: str = "image-enhancement-dlq"
    marketplace_topic: str = "marketplace-image-updates"
    
    consumer_group: str = "image-enhancer-workers"
    auto_offset_reset: str = "earliest"
    enable_auto_commit: bool = False
    max_poll_records: int = 10
    
    acks: str = "all"
    retries: int = 3
    
    session_timeout_ms: int = 30000
    heartbeat_interval_ms: int = 10000


@dataclass
class RedisConfig:
    """Redis configuration"""
    host: str = field(default_factory=lambda: os.getenv("REDIS_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")))
    db: int = 0
    password: Optional[str] = field(default_factory=lambda: os.getenv("REDIS_PASSWORD"))
    
    job_status_prefix: str = "job:status:"
    job_progress_prefix: str = "job:progress:"
    image_cache_prefix: str = "img:cache:"
    
    status_ttl: int = 86400
    cache_ttl: int = 3600
    
    @property
    def url(self) -> str:
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


@dataclass
class MySQLConfig:
    """MySQL Database configuration"""
    host: str = field(default_factory=lambda: os.getenv("MYSQL_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("MYSQL_PORT", "3306")))
    database: str = field(default_factory=lambda: os.getenv("MYSQL_DATABASE", "image_enhancer"))
    user: str = field(default_factory=lambda: os.getenv("MYSQL_USER", "root"))
    password: str = field(default_factory=lambda: os.getenv("MYSQL_PASSWORD", ""))
    charset: str = "utf8mb4"
    
    pool_size: int = 10
    max_overflow: int = 20
    pool_recycle: int = 3600
    echo: bool = False
    # Auto-migrate/create tables and missing columns when true (development convenience)
    auto_migrate: bool = field(default_factory=lambda: os.getenv("DB_AUTO_MIGRATE", "false").lower() == "true")
    
    @property
    def url(self) -> str:
        encoded_password = quote_plus(self.password)
        return (
            f"mysql+pymysql://{self.user}:{encoded_password}@"
            f"{self.host}:{self.port}/{self.database}?charset={self.charset}"
        )


@dataclass
class StorageConfig:
    """Storage configuration"""
    local_storage_path: Path = field(
        default_factory=lambda: Path(__file__).parent.parent / "data" / "enhanced"
    )
    
    # S3 Configuration
    s3_bucket: str = field(default_factory=lambda: os.getenv("S3_BUCKET", ""))
    s3_prefix: str = "enhanced/"
    s3_region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "ap-south-1"))
    s3_endpoint: str = field(default_factory=lambda: os.getenv("S3_ENDPOINT", ""))
    s3_access_key: str = field(default_factory=lambda: os.getenv("AWS_ACCESS_KEY_ID", ""))
    s3_secret_key: str = field(default_factory=lambda: os.getenv("AWS_SECRET_ACCESS_KEY", ""))
    catalyst_bucket: str = field(default_factory=lambda: os.getenv("CATALYST_BUCKET", ""))
    catalyst_s3_access_key: str = field(default_factory=lambda: os.getenv("CATALYST_BUCKET_ACCESS_KEY", ""))
    catalyst_s3_secret_key: str = field(default_factory=lambda: os.getenv("CATALYST_BUCKET_SECRET_KEY", ""))
    
    cloudfront_domain: str = field(
        default_factory=lambda: os.getenv("CLOUDFRONT_DOMAIN", "")
    )
    
    # Storage options
    use_s3_only: bool = field(default_factory=lambda: os.getenv("USE_S3_ONLY", "false").lower() == "true")
    
    @property
    def use_s3(self) -> bool:
        return bool(self.s3_bucket)


@dataclass
class APIConfig:
    """API configuration"""
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    
    rate_limit_requests: int = 100
    rate_limit_window: int = 60
    
    max_upload_size_mb: int = 50
    allowed_extensions: tuple = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff")
    
    cors_origins: list = field(default_factory=lambda: ["*"])
    
    # Gemini API configuration
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    enable_gemini: bool = field(default_factory=lambda: bool(os.getenv("GEMINI_API_KEY")))
    use_gemini_batch: bool = field(default_factory=lambda: os.getenv("USE_GEMINI_BATCH", "false").lower() == "true")


@dataclass
class HybridConfig:
    """
    Hybrid AI/Local Pipeline Configuration
    
    Controls when to use AI (Bedrock) vs local (OpenCV) processing.
    AI is more expensive but higher quality for complex cases.
    
    IMPORTANT: Bedrock is in us-east-1 region!
    """
    # Master toggle for Bedrock
    enable_bedrock: bool = field(
        default_factory=lambda: os.getenv("ENABLE_BEDROCK", "true").lower() == "true"
    )
    
    # Bedrock region (separate from S3 region!)
    bedrock_region: str = field(
        default_factory=lambda: os.getenv("BEDROCK_REGION", "us-east-1")
    )
    
    # Cost controls
    max_daily_cost: float = field(
        default_factory=lambda: float(os.getenv("MAX_DAILY_AI_COST", "10.0"))
    )
    
    # Default model selection
    # Options: nova_canvas, titan_v2, titan_v1, sd35_large, stability_services
    default_model: str = field(
        default_factory=lambda: os.getenv("BEDROCK_DEFAULT_MODEL", "nova_canvas")
    )
    
    # Model preferences per operation (override defaults)
    # Format: operation=model (e.g., "background_removal=nova_canvas")
    model_bg_removal: str = field(
        default_factory=lambda: os.getenv("MODEL_BG_REMOVAL", "nova_canvas")
    )
    model_upscale: str = field(
        default_factory=lambda: os.getenv("MODEL_UPSCALE", "nova_canvas")
    )
    model_lighting: str = field(
        default_factory=lambda: os.getenv("MODEL_LIGHTING", "nova_canvas")
    )
    model_inpainting: str = field(
        default_factory=lambda: os.getenv("MODEL_INPAINTING", "nova_canvas")
    )
    
    # Smart routing thresholds (when to use AI vs local)
    low_res_threshold: int = field(
        default_factory=lambda: int(os.getenv("LOW_RES_THRESHOLD", "800"))
    )
    blur_threshold: float = field(
        default_factory=lambda: float(os.getenv("BLUR_THRESHOLD", "100.0"))
    )
    bg_complexity_threshold: float = field(
        default_factory=lambda: float(os.getenv("BG_COMPLEXITY_THRESHOLD", "0.4"))
    )
    brightness_deviation_threshold: float = field(
        default_factory=lambda: float(os.getenv("BRIGHTNESS_DEVIATION_THRESHOLD", "40.0"))
    )
    
    # Feature toggles for specific AI operations
    use_ai_upscaling: bool = field(
        default_factory=lambda: os.getenv("USE_AI_UPSCALING", "true").lower() == "true"
    )
    use_ai_lighting: bool = field(
        default_factory=lambda: os.getenv("USE_AI_LIGHTING", "true").lower() == "true"
    )
    use_ai_bg_removal: bool = field(
        default_factory=lambda: os.getenv("USE_AI_BG_REMOVAL", "true").lower() == "true"
    )
    
    # Stability AI specific settings
    stability_upscale_mode: str = field(
        default_factory=lambda: os.getenv("STABILITY_UPSCALE_MODE", "creative")
    )  # creative, conservative, fast


@dataclass 
class Config:
    """Main configuration class"""
    quality: QualityThresholds = field(default_factory=QualityThresholds)
    enhancement: EnhancementParams = field(default_factory=EnhancementParams)
    standardization: StandardizationParams = field(default_factory=StandardizationParams)
    kafka: KafkaConfig = field(default_factory=KafkaConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    mysql: MySQLConfig = field(default_factory=MySQLConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    api: APIConfig = field(default_factory=APIConfig)
    hybrid: HybridConfig = field(default_factory=HybridConfig)
    
    worker_concurrency: int = 4
    batch_size: int = 50
    
    enable_brisque: bool = True
    enable_background_removal: bool = True
    enable_realtime_api: bool = True
    enable_kafka_pipeline: bool = True
    enable_qc_workflow: bool = True
    
    log_level: str = "INFO"
    
    @property
    def database(self) -> MySQLConfig:
        """Alias for mysql config"""
        return self.mysql
    
    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            worker_concurrency=int(os.getenv("WORKER_CONCURRENCY", "4")),
            batch_size=int(os.getenv("BATCH_SIZE", "50")),
            enable_brisque=os.getenv("ENABLE_BRISQUE", "true").lower() == "true",
            enable_background_removal=os.getenv("ENABLE_BG_REMOVAL", "true").lower() == "true",
            enable_qc_workflow=os.getenv("ENABLE_QC_WORKFLOW", "true").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


# Global config instance
_config = None


def get_config() -> Config:
    """Get the global config instance"""
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config