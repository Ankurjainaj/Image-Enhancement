"""
Image Quality Assessment Module
Analyzes images and provides quality scores
Supports both fast CPU metrics and optional BRISQUE (requires PyTorch)

BRISQUE Requirements:
- pip install pyiqa torch torchvision
- Set ENABLE_BRISQUE=true in .env
"""
import logging
import os
import time
from typing import Dict, Any, Optional, Tuple, Union
from pathlib import Path
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from .config import get_config, QualityTier, QualityThresholds

logger = logging.getLogger(__name__)

# Check BRISQUE availability at module load
_BRISQUE_AVAILABLE = None
_BRISQUE_ENABLED = os.getenv("ENABLE_BRISQUE", "false").lower() in ("true", "1", "yes")


@dataclass
class QualityReport:
    """Complete quality assessment report"""
    blur_score: float = 0.0
    brightness: float = 0.0
    contrast: float = 0.0
    noise_level: float = 0.0
    brisque_score: Optional[float] = None
    edge_density: float = 0.0
    color_variance: float = 0.0
    width: int = 0
    height: int = 0
    file_size_bytes: int = 0
    format: str = ""
    sharpness_score: float = 0.0
    brightness_score: float = 0.0
    contrast_score: float = 0.0
    resolution_score: float = 0.0
    overall_score: float = 0.0
    quality_tier: QualityTier = QualityTier.ACCEPTABLE
    needs_enhancement: bool = False
    issues: list = None
    recommendations: list = None
    
    def __post_init__(self):
        if self.issues is None:
            self.issues = []
        if self.recommendations is None:
            self.recommendations = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "blur_score": round(self.blur_score, 2),
            "brightness": round(self.brightness, 2),
            "contrast": round(self.contrast, 2),
            "noise_level": round(self.noise_level, 2),
            "brisque_score": round(self.brisque_score, 2) if self.brisque_score else None,
            "edge_density": round(self.edge_density, 4),
            "width": self.width,
            "height": self.height,
            "file_size_kb": round(self.file_size_bytes / 1024, 2),
            "sharpness_score": round(self.sharpness_score, 2),
            "brightness_score": round(self.brightness_score, 2),
            "contrast_score": round(self.contrast_score, 2),
            "resolution_score": round(self.resolution_score, 2),
            "overall_score": round(self.overall_score, 2),
            "quality_tier": self.quality_tier.value,
            "needs_enhancement": self.needs_enhancement,
            "issues": self.issues,
            "recommendations": self.recommendations,
        }


