"""
Image Enhancement Pipeline - Core Source Package
MedikaBazaar B2B Marketplace Image Enhancement
Hybrid AI/Local Pipeline with Smart Routing
"""
from .config import (
    get_config, 
    EnhancementMode, 
    ProcessingStatus, 
    QualityTier,
    QCStatus,
    ImageType,
    HybridConfig,
)
from .enhancer import (
    ImageEnhancer, 
    enhance_image, 
    StandardizationConfig,
    EnhancementResult,
    ProcessingStep,
    RoutingDecision,
)
from .quality import QualityAssessor, assess_image, QualityReport
from .bedrock_service import (
    BedrockService, 
    BedrockCallResult,
    Operation,
    ModelProvider,
    ModelConfig,
    AVAILABLE_MODELS,
    RECOMMENDED_MODELS,
    FORMATTERS,
    create_bedrock_service,
    get_model_info,
    list_models_by_provider,
    get_cheapest_model_for_operation,
)
from .database import (
    init_db, get_db, 
    ProductImageRepository, SKURepository, JobRepository,
    ProductGroupRepository, ImageMetricsRepository,
    ProductImage, SKU, ProductGroup, ImageMetrics, ProcessingJob,
    EnhancementConfig, QCReviewLog,
)

# Backward compatibility
ImageRepository = ProductImageRepository
ImageRecord = ProductImage

__all__ = [
    # Config
    'get_config',
    'EnhancementMode',
    'ProcessingStatus',
    'QualityTier',
    'QCStatus',
    'ImageType',
    'HybridConfig',
    
    # Enhancement
    'ImageEnhancer',
    'enhance_image',
    'StandardizationConfig',
    'EnhancementResult',
    'ProcessingStep',
    'RoutingDecision',
    
    # Bedrock AI Service (Multi-Model)
    'BedrockService',
    'BedrockCallResult',
    'Operation',
    'ModelProvider',
    'ModelConfig',
    'AVAILABLE_MODELS',
    'RECOMMENDED_MODELS',
    'FORMATTERS',
    'create_bedrock_service',
    'get_model_info',
    'list_models_by_provider',
    'get_cheapest_model_for_operation',
    
    # Quality
    'QualityAssessor',
    'assess_image',
    'QualityReport',
    
    # Database
    'init_db',
    'get_db',
    'ProductImageRepository',
    'SKURepository',
    'JobRepository',
    'ProductGroupRepository',
    'ImageMetricsRepository',
    
    # Models
    'ProductImage',
    'SKU',
    'ProductGroup',
    'ImageMetrics',
    'ProcessingJob',
    'EnhancementConfig',
    'QCReviewLog',
    
    # Backward compatibility
    'ImageRepository',
    'ImageRecord',
]
