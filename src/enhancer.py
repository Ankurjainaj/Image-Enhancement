"""
Core Image Enhancement Engine - Hybrid AI/Local Pipeline
Cost-optimized implementation using Smart Router

Pipeline Flow:
1. INPUT → Quality Analysis
2. Quality Analysis → Smart Router (decide Local vs AI for each operation)
3. Smart Router → Processing (Background, Lighting, Upscale, Denoise)
4. Processing → Standardization
5. Standardization → Optimization (compression)
6. Optimization → OUTPUT

Logging: Comprehensive step-by-step logging for debugging
"""
import io
import time
import logging
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Union, List
from dataclasses import dataclass, field
from enum import Enum

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from .config import get_config, EnhancementMode, EnhancementParams
from .logging_config import RequestLogger

# Configure detailed logging
logger = logging.getLogger(__name__)


@dataclass
class ProcessingStep:
    """Record of a single processing step"""
    name: str
    method: str  # "local" or "ai"
    success: bool
    latency_ms: int
    details: str = ""
    cost_usd: float = 0.0


@dataclass
class EnhancementResult:
    """Result of image enhancement operation with detailed metrics"""
    success: bool
    enhanced_image: Optional[np.ndarray] = None
    enhanced_pil: Optional[Image.Image] = None
    original_size_bytes: int = 0
    enhanced_size_bytes: int = 0
    original_dimensions: Tuple[int, int] = (0, 0)
    enhanced_dimensions: Tuple[int, int] = (0, 0)
    processing_time_ms: int = 0
    enhancements_applied: List[str] = None
    processing_steps: List[ProcessingStep] = None
    background_removed: bool = False
    ai_used: bool = False
    total_ai_cost: float = 0.0
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.enhancements_applied is None:
            self.enhancements_applied = []
        if self.processing_steps is None:
            self.processing_steps = []
    
    @property
    def size_reduction_percent(self) -> float:
        if self.original_size_bytes == 0:
            return 0.0
        reduction = (1 - self.enhanced_size_bytes / self.original_size_bytes) * 100
        return round(reduction, 2)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "original_size_bytes": self.original_size_bytes,
            "enhanced_size_bytes": self.enhanced_size_bytes,
            "size_reduction_percent": self.size_reduction_percent,
            "original_dimensions": self.original_dimensions,
            "enhanced_dimensions": self.enhanced_dimensions,
            "processing_time_ms": self.processing_time_ms,
            "enhancements_applied": self.enhancements_applied,
            "processing_steps": [
                {"name": s.name, "method": s.method, "latency_ms": s.latency_ms, "cost": s.cost_usd}
                for s in self.processing_steps
            ],
            "background_removed": self.background_removed,
            "ai_used": self.ai_used,
            "total_ai_cost_usd": self.total_ai_cost,
            "error": self.error,
        }


@dataclass
class StandardizationConfig:
    """Configuration for image standardization"""
    target_width: Optional[int] = None
    target_height: Optional[int] = None
    target_aspect_ratio: Optional[str] = None  # "1:1", "4:3", "16:9"
    padding_percent: int = 5
    background_color: Tuple[int, int, int] = (255, 255, 255)
    min_dimension: int = 1000
    max_dimension: int = 2000


@dataclass
class RoutingDecision:
    """Decision from Smart Router for an operation"""
    operation: str
    use_ai: bool
    reason: str
    metrics_used: Dict[str, Any] = None