class QualityAssessor:
    """
    Assesses image quality using multiple metrics
    
    Metrics calculated:
    - Blur score (Laplacian variance)
    - Brightness (mean grayscale value)
    - Contrast (std deviation of grayscale)
    - Noise level (median absolute Laplacian)
    - Edge density (Canny edge ratio)
    - Color variance (HSV hue std)
    - BRISQUE score (optional, requires pyiqa)
    """
    
    def __init__(self, thresholds: Optional[QualityThresholds] = None):
        self.thresholds = thresholds or get_config().quality
        self._brisque_model = None
        self._brisque_available = None
        
        logger.info("=" * 80)
        logger.info("🔍 QualityAssessor Initialized")
        logger.info("=" * 80)
        logger.info(f"   ENABLE_BRISQUE env: {_BRISQUE_ENABLED}")
        logger.info(f"   Thresholds:")
        logger.info(f"      Blur - Excellent: {self.thresholds.blur_excellent}")
        logger.info(f"      Blur - Acceptable: {self.thresholds.blur_acceptable}")
        logger.info(f"      Blur - Poor: {self.thresholds.blur_poor}")
        logger.info(f"      Resolution - Excellent: {self.thresholds.resolution_excellent}px")
        logger.info(f"      Resolution - Acceptable: {self.thresholds.resolution_acceptable}px")
        logger.info("=" * 80)
    
    def assess(
        self,
        image_input: Union[str, Path, bytes, np.ndarray, Image.Image],
        include_brisque: bool = True
    ) -> QualityReport:
        """
        Perform full quality assessment on an image
        
        Args:
            image_input: Image to assess (path, bytes, numpy array, or PIL Image)
            include_brisque: Whether to include BRISQUE score (if available)
            
        Returns:
            QualityReport with all metrics
        """
        assess_id = f"QA-{int(time.time()*1000)}"
        start_time = time.time()
        
        logger.info("=" * 80)
        logger.info(f"📊 QUALITY ASSESSMENT START | ID: {assess_id}")
        logger.info("=" * 80)
        
        report = QualityReport()
        
        try:
            # Load image
            logger.info("   📷 Loading image...")
            load_start = time.time()
            img, file_size = self._load_image(image_input)
            load_time = (time.time() - load_start) * 1000
            
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            report.height, report.width = img.shape[:2]
            report.file_size_bytes = file_size
            
            logger.info(f"      ✅ Loaded in {load_time:.1f}ms")
            logger.info(f"      Dimensions: {report.width}x{report.height}")
            logger.info(f"      File size: {file_size / 1024:.1f} KB")
            logger.info(f"      Channels: {img.shape[2] if len(img.shape) > 2 else 1}")
            
            # Calculate all metrics with detailed logging
            logger.info("-" * 80)
            logger.info("   📏 CALCULATING METRICS")
            logger.info("-" * 80)
            
            # Blur score
            metric_start = time.time()
            report.blur_score = self._calculate_blur_score(gray)
            logger.info(f"   🔹 Blur Score: {report.blur_score:.2f}")
            logger.info(f"      Threshold (excellent): {self.thresholds.blur_excellent}")
            logger.info(f"      Threshold (acceptable): {self.thresholds.blur_acceptable}")
            is_blurry = report.blur_score < self.thresholds.blur_acceptable
            logger.info(f"      Assessment: {'⚠️ BLURRY' if is_blurry else '✅ Sharp'}")
            
            # Brightness
            report.brightness = float(np.mean(gray))
            logger.info(f"   🔹 Brightness: {report.brightness:.2f}")
            logger.info(f"      Range: 0 (black) - 255 (white)")
            logger.info(f"      Optimal: ~130")
            is_dark = report.brightness < 80
            is_bright = report.brightness > 200
            if is_dark:
                logger.info(f"      Assessment: ⚠️ TOO DARK")
            elif is_bright:
                logger.info(f"      Assessment: ⚠️ OVEREXPOSED")
            else:
                logger.info(f"      Assessment: ✅ Good exposure")
            
            # Contrast
            report.contrast = float(np.std(gray))
            logger.info(f"   🔹 Contrast: {report.contrast:.2f}")
            logger.info(f"      Good contrast: >40")
            is_low_contrast = report.contrast < 40
            logger.info(f"      Assessment: {'⚠️ LOW CONTRAST' if is_low_contrast else '✅ Good contrast'}")
            
            # Noise level
            report.noise_level = self._estimate_noise(gray)
            logger.info(f"   🔹 Noise Level: {report.noise_level:.2f}")
            logger.info(f"      Low noise: <10, High noise: >20")
            is_noisy = report.noise_level > 20
            logger.info(f"      Assessment: {'⚠️ NOISY' if is_noisy else '✅ Low noise'}")
            
            # Edge density
            report.edge_density = self._calculate_edge_density(gray)
            logger.info(f"   🔹 Edge Density: {report.edge_density:.4f}")
            logger.info(f"      Indicates detail level (higher = more detail)")
            
            # Color variance
            report.color_variance = self._calculate_color_variance(img)
            logger.info(f"   🔹 Color Variance: {report.color_variance:.2f}")
            
            metrics_time = (time.time() - metric_start) * 1000
            logger.info(f"   ⏱️ Metrics calculated in {metrics_time:.1f}ms")
            
            # BRISQUE Score (optional)
            logger.info("-" * 80)
            logger.info("   🧠 BRISQUE ASSESSMENT")
            logger.info("-" * 80)
            
            if include_brisque and _BRISQUE_ENABLED:
                logger.info(f"      ENABLE_BRISQUE: True")
                if self._is_brisque_available():
                    logger.info(f"      pyiqa library: Available")
                    try:
                        brisque_start = time.time()
                        report.brisque_score = self._calculate_brisque(img)
                        brisque_time = (time.time() - brisque_start) * 1000
                        
                        logger.info(f"   🔹 BRISQUE Score: {report.brisque_score:.2f}")
                        logger.info(f"      Range: 0 (best) - 100+ (worst)")
                        logger.info(f"      Good quality: <30")
                        logger.info(f"      Calculated in: {brisque_time:.1f}ms")
                        
                        if report.brisque_score < 30:
                            logger.info(f"      Assessment: ✅ Good perceptual quality")
                        elif report.brisque_score < 50:
                            logger.info(f"      Assessment: ⚠️ Moderate quality")
                        else:
                            logger.info(f"      Assessment: ❌ Poor perceptual quality")
                            
                    except Exception as e:
                        logger.warning(f"      ❌ BRISQUE calculation failed: {e}")
                        report.brisque_score = None
                else:
                    logger.warning(f"      ❌ pyiqa library NOT available")
                    logger.warning(f"      💡 Install with: pip install pyiqa torch torchvision")
                    report.brisque_score = None
            else:
                if not _BRISQUE_ENABLED:
                    logger.info(f"      BRISQUE disabled (ENABLE_BRISQUE={_BRISQUE_ENABLED})")
                else:
                    logger.info(f"      BRISQUE skipped (include_brisque=False)")
                report.brisque_score = None
            
            # Calculate normalized scores
            logger.info("-" * 80)
            logger.info("   📈 NORMALIZED SCORES (0-100)")
            logger.info("-" * 80)
            
            report.sharpness_score = self._blur_to_score(report.blur_score)
            report.brightness_score = self._brightness_to_score(report.brightness)
            report.contrast_score = self._contrast_to_score(report.contrast)
            report.resolution_score = self._resolution_to_score(report.width, report.height)
            
            logger.info(f"   🔹 Sharpness Score: {report.sharpness_score:.1f}/100")
            logger.info(f"   🔹 Brightness Score: {report.brightness_score:.1f}/100")
            logger.info(f"   🔹 Contrast Score: {report.contrast_score:.1f}/100")
            logger.info(f"   🔹 Resolution Score: {report.resolution_score:.1f}/100")
            
            # Calculate overall score
            report.overall_score = self._calculate_overall_score(report)
            report.quality_tier = self._determine_tier(report.overall_score)
            
            logger.info("-" * 80)
            logger.info(f"   🎯 OVERALL SCORE: {report.overall_score:.1f}/100")
            logger.info(f"   🏆 QUALITY TIER: {report.quality_tier.value}")
            logger.info("-" * 80)
            
            # Analyze issues
            report.issues, report.recommendations = self._analyze_issues(report)
            report.needs_enhancement = len(report.issues) > 0 or report.overall_score < 70
            
            if report.issues:
                logger.info("   ⚠️ ISSUES DETECTED:")
                for issue in report.issues:
                    logger.info(f"      - {issue}")
            else:
                logger.info("   ✅ No significant issues detected")
            
            if report.recommendations:
                logger.info("   💡 RECOMMENDATIONS:")
                for rec in report.recommendations:
                    logger.info(f"      - {rec}")
            
            total_time = (time.time() - start_time) * 1000
            logger.info("-" * 80)
            logger.info(f"   ⏱️ Total assessment time: {total_time:.1f}ms")
            logger.info(f"   📊 Needs enhancement: {report.needs_enhancement}")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error("=" * 80)
            logger.error(f"   ❌ QUALITY ASSESSMENT FAILED")
            logger.error(f"      Error: {str(e)}")
            logger.error("=" * 80)
            import traceback
            logger.error(traceback.format_exc())
            report.issues.append(f"Assessment error: {str(e)}")
        
        return report
    
    def quick_assess(self, image_input: Union[str, Path, bytes, np.ndarray, Image.Image]) -> Dict[str, Any]:
        """Quick assessment with minimal metrics"""
        try:
            img, file_size = self._load_image(image_input)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            blur_score = self._calculate_blur_score(gray)
            brightness = float(np.mean(gray))
            h, w = img.shape[:2]
            
            is_blurry = blur_score < self.thresholds.blur_acceptable
            is_dark = brightness < 80
            is_bright = brightness > 200
            is_low_res = min(w, h) < self.thresholds.resolution_acceptable
            
            return {
                "blur_score": round(blur_score, 2),
                "brightness": round(brightness, 2),
                "width": w,
                "height": h,
                "file_size_kb": round(file_size / 1024, 2),
                "is_blurry": is_blurry,
                "is_dark": is_dark,
                "is_overexposed": is_bright,
                "is_low_res": is_low_res,
                "needs_enhancement": is_blurry or is_dark or is_bright or is_low_res,
            }
        except Exception as e:
            return {"error": str(e), "needs_enhancement": True}
    
    def _load_image(self, image_input) -> Tuple[np.ndarray, int]:
        """Load image and return (opencv image, file size)"""
        file_size = 0
        
        if isinstance(image_input, (str, Path)):
            path = Path(image_input)
            file_size = path.stat().st_size
            img = cv2.imread(str(path))
            if img is None:
                raise ValueError(f"Could not load image: {path}")
        elif isinstance(image_input, bytes):
            file_size = len(image_input)
            nparr = np.frombuffer(image_input, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("Could not decode image bytes")
        elif isinstance(image_input, np.ndarray):
            img = image_input
            if len(img.shape) == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            _, encoded = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            file_size = len(encoded)
        elif isinstance(image_input, Image.Image):
            img = cv2.cvtColor(np.array(image_input), cv2.COLOR_RGB2BGR)
            _, encoded = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            file_size = len(encoded)
        else:
            raise TypeError(f"Unsupported input type: {type(image_input)}")
        
        return img, file_size
    
    def _calculate_blur_score(self, gray: np.ndarray) -> float:
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())
    
    def _estimate_noise(self, gray: np.ndarray) -> float:
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        return float(np.median(np.abs(laplacian)) / 0.6745)
    
    def _calculate_edge_density(self, gray: np.ndarray) -> float:
        edges = cv2.Canny(gray, 100, 200)
        return np.count_nonzero(edges) / (edges.shape[0] * edges.shape[1])
    
    def _calculate_color_variance(self, img: np.ndarray) -> float:
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        return float(np.std(hsv[:, :, 0]))
    
    def _is_brisque_available(self) -> bool:
        """Check if BRISQUE (pyiqa) is available"""
        global _BRISQUE_AVAILABLE
        
        if _BRISQUE_AVAILABLE is not None:
            return _BRISQUE_AVAILABLE
        
        logger.info("   🔍 Checking BRISQUE availability...")
        try:
            import torch
            logger.info(f"      PyTorch: ✅ Available (version {torch.__version__})")
            logger.info(f"      CUDA: {'✅ Available' if torch.cuda.is_available() else '❌ Not available (CPU mode)'}")
            
            import pyiqa
            logger.info(f"      pyiqa: ✅ Available")
            
            _BRISQUE_AVAILABLE = True
            logger.info(f"      BRISQUE: ✅ Ready to use")
            
        except ImportError as e:
            _BRISQUE_AVAILABLE = False
            logger.warning(f"      ❌ BRISQUE not available: {e}")
            logger.warning(f"      💡 To enable: pip install pyiqa torch torchvision")
        
        return _BRISQUE_AVAILABLE
    
    def _calculate_brisque(self, img: np.ndarray) -> float:
        if self._brisque_model is None:
            import torch
            import pyiqa
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self._brisque_model = pyiqa.create_metric('brisque', device=device)
        
        import torch
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_tensor = torch.from_numpy(img_rgb).permute(2, 0, 1).unsqueeze(0).float() / 255.0
        
        with torch.no_grad():
            score = self._brisque_model(img_tensor).item()
        return score
    
    def _blur_to_score(self, blur: float) -> float:
        if blur >= self.thresholds.blur_excellent:
            return 100.0
        elif blur >= self.thresholds.blur_acceptable:
            ratio = (blur - self.thresholds.blur_acceptable) / (self.thresholds.blur_excellent - self.thresholds.blur_acceptable)
            return 70 + (ratio * 30)
        elif blur >= self.thresholds.blur_poor:
            ratio = (blur - self.thresholds.blur_poor) / (self.thresholds.blur_acceptable - self.thresholds.blur_poor)
            return 40 + (ratio * 30)
        else:
            return max(0, blur / self.thresholds.blur_poor * 40)
    
    def _brightness_to_score(self, brightness: float) -> float:
        optimal = 130
        deviation = abs(brightness - optimal)
        if deviation < 20:
            return 100.0
        elif deviation < 50:
            return 100 - (deviation - 20)
        elif deviation < 80:
            return 70 - (deviation - 50) * 0.5
        else:
            return max(0, 55 - (deviation - 80) * 0.5)
    
    def _contrast_to_score(self, contrast: float) -> float:
        if contrast >= 60:
            return 100.0
        elif contrast >= 40:
            return 70 + ((contrast - 40) / 20) * 30
        elif contrast >= 25:
            return 50 + ((contrast - 25) / 15) * 20
        else:
            return max(0, (contrast / 25) * 50)
    
    def _resolution_to_score(self, width: int, height: int) -> float:
        min_dim = min(width, height)
        if min_dim >= self.thresholds.resolution_excellent:
            return 100.0
        elif min_dim >= self.thresholds.resolution_good:
            ratio = (min_dim - self.thresholds.resolution_good) / (self.thresholds.resolution_excellent - self.thresholds.resolution_good)
            return 80 + (ratio * 20)
        elif min_dim >= self.thresholds.resolution_acceptable:
            ratio = (min_dim - self.thresholds.resolution_acceptable) / (self.thresholds.resolution_good - self.thresholds.resolution_acceptable)
            return 60 + (ratio * 20)
        elif min_dim >= self.thresholds.resolution_poor:
            ratio = (min_dim - self.thresholds.resolution_poor) / (self.thresholds.resolution_acceptable - self.thresholds.resolution_poor)
            return 40 + (ratio * 20)
        else:
            return max(0, (min_dim / self.thresholds.resolution_poor) * 40)
    
    def _calculate_overall_score(self, report: QualityReport) -> float:
        weights = {
            'sharpness': 0.35,
            'brightness': 0.15,
            'contrast': 0.20,
            'resolution': 0.30,
        }
        
        score = (
            report.sharpness_score * weights['sharpness'] +
            report.brightness_score * weights['brightness'] +
            report.contrast_score * weights['contrast'] +
            report.resolution_score * weights['resolution']
        )
        
        if report.brisque_score is not None:
            brisque_factor = max(0, 1 - (report.brisque_score / 100))
            score = score * 0.7 + (brisque_factor * 100) * 0.3
        
        return min(100, max(0, score))
    
    def _determine_tier(self, score: float) -> QualityTier:
        if score >= 80:
            return QualityTier.EXCELLENT
        elif score >= 60:
            return QualityTier.GOOD
        elif score >= 40:
            return QualityTier.ACCEPTABLE
        elif score >= 20:
            return QualityTier.POOR
        else:
            return QualityTier.VERY_POOR
    
    def _analyze_issues(self, report: QualityReport) -> Tuple[list, list]:
        issues = []
        recommendations = []
        
        if report.sharpness_score < 50:
            issues.append("Image is blurry")
            recommendations.append("Apply sharpening enhancement")
        elif report.sharpness_score < 70:
            issues.append("Image could be sharper")
            recommendations.append("Light sharpening recommended")
        
        if report.brightness_score < 50:
            if report.brightness < 100:
                issues.append("Image is too dark")
                recommendations.append("Increase brightness")
            else:
                issues.append("Image is overexposed")
                recommendations.append("Reduce brightness")
        
        if report.contrast_score < 50:
            issues.append("Low contrast")
            recommendations.append("Apply CLAHE contrast enhancement")
        
        if report.resolution_score < 60:
            issues.append("Low resolution")
            recommendations.append("Consider upscaling")
        
        if report.noise_level > 20:
            issues.append("Image has noise")
            recommendations.append("Apply denoising")
        
        if report.file_size_bytes > 1024 * 1024:
            issues.append("Large file size (>1MB)")
            recommendations.append("Optimize compression")
        
        return issues, recommendations


def assess_image(image_input, include_brisque: bool = True) -> QualityReport:
    """Convenience function for quick assessment"""
    assessor = QualityAssessor()
    return assessor.assess(image_input, include_brisque)