class ImageEnhancer:
    """
    Core Enhancement Engine with Hybrid AI/Local Pipeline
    
    Smart Router Logic:
    - Analyzes image metrics FIRST
    - Routes each operation to Local (free) or AI (paid) based on thresholds
    - Logs every decision and step for debugging
    """
    
    def __init__(self, params: Optional[EnhancementParams] = None):
        self.params = params or get_config().enhancement
        self.config = get_config()
        self._bedrock = None  # Lazy load
        self._assessor = None  # Lazy load
        
        logger.info("=" * 60)
        logger.info("🔧 ImageEnhancer Initialized")
        logger.info(f"   Bedrock Enabled: {self.config.hybrid.enable_bedrock}")
        logger.info(f"   Thresholds: blur<{self.config.hybrid.blur_threshold}, "
                   f"res<{self.config.hybrid.low_res_threshold}px, "
                   f"bg_complexity>{self.config.hybrid.bg_complexity_threshold}")
        logger.info("=" * 60)
    
    @property
    def bedrock(self):
        """Lazy load Bedrock service"""
        if self._bedrock is None:
            from .bedrock_service import BedrockService
            self._bedrock = BedrockService()
        return self._bedrock
    
    @property
    def assessor(self):
        """Lazy load Quality Assessor"""
        if self._assessor is None:
            from .quality import QualityAssessor
            self._assessor = QualityAssessor()
        return self._assessor
    
    # ==================== SMART ROUTER ====================
    
    def _analyze_and_route(self, img: np.ndarray) -> Tuple[Dict[str, Any], List[RoutingDecision]]:
        """
        Analyze image and determine routing for each operation
        Returns: (metrics_dict, list of routing decisions)
        """
        logger.info("📊 SMART ROUTER: Analyzing image metrics...")
        
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Calculate all metrics
        metrics = {
            "width": w,
            "height": h,
            "min_dimension": min(w, h),
            "blur_score": float(cv2.Laplacian(gray, cv2.CV_64F).var()),
            "brightness": float(np.mean(gray)),
            "contrast": float(np.std(gray)),
            "noise_level": self._estimate_noise(gray),
            "background_complexity": self.detect_background_complexity(img),
        }
        
        # Calculate lighting deviation from optimal (128)
        metrics["lighting_deviation"] = abs(metrics["brightness"] - 128)
        
        logger.info(f"   📏 Dimensions: {w}x{h} (min: {metrics['min_dimension']}px)")
        logger.info(f"   🔍 Blur Score: {metrics['blur_score']:.1f} (threshold: {self.config.hybrid.blur_threshold})")
        logger.info(f"   💡 Brightness: {metrics['brightness']:.1f} (deviation: {metrics['lighting_deviation']:.1f})")
        logger.info(f"   📊 Contrast: {metrics['contrast']:.1f}")
        logger.info(f"   🔊 Noise: {metrics['noise_level']:.1f}")
        logger.info(f"   🖼️ BG Complexity: {metrics['background_complexity']:.2f} (threshold: {self.config.hybrid.bg_complexity_threshold})")
        
        # Make routing decisions
        decisions = []
        hybrid = self.config.hybrid
        
        logger.info("")
        logger.info("🔍 THRESHOLD CHECKS:")
        
        # 1. Background Removal Routing
        bg_complex = metrics["background_complexity"] > hybrid.bg_complexity_threshold
        logger.info(f"   Background Complexity: {metrics['background_complexity']:.2f} {'>' if bg_complex else '<='} {hybrid.bg_complexity_threshold}")
        if bg_complex:
            logger.info(f"      → ☁️  COMPLEX: Will use AI (Bedrock) if enabled")
            decisions.append(RoutingDecision(
                operation="background_removal",
                use_ai=hybrid.use_ai_bg_removal and hybrid.enable_bedrock,
                reason=f"Complex background ({metrics['background_complexity']:.2f} > {hybrid.bg_complexity_threshold})",
                metrics_used={"background_complexity": metrics["background_complexity"]}
            ))
        else:
            logger.info(f"      → 💻 SIMPLE: Will use LOCAL (GrabCut)")
            decisions.append(RoutingDecision(
                operation="background_removal",
                use_ai=False,
                reason=f"Simple background ({metrics['background_complexity']:.2f} <= {hybrid.bg_complexity_threshold})",
                metrics_used={"background_complexity": metrics["background_complexity"]}
            ))
        
        # 2. Upscaling Routing
        low_res = metrics["min_dimension"] < hybrid.low_res_threshold
        blurry = metrics["blur_score"] < hybrid.blur_threshold
        logger.info(f"   Resolution: {metrics['min_dimension']}px {'<' if low_res else '>='} {hybrid.low_res_threshold}px")
        logger.info(f"   Blur Score: {metrics['blur_score']:.1f} {'<' if blurry else '>='} {hybrid.blur_threshold}")
        
        needs_ai_upscale = low_res or blurry
        if needs_ai_upscale:
            reasons = []
            if low_res:
                reasons.append(f"low resolution ({metrics['min_dimension']}<{hybrid.low_res_threshold})")
            if blurry:
                reasons.append(f"blurry ({metrics['blur_score']:.0f}<{hybrid.blur_threshold})")
            logger.info(f"      → ☁️  NEEDS UPSCALE: {' AND '.join(reasons)} - Will use AI if enabled")
            decisions.append(RoutingDecision(
                operation="upscaling",
                use_ai=hybrid.use_ai_upscaling and hybrid.enable_bedrock,
                reason=f"Low res ({metrics['min_dimension']}<{hybrid.low_res_threshold}) or blurry ({metrics['blur_score']:.0f}<{hybrid.blur_threshold})",
                metrics_used={"min_dimension": metrics["min_dimension"], "blur_score": metrics["blur_score"]}
            ))
        else:
            logger.info(f"      → 💻 GOOD QUALITY: Will use LOCAL (Lanczos)")
            decisions.append(RoutingDecision(
                operation="upscaling",
                use_ai=False,
                reason=f"Good quality (res:{metrics['min_dimension']}px, blur:{metrics['blur_score']:.0f})",
                metrics_used={"min_dimension": metrics["min_dimension"], "blur_score": metrics["blur_score"]}
            ))
        
        # 3. Lighting Correction Routing
        major_lighting_issue = metrics["lighting_deviation"] > 40
        logger.info(f"   Lighting Deviation: {metrics['lighting_deviation']:.1f} {'>' if major_lighting_issue else '<='} 40")
        if major_lighting_issue:
            logger.info(f"      → ☁️  MAJOR ISSUE: Will use AI (Bedrock) if enabled")
            decisions.append(RoutingDecision(
                operation="lighting",
                use_ai=hybrid.use_ai_lighting and hybrid.enable_bedrock,
                reason=f"Major lighting issue (deviation: {metrics['lighting_deviation']:.0f} > 40)",
                metrics_used={"brightness": metrics["brightness"], "deviation": metrics["lighting_deviation"]}
            ))
        else:
            logger.info(f"      → 💻 MINOR/NO ISSUE: Will use LOCAL (CLAHE)")
            decisions.append(RoutingDecision(
                operation="lighting",
                use_ai=False,
                reason=f"Minor/no lighting issue (deviation: {metrics['lighting_deviation']:.0f} <= 40)",
                metrics_used={"brightness": metrics["brightness"], "deviation": metrics["lighting_deviation"]}
            ))
        
        # Log final routing decisions
        logger.info("")
        logger.info("🔀 FINAL ROUTING DECISIONS:")
        for d in decisions:
            method = "☁️ AI (Bedrock)" if d.use_ai else "💻 LOCAL (OpenCV)"
            enabled_status = ""
            if d.use_ai and not hybrid.enable_bedrock:
                enabled_status = " [DISABLED - using LOCAL instead]"
            logger.info(f"   {d.operation.upper()}: {method}{enabled_status}")
            logger.info(f"      Reason: {d.reason}")
        
        return metrics, decisions
    
    def _get_routing_decision(self, decisions: List[RoutingDecision], operation: str) -> Optional[RoutingDecision]:
        """Get routing decision for a specific operation"""
        for d in decisions:
            if d.operation == operation:
                return d
        return None
    
    # ==================== MAIN ENHANCE METHOD ====================
    
    def enhance(
        self,
        image_input: Union[str, Path, bytes, np.ndarray, Image.Image],
        mode: EnhancementMode = EnhancementMode.AUTO,
        output_format: str = "JPEG",
        target_size_kb: Optional[int] = None,
        remove_background: bool = False,
        background_color: Tuple[int, int, int] = (255, 255, 255),
        standardize: bool = False,
        standardization_config: Optional[StandardizationConfig] = None
    ) -> EnhancementResult:
        """
        Main enhancement entry point with Smart Router
        
        Pipeline:
        1. Load image
        2. Analyze metrics & make routing decisions
        3. Apply enhancements (routed to Local or AI)
        4. Standardize (if requested)
        5. Optimize output
        """
        start_time = time.time()
        result = EnhancementResult(success=False)
        
        logger.info("=" * 70)
        logger.info(f"🖼️ ENHANCEMENT START | Mode: {mode.value} | BG Remove: {remove_background} | Standardize: {standardize}")
        logger.info("=" * 70)
        
        try:
            # ========== STEP 1: LOAD IMAGE ==========
            step_start = time.time()
            img, original_bytes = self._load_image(image_input)
            result.original_size_bytes = len(original_bytes) if original_bytes else 0
            result.original_dimensions = (img.shape[1], img.shape[0])
            
            load_time = int((time.time() - step_start) * 1000)
            logger.info(f"📥 STEP 1: Image Loaded | Size: {result.original_size_bytes/1024:.1f}KB | "
                       f"Dims: {result.original_dimensions} | Time: {load_time}ms")
            
            # ========== STEP 2: ANALYZE & ROUTE ==========
            step_start = time.time()
            metrics, routing_decisions = self._analyze_and_route(img)
            route_time = int((time.time() - step_start) * 1000)
            logger.info(f"📊 STEP 2: Analysis Complete | Time: {route_time}ms")
            
            # ========== STEP 3: APPLY ENHANCEMENTS ==========
            enhanced = img.copy()
            enhancements = []
            total_ai_cost = 0.0
            
            logger.info("⚙️ STEP 3: Applying Enhancements...")
            
            # --- 3a. Background Removal ---
            if mode == EnhancementMode.BACKGROUND_REMOVE or remove_background:
                step_start = time.time()
                routing = self._get_routing_decision(routing_decisions, "background_removal")
                
                if routing and routing.use_ai:
                    # Use AI for complex backgrounds
                    logger.info("")
                    logger.info("☁️  USING AI: Background Removal (Bedrock)")
                    logger.info(f"   Reason: {routing.reason}")
                    pil_img = Image.fromarray(cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB))
                    bedrock_result = self.bedrock.remove_background(pil_img, background_color)
                    
                    if bedrock_result.success and bedrock_result.image:
                        enhanced = cv2.cvtColor(np.array(bedrock_result.image), cv2.COLOR_RGB2BGR)
                        enhancements.append("ai_background_removal")
                        result.ai_used = True
                        total_ai_cost += bedrock_result.estimated_cost
                        result.processing_steps.append(ProcessingStep(
                            name="background_removal", method="ai", success=True,
                            latency_ms=bedrock_result.latency_ms, cost_usd=bedrock_result.estimated_cost,
                            details="Bedrock Titan"
                        ))
                    else:
                        # Fallback to local
                        logger.warning(f"   ⚠️ AI BG removal failed: {bedrock_result.error}, falling back to local")
                        enhanced, bg_removed = self._remove_background_grabcut(enhanced, background_color)
                        if bg_removed:
                            enhancements.append("local_background_removal_fallback")
                else:
                    # Use local GrabCut
                    logger.info("")
                    logger.info("💻 USING LOCAL: Background Removal (GrabCut)")
                    logger.info(f"   Reason: {routing.reason if routing else 'Default'}")
                    enhanced, bg_removed = self._remove_background_grabcut(enhanced, background_color)
                    if bg_removed:
                        enhancements.append("local_background_removal")
                        result.processing_steps.append(ProcessingStep(
                            name="background_removal", method="local", success=bg_removed,
                            latency_ms=int((time.time() - step_start) * 1000),
                            details="GrabCut algorithm"
                        ))
                
                result.background_removed = True
                step_time = int((time.time() - step_start) * 1000)
                logger.info(f"   ✅ Background Removal Complete | Time: {step_time}ms")
            
            # --- 3b. Apply Mode-Specific Enhancements ---
            if mode == EnhancementMode.AUTO:
                enhanced, mode_enhancements, mode_steps = self._auto_enhance_with_routing(
                    enhanced, metrics, routing_decisions
                )
                enhancements.extend(mode_enhancements)
                result.processing_steps.extend(mode_steps)
                for step in mode_steps:
                    if step.method == "ai":
                        result.ai_used = True
                        total_ai_cost += step.cost_usd
                        
            elif mode == EnhancementMode.LIGHT_CORRECTION:
                step_start = time.time()
                routing = self._get_routing_decision(routing_decisions, "lighting")
                
                if routing and routing.use_ai:
                    logger.info("   🔄 Lighting Correction: Using AI (Bedrock)...")
                    pil_img = Image.fromarray(cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB))
                    bedrock_result = self.bedrock.fix_lighting(pil_img)
                    
                    if bedrock_result.success and bedrock_result.image:
                        enhanced = cv2.cvtColor(np.array(bedrock_result.image), cv2.COLOR_RGB2BGR)
                        enhancements.append("ai_lighting_correction")
                        result.ai_used = True
                        total_ai_cost += bedrock_result.estimated_cost
                    else:
                        enhanced = self._light_correction(enhanced)
                        enhanced = self._color_balance(enhanced)
                        enhancements.extend(["local_light_correction_fallback", "color_balance"])
                else:
                    logger.info("   🔄 Lighting Correction: Using LOCAL (CLAHE)...")
                    enhanced = self._light_correction(enhanced)
                    enhancements.append("local_light_correction")
                    enhanced = self._color_balance(enhanced)
                    enhancements.append("color_balance")
                
                logger.info(f"   ✅ Lighting Correction Complete | Time: {int((time.time() - step_start) * 1000)}ms")
                
            elif mode == EnhancementMode.UPSCALE_DENOISE:
                step_start = time.time()
                enhanced = self._smart_denoise(enhanced)
                enhancements.append("denoise")
                
                routing = self._get_routing_decision(routing_decisions, "upscaling")
                if routing and routing.use_ai:
                    logger.info("   🔄 Upscaling: Using AI (Bedrock Titan)...")
                    pil_img = Image.fromarray(cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB))
                    bedrock_result = self.bedrock.upscale_image(pil_img)
                    
                    if bedrock_result.success and bedrock_result.image:
                        enhanced = cv2.cvtColor(np.array(bedrock_result.image), cv2.COLOR_RGB2BGR)
                        enhancements.append("ai_upscale_titan")
                        result.ai_used = True
                        total_ai_cost += bedrock_result.estimated_cost
                    else:
                        enhanced = self._upscale_lanczos(enhanced, self.params.upscale_factor)
                        enhancements.append("local_upscale_fallback")
                else:
                    logger.info("   🔄 Upscaling: Using LOCAL (Lanczos)...")
                    enhanced = self._upscale_lanczos(enhanced, self.params.upscale_factor)
                    enhancements.append(f"local_upscale_{self.params.upscale_factor}x")
                
                logger.info(f"   ✅ Upscale+Denoise Complete | Time: {int((time.time() - step_start) * 1000)}ms")
                
            elif mode == EnhancementMode.STANDARDIZE:
                config = standardization_config or StandardizationConfig(background_color=background_color)
                enhanced = self.standardize_image(enhanced, config)
                enhancements.append("standardization")
                standardize = False
                
            elif mode == EnhancementMode.SHARPEN:
                enhanced = self._smart_sharpen(enhanced)
                enhancements.append("smart_sharpen")
                
            elif mode == EnhancementMode.DENOISE:
                enhanced = self._smart_denoise(enhanced)
                enhancements.append("denoise")
                
            elif mode == EnhancementMode.UPSCALE:
                routing = self._get_routing_decision(routing_decisions, "upscaling")
                if routing and routing.use_ai:
                    pil_img = Image.fromarray(cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB))
                    bedrock_result = self.bedrock.upscale_image(pil_img)
                    if bedrock_result.success and bedrock_result.image:
                        enhanced = cv2.cvtColor(np.array(bedrock_result.image), cv2.COLOR_RGB2BGR)
                        enhancements.append("ai_upscale_titan")
                        result.ai_used = True
                        total_ai_cost += bedrock_result.estimated_cost
                    else:
                        enhanced = self._upscale_lanczos(enhanced, self.params.upscale_factor)
                        enhancements.append("local_upscale_fallback")
                else:
                    enhanced = self._upscale_lanczos(enhanced, self.params.upscale_factor)
                    enhancements.append(f"local_upscale_{self.params.upscale_factor}x")
                    
            elif mode == EnhancementMode.OPTIMIZE:
                enhancements.append("optimize_only")
                
            elif mode == EnhancementMode.FULL:
                enhanced, full_enhancements, full_steps = self._full_enhance_with_routing(
                    enhanced, metrics, routing_decisions, remove_background, background_color
                )
                enhancements.extend(full_enhancements)
                result.processing_steps.extend(full_steps)
                for step in full_steps:
                    if step.method == "ai":
                        result.ai_used = True
                        total_ai_cost += step.cost_usd
            
            # ========== STEP 4: STANDARDIZATION ==========
            if standardize:
                step_start = time.time()
                logger.info("📐 STEP 4: Standardization...")
                config = standardization_config or StandardizationConfig(background_color=background_color)
                # If AI was used (especially upscaling), preserve the high resolution
                # Only standardize aspect ratio/padding, but don't downscale
                enhanced = self.standardize_image(enhanced, config, maintain_resolution=result.ai_used)
                enhancements.append("standardization")
                logger.info(f"   ✅ Standardization Complete | Time: {int((time.time() - step_start) * 1000)}ms")
            
            # ========== STEP 5: OPTIMIZATION ==========
            step_start = time.time()
            logger.info("💾 STEP 5: Output Optimization...")
            enhanced_pil = Image.fromarray(cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB))
            
            target_kb = target_size_kb or self.params.target_max_size_kb
            optimized_bytes = self._optimize_output(enhanced_pil, output_format, target_kb)
            
            opt_time = int((time.time() - step_start) * 1000)
            logger.info(f"   ✅ Optimization Complete | Final Size: {len(optimized_bytes)/1024:.1f}KB | Time: {opt_time}ms")
            
            # ========== FINALIZE RESULT ==========
            result.success = True
            result.enhanced_image = enhanced
            result.enhanced_pil = enhanced_pil
            result.enhanced_size_bytes = len(optimized_bytes)
            result.enhanced_dimensions = (enhanced.shape[1], enhanced.shape[0])
            result.enhancements_applied = enhancements
            result.total_ai_cost = total_ai_cost
            result.processing_time_ms = int((time.time() - start_time) * 1000)
            
            logger.info("=" * 70)
            logger.info(f"✅ ENHANCEMENT COMPLETE")
            logger.info(f"   Total Time: {result.processing_time_ms}ms")
            logger.info(f"   Size: {result.original_size_bytes/1024:.1f}KB → {result.enhanced_size_bytes/1024:.1f}KB "
                       f"({result.size_reduction_percent:+.1f}%)")
            logger.info(f"   Dimensions: {result.original_dimensions} → {result.enhanced_dimensions}")
            logger.info(f"   AI Used: {result.ai_used} | AI Cost: ${result.total_ai_cost:.4f}")
            logger.info(f"   Enhancements: {', '.join(enhancements)}")
            logger.info("=" * 70)
            
        except Exception as e:
            logger.error(f"❌ ENHANCEMENT FAILED: {str(e)}", exc_info=True)
            result.error = str(e)
            result.processing_time_ms = int((time.time() - start_time) * 1000)
        
        return result
    
    def _auto_enhance_with_routing(
        self, 
        img: np.ndarray, 
        metrics: Dict, 
        routing: List[RoutingDecision]
    ) -> Tuple[np.ndarray, List[str], List[ProcessingStep]]:
        """Auto enhance with smart routing"""
        enhancements = []
        steps = []
        
        logger.info("   🤖 AUTO Mode: Applying smart enhancements based on analysis...")
        
        # Denoise if needed
        if metrics["noise_level"] > 15:
            step_start = time.time()
            img = self._smart_denoise(img, strength=min(metrics["noise_level"] / 2, 20))
            enhancements.append("denoise")
            steps.append(ProcessingStep(
                name="denoise", method="local", success=True,
                latency_ms=int((time.time() - step_start) * 1000),
                details=f"Noise level was {metrics['noise_level']:.1f}"
            ))
        
        # Fix brightness
        if metrics["brightness"] < 80:
            step_start = time.time()
            img = self._adjust_brightness(img, factor=1.2)
            enhancements.append("brightness_boost")
            steps.append(ProcessingStep(
                name="brightness", method="local", success=True,
                latency_ms=int((time.time() - step_start) * 1000)
            ))
        elif metrics["brightness"] > 200:
            step_start = time.time()
            img = self._adjust_brightness(img, factor=0.85)
            enhancements.append("brightness_reduce")
            steps.append(ProcessingStep(
                name="brightness", method="local", success=True,
                latency_ms=int((time.time() - step_start) * 1000)
            ))
        
        # Fix contrast
        if metrics["contrast"] < 40:
            step_start = time.time()
            img = self._apply_clahe(img)
            enhancements.append("contrast_clahe")
            steps.append(ProcessingStep(
                name="contrast", method="local", success=True,
                latency_ms=int((time.time() - step_start) * 1000)
            ))
        
        # Sharpen if blurry
        if metrics["blur_score"] < 200:
            step_start = time.time()
            strength = 2.0 if metrics["blur_score"] < 100 else 1.5
            img = self._smart_sharpen(img, strength=strength)
            enhancements.append("smart_sharpen")
            steps.append(ProcessingStep(
                name="sharpen", method="local", success=True,
                latency_ms=int((time.time() - step_start) * 1000),
                details=f"Blur score was {metrics['blur_score']:.1f}"
            ))
        
        # Final touch
        step_start = time.time()
        img = self._final_touch(img)
        enhancements.append("final_touch")
        steps.append(ProcessingStep(
            name="final_touch", method="local", success=True,
            latency_ms=int((time.time() - step_start) * 1000)
        ))
        
        return img, enhancements, steps
    
    def _full_enhance_with_routing(
        self,
        img: np.ndarray,
        metrics: Dict,
        routing: List[RoutingDecision],
        remove_bg: bool,
        bg_color: Tuple[int, int, int]
    ) -> Tuple[np.ndarray, List[str], List[ProcessingStep]]:
        """Full enhancement pipeline with smart routing"""
        enhancements = []
        steps = []
        
        logger.info("   🔥 FULL Mode: Applying complete enhancement pipeline...")
        
        # 1. Background removal (only if requested)
        if remove_bg:
            step_start = time.time()
            bg_routing = self._get_routing_decision(routing, "background_removal")
            if bg_routing and bg_routing.use_ai:
                pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
                result = self.bedrock.remove_background(pil_img, bg_color)
                if result.success:
                    img = cv2.cvtColor(np.array(result.image), cv2.COLOR_RGB2BGR)
                    enhancements.append("ai_bg_removal")
                    steps.append(ProcessingStep(
                        name="background_removal", method="ai", success=True,
                        latency_ms=result.latency_ms, cost_usd=result.estimated_cost
                    ))
                else:
                    img, _ = self._remove_background_grabcut(img, bg_color)
                    enhancements.append("local_bg_removal_fallback")
            else:
                img, _ = self._remove_background_grabcut(img, bg_color)
                enhancements.append("local_bg_removal")
                steps.append(ProcessingStep(
                    name="background_removal", method="local", success=True,
                    latency_ms=int((time.time() - step_start) * 1000)
                ))
        
        # 2. Light/Color correction
        step_start = time.time()
        light_routing = self._get_routing_decision(routing, "lighting")
        if light_routing and light_routing.use_ai:
            pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            result = self.bedrock.fix_lighting(pil_img)
            if result.success:
                img = cv2.cvtColor(np.array(result.image), cv2.COLOR_RGB2BGR)
                enhancements.append("ai_lighting")
                steps.append(ProcessingStep(
                    name="lighting", method="ai", success=True,
                    latency_ms=result.latency_ms, cost_usd=result.estimated_cost
                ))
            else:
                img = self._light_correction(img)
                img = self._color_balance(img)
                enhancements.extend(["local_light_fallback", "color_balance"])
        else:
            img = self._light_correction(img)
            img = self._color_balance(img)
            enhancements.extend(["local_light_correction", "color_balance"])
            steps.append(ProcessingStep(
                name="lighting", method="local", success=True,
                latency_ms=int((time.time() - step_start) * 1000)
            ))
        
        # 3. Denoise
        step_start = time.time()
        img = self._smart_denoise(img)
        enhancements.append("denoise")
        steps.append(ProcessingStep(
            name="denoise", method="local", success=True,
            latency_ms=int((time.time() - step_start) * 1000)
        ))
        
        # 4. Upscale if needed
        h, w = img.shape[:2]
        if min(h, w) < self.config.standardization.min_dimension:
            step_start = time.time()
            upscale_routing = self._get_routing_decision(routing, "upscaling")
            if upscale_routing and upscale_routing.use_ai:
                pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
                result = self.bedrock.upscale_image(pil_img)
                if result.success:
                    img = cv2.cvtColor(np.array(result.image), cv2.COLOR_RGB2BGR)
                    enhancements.append("ai_upscale")
                    steps.append(ProcessingStep(
                        name="upscale", method="ai", success=True,
                        latency_ms=result.latency_ms, cost_usd=result.estimated_cost
                    ))
                    
                    # Skip subsequent local enhancements (Sharpen, Contrast) as AI result is already polished
                    return img, enhancements, steps
                else:
                    img = self._upscale_lanczos(img, self.params.upscale_factor)
                    enhancements.append("local_upscale_fallback")
            else:
                img = self._upscale_lanczos(img, self.params.upscale_factor)
                enhancements.append("local_upscale")
                steps.append(ProcessingStep(
                    name="upscale", method="local", success=True,
                    latency_ms=int((time.time() - step_start) * 1000)
                ))
        
        # 5. Sharpen
        step_start = time.time()
        img = self._smart_sharpen(img)
        enhancements.append("sharpen")
        steps.append(ProcessingStep(
            name="sharpen", method="local", success=True,
            latency_ms=int((time.time() - step_start) * 1000)
        ))
        
        # 6. Contrast
        step_start = time.time()
        img = self._apply_clahe(img)
        enhancements.append("contrast_enhance")
        steps.append(ProcessingStep(
            name="contrast", method="local", success=True,
            latency_ms=int((time.time() - step_start) * 1000)
        ))
        
        return img, enhancements, steps
    
    # ==================== LOCAL PROCESSING METHODS ====================
    
    def _load_image(self, image_input: Union[str, Path, bytes, np.ndarray, Image.Image]) -> Tuple[np.ndarray, Optional[bytes]]:
        """Load image from various input types"""
        original_bytes = None
        
        if isinstance(image_input, (str, Path)):
            path = Path(image_input)
            if not path.exists():
                raise ValueError(f"Image file not found: {path}")
            with open(path, 'rb') as f:
                original_bytes = f.read()
            if len(original_bytes) == 0:
                raise ValueError(f"Image file is empty: {path}")
            img = cv2.imread(str(path))
            if img is None:
                raise ValueError(f"Could not load image from {path}. File may be corrupted or unsupported format.")
                
        elif isinstance(image_input, bytes):
            if len(image_input) == 0:
                raise ValueError("Image bytes are empty")
            original_bytes = image_input
            
            # Detect format from magic bytes
            magic_bytes = image_input[:20]
            
            # Check for AVIF format
            if b'ftypavif' in magic_bytes or b'ftypavis' in magic_bytes:
                try:
                    # Try pillow-avif-plugin if available
                    import pillow_avif
                    pil_img = Image.open(io.BytesIO(image_input))
                    img = cv2.cvtColor(np.array(pil_img.convert('RGB')), cv2.COLOR_RGB2BGR)
                    logger.info("   ℹ️ Decoded AVIF image using pillow-avif-plugin")
                except ImportError:
                    raise ValueError(
                        "AVIF image format detected but pillow-avif-plugin is not installed.\n"
                        "Install it with: pip install pillow-avif-plugin"
                    )
                except Exception as e:
                    raise ValueError(f"Failed to decode AVIF image: {str(e)}")
            else:
                # Try cv2.imdecode first for common formats
                nparr = np.frombuffer(image_input, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                # If cv2 fails, try PIL as fallback
                if img is None:
                    try:
                        pil_img = Image.open(io.BytesIO(image_input))
                        img = cv2.cvtColor(np.array(pil_img.convert('RGB')), cv2.COLOR_RGB2BGR)
                        logger.info("   ℹ️ Used PIL fallback for image decoding")
                    except Exception as e:
                        content_preview = magic_bytes.decode('utf-8', errors='ignore')[:50]
                        raise ValueError(
                            f"Could not decode image bytes. Size: {len(image_input)} bytes.\n"
                            f"Magic bytes: {magic_bytes.hex()[:40]}\n"
                            f"Content preview: {content_preview}\n"
                            f"Supported formats: JPEG, PNG, GIF, WEBP, BMP, TIFF.\n"
                            f"For AVIF support, install: pip install pillow-avif-plugin"
                        )
                
        elif isinstance(image_input, np.ndarray):
            img = image_input
            if len(img.shape) == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            elif len(img.shape) != 3 or img.shape[2] not in [3, 4]:
                raise ValueError(f"Invalid numpy array shape: {img.shape}. Expected (H, W, 3) or (H, W, 4)")
            _, encoded = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            original_bytes = encoded.tobytes()
                
        elif isinstance(image_input, Image.Image):
            img = cv2.cvtColor(np.array(image_input.convert('RGB')), cv2.COLOR_RGB2BGR)
            buffer = io.BytesIO()
            image_input.save(buffer, format='JPEG', quality=95)
            original_bytes = buffer.getvalue()
            
        else:
            raise TypeError(f"Unsupported image input type: {type(image_input)}")
        
        return img, original_bytes
    
    def _estimate_noise(self, gray: np.ndarray) -> float:
        """Estimate noise level using Laplacian"""
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        return float(np.median(np.abs(laplacian)) / 0.6745)
    
    def _adjust_brightness(self, img: np.ndarray, factor: float = 1.0) -> np.ndarray:
        """Adjust image brightness"""
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 2] = np.clip(hsv[:, :, 2] * factor, 0, 255)
        return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    
    def _enhance_colors(self, img: np.ndarray) -> np.ndarray:
        """Subtle color enhancement"""
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
        lab[:, :, 1] = np.clip(lab[:, :, 1] * 1.05, 0, 255)  # Boost a channel
        lab[:, :, 2] = np.clip(lab[:, :, 2] * 1.05, 0, 255)  # Boost b channel
        return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR)
    
    def _final_touch(self, img: np.ndarray) -> np.ndarray:
        """Final subtle enhancement"""
        # Slight saturation boost
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.05, 0, 255)
        return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    
    def _light_correction(self, img: np.ndarray) -> np.ndarray:
        """Light correction - fix exposure and brightness"""
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        mean_brightness = np.mean(l)
        target_brightness = 128
        
        if mean_brightness < 80:
            adjustment = min(50, (target_brightness - mean_brightness) * 0.5)
            l = cv2.add(l, int(adjustment))
        elif mean_brightness > 180:
            adjustment = min(50, (mean_brightness - target_brightness) * 0.5)
            l = cv2.subtract(l, int(adjustment))
        
        clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
        l = clahe.apply(l)
        
        lab = cv2.merge([l, a, b])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    
    def _color_balance(self, img: np.ndarray) -> np.ndarray:
        """Gray-world white balance"""
        result = img.copy().astype(np.float32)
        
        avg_b = np.mean(result[:, :, 0])
        avg_g = np.mean(result[:, :, 1])
        avg_r = np.mean(result[:, :, 2])
        avg_gray = (avg_b + avg_g + avg_r) / 3
        
        if avg_b > 0:
            result[:, :, 0] = result[:, :, 0] * (avg_gray / avg_b)
        if avg_g > 0:
            result[:, :, 1] = result[:, :, 1] * (avg_gray / avg_g)
        if avg_r > 0:
            result[:, :, 2] = result[:, :, 2] * (avg_gray / avg_r)
        
        return np.clip(result, 0, 255).astype(np.uint8)
    
    def _smart_sharpen(self, img: np.ndarray, strength: float = None) -> np.ndarray:
        """Smart sharpening using unsharp mask"""
        strength = strength or self.params.sharpen_strength
        blurred = cv2.GaussianBlur(img, (0, 0), self.params.sharpen_radius)
        sharpened = cv2.addWeighted(img, 1 + strength, blurred, -strength, 0)
        return np.clip(sharpened, 0, 255).astype(np.uint8)
    
    def _smart_denoise(self, img: np.ndarray, strength: float = None) -> np.ndarray:
        """Bilateral filter denoising"""
        strength = int(strength or self.params.denoise_strength)
        return cv2.bilateralFilter(img, d=9, sigmaColor=strength * 2, sigmaSpace=strength)
    
    def _apply_clahe(self, img: np.ndarray) -> np.ndarray:
        """Apply CLAHE contrast enhancement"""
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        clahe = cv2.createCLAHE(
            clipLimit=self.params.clahe_clip_limit,
            tileGridSize=self.params.clahe_grid_size
        )
        l = clahe.apply(l)
        
        lab = cv2.merge([l, a, b])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    
    def _upscale_lanczos(self, img: np.ndarray, factor: float = 2.0) -> np.ndarray:
        """Upscale using Lanczos interpolation"""
        h, w = img.shape[:2]
        new_w = int(w * factor)
        new_h = int(h * factor)
        
        max_dim = self.params.upscale_max_dimension
        if max(new_w, new_h) > max_dim:
            scale = max_dim / max(new_w, new_h)
            new_w = int(new_w * scale)
            new_h = int(new_h * scale)
        
        upscaled = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        return self._smart_sharpen(upscaled, strength=0.5)
    
    def _remove_background_grabcut(
        self,
        img: np.ndarray,
        background_color: Tuple[int, int, int] = (255, 255, 255)
    ) -> Tuple[np.ndarray, bool]:
        """Remove background using GrabCut"""
        try:
            h, w = img.shape[:2]
            mask = np.zeros((h, w), np.uint8)
            margin = int(min(h, w) * 0.02)
            rect = (margin, margin, w - 2*margin, h - 2*margin)
            
            bgd_model = np.zeros((1, 65), np.float64)
            fgd_model = np.zeros((1, 65), np.float64)
            
            cv2.grabCut(img, mask, rect, bgd_model, fgd_model, 5, cv2.GC_INIT_WITH_RECT)
            mask2 = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')
            
            kernel = np.ones((3, 3), np.uint8)
            mask2 = cv2.morphologyEx(mask2, cv2.MORPH_CLOSE, kernel, iterations=2)
            mask2 = cv2.morphologyEx(mask2, cv2.MORPH_OPEN, kernel, iterations=1)
            
            mask_blur = cv2.GaussianBlur(mask2.astype(float), (5, 5), 0)
            
            bg_color_bgr = (background_color[2], background_color[1], background_color[0])
            background = np.full(img.shape, bg_color_bgr, dtype=np.uint8)
            
            mask_3ch = np.stack([mask_blur] * 3, axis=-1)
            result = (img * mask_3ch + background * (1 - mask_3ch)).astype(np.uint8)
            
            return result, True
        except Exception as e:
            logger.warning(f"GrabCut failed: {e}")
            return img, False
    
    def detect_background_complexity(self, img: np.ndarray) -> float:
        """Detect background complexity (0-1 scale)"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        
        edges = cv2.Canny(gray, 50, 150)
        border_width = int(min(h, w) * 0.15)
        
        border_mask = np.zeros((h, w), dtype=np.uint8)
        border_mask[:border_width, :] = 255
        border_mask[-border_width:, :] = 255
        border_mask[:, :border_width] = 255
        border_mask[:, -border_width:] = 255
        
        border_edges = cv2.bitwise_and(edges, border_mask)
        border_edge_count = np.count_nonzero(border_edges)
        border_pixel_count = np.count_nonzero(border_mask)
        
        border_pixels = gray[border_mask > 0]
        variance = np.std(border_pixels) / 255.0
        
        edge_ratio = border_edge_count / max(border_pixel_count, 1)
        complexity = (edge_ratio * 0.5 + variance * 0.5)
        
        return min(1.0, complexity * 3)
    
    def standardize_image(
        self, 
        img: np.ndarray, 
        config: Optional[StandardizationConfig] = None,
        maintain_resolution: bool = False
    ) -> np.ndarray:
        """Standardize image dimensions"""
        config = config or StandardizationConfig()
        h, w = img.shape[:2]
        
        if config.target_width and config.target_height:
            target_w, target_h = config.target_width, config.target_height
        else:
            if min(w, h) < config.min_dimension:
                scale = config.min_dimension / min(w, h)
                target_w = int(w * scale)
                target_h = int(h * scale)
                target_w = int(w * scale)
                target_h = int(h * scale)
            elif max(w, h) > config.max_dimension and not maintain_resolution:
                scale = config.max_dimension / max(w, h)
                target_w = int(w * scale)
                target_h = int(h * scale)
            elif maintain_resolution and max(w, h) > config.max_dimension:
                 # If maintaining resolution, keep dimensions but ensuring padding logic works
                 # We will set target to current dims (or slightly larger for padding)
                 # Actually, standardization usually implies fixed box. 
                 # If maintain_resolution is True, we define the "box" as the current image size 
                 # plus padding, essentially ignoring max_dimension cap.
                 target_w, target_h = w, h
            else:
                target_w, target_h = w, h
        
        padding = int(min(target_w, target_h) * config.padding_percent / 100)
        content_w = target_w - 2 * padding
        content_h = target_h - 2 * padding
        
        scale = min(content_w / w, content_h / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        
        bg_color_bgr = (config.background_color[2], config.background_color[1], config.background_color[0])
        canvas = np.full((target_h, target_w, 3), bg_color_bgr, dtype=np.uint8)
        
        x_offset = (target_w - new_w) // 2
        y_offset = (target_h - new_h) // 2
        canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
        
        return canvas
    
    def _optimize_output(self, img: Image.Image, format: str, target_size_kb: int) -> bytes:
        """Optimize output file size"""
        format = format.upper()
        buffer = io.BytesIO()
        
        if format == "JPEG":
            quality = self.params.jpeg_quality
            img.save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)
        elif format == "PNG":
            img.save(buffer, format="PNG", optimize=True, compress_level=self.params.png_compression)
        elif format == "WEBP":
            img.save(buffer, format="WEBP", quality=self.params.webp_quality, method=6)
        else:
            img.save(buffer, format="JPEG", quality=92)
        
        result = buffer.getvalue()
        
        if format in ["JPEG", "WEBP"] and len(result) > target_size_kb * 1024:
            quality = 90
            while len(result) > target_size_kb * 1024 and quality > self.params.min_quality:
                buffer = io.BytesIO()
                if format == "JPEG":
                    img.save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)
                else:
                    img.save(buffer, format="WEBP", quality=quality, method=6)
                result = buffer.getvalue()
                quality -= 5
        
        return result
    
    def get_enhanced_bytes(self, result: EnhancementResult, format: str = "JPEG", target_size_kb: Optional[int] = None) -> bytes:
        """Get enhanced image as bytes"""
        if not result.success or result.enhanced_pil is None:
            raise ValueError("Cannot get bytes from failed result")
        return self._optimize_output(result.enhanced_pil, format, target_size_kb or self.params.target_max_size_kb)
    
    def save_enhanced(self, result: EnhancementResult, output_path: Union[str, Path], format: str = "JPEG", target_size_kb: Optional[int] = None) -> int:
        """Save enhanced image to file"""
        if not result.success or result.enhanced_pil is None:
            raise ValueError("Cannot save failed result")
        
        optimized = self._optimize_output(result.enhanced_pil, format, target_size_kb or self.params.target_max_size_kb)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'wb') as f:
            f.write(optimized)
        
        return len(optimized)


def enhance_image(
    image_input: Union[str, Path, bytes, np.ndarray, Image.Image],
    mode: EnhancementMode = EnhancementMode.AUTO,
    output_format: str = "JPEG",
    target_size_kb: Optional[int] = None
) -> EnhancementResult:
    """Quick function to enhance an image"""
    enhancer = ImageEnhancer()
    return enhancer.enhance(image_input, mode, output_format, target_size_kb)
