"""
Gemini API service for image enhancement
Handles API calls to Google's Gemini Vision model for image processing
"""
import os
import base64
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class GeminiEnhancementResult:
    """Result from Gemini enhancement"""
    success: bool
    enhanced_image_base64: Optional[str] = None
    original_image_base64: Optional[str] = None
    prompt: Optional[str] = None
    usage_metadata: Optional[Dict[str, Any]] = None
    model_version: Optional[str] = None
    response_id: Optional[str] = None
    error: Optional[str] = None
    
    def get_image_bytes(self) -> bytes:
        """Decode base64 enhanced image to bytes"""
        if not self.enhanced_image_base64:
            raise ValueError("Enhanced image is not available")
        return base64.b64decode(self.enhanced_image_base64)

class GeminiService:
    """Service for calling Google Gemini API for image enhancement"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Gemini service
        
        Args:
            api_key: Google API key for Gemini. If not provided, reads from GEMINI_API_KEY env var
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.model = "gemini-3-pro-image-preview"
        self.timeout = 120  # 2 minutes timeout for image processing
    
    def enhance_image(
        self,
        image_bytes: bytes,
        enhancement_prompt: Optional[str] = None,
        mime_type: str = "image/jpeg"
    ) -> GeminiEnhancementResult:
        """
        Enhance image using Gemini API
        
        Args:
            image_bytes: Image data in bytes
            enhancement_prompt: Custom prompt for enhancement. If not provided, uses default
            mime_type: MIME type of the image (default: image/jpeg)
        
        Returns:
            GeminiEnhancementResult with enhanced image or error
        """
        try:
            if not image_bytes:
                return GeminiEnhancementResult(
                    success=False,
                    error="Image bytes cannot be empty"
                )
            
            # Encode image to base64
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            
            # Use default prompt if not provided
            if enhancement_prompt is None:
                enhancement_prompt = (
                    "true color reproduction, neutral white balance, "
                    "color consistency across product, enhance the quality"
                )
            
            # Build request payload
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": enhancement_prompt
                            },
                            {
                                "inline_data": {
                                    "mime_type": mime_type,
                                    "data": image_base64
                                }
                            }
                        ]
                    }
                ]
            }
            
            # Make API call
            url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"
            
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
            
            if response.status_code != 200:
                error_msg = f"Gemini API error {response.status_code}: {response.text}"
                logger.error(error_msg)
                return GeminiEnhancementResult(success=False, error=error_msg)
            
            response_data = response.json()
            
            # Extract enhanced image from response
            try:
                candidates = response_data.get("candidates", [])
                if not candidates:
                    return GeminiEnhancementResult(
                        success=False,
                        error="No candidates in Gemini response"
                    )
                
                candidate = candidates[0]
                content = candidate.get("content", {})
                parts = content.get("parts", [])
                
                if not parts:
                    return GeminiEnhancementResult(
                        success=False,
                        error="No parts in Gemini response content"
                    )
                
                part = parts[0]
                inline_data = part.get("inlineData", {})
                enhanced_image_base64 = inline_data.get("data")
                
                if not enhanced_image_base64:
                    return GeminiEnhancementResult(
                        success=False,
                        error="No image data in Gemini response"
                    )
                
                # Success
                return GeminiEnhancementResult(
                    success=True,
                    enhanced_image_base64=enhanced_image_base64,
                    original_image_base64=image_base64,
                    prompt=enhancement_prompt,
                    usage_metadata=response_data.get("usageMetadata"),
                    model_version=response_data.get("modelVersion"),
                    response_id=response_data.get("responseId")
                )
            
            except (KeyError, IndexError, TypeError) as e:
                error_msg = f"Failed to parse Gemini response: {str(e)}"
                logger.error(error_msg)
                logger.debug(f"Response data: {response_data}")
                return GeminiEnhancementResult(success=False, error=error_msg)
        
        except Exception as e:
            error_msg = f"Gemini enhancement failed: {str(e)}"
            logger.error(error_msg)
            return GeminiEnhancementResult(success=False, error=error_msg)
    
    def enhance_image_from_base64(
        self,
        image_base64: str,
        enhancement_prompt: Optional[str] = None,
        mime_type: str = "image/jpeg"
    ) -> GeminiEnhancementResult:
        """
        Enhance image from base64-encoded data
        
        Args:
            image_base64: Base64-encoded image data
            enhancement_prompt: Custom prompt for enhancement
            mime_type: MIME type of the image
        
        Returns:
            GeminiEnhancementResult with enhanced image or error
        """
        try:
            # Decode base64 to bytes
            image_bytes = base64.b64decode(image_base64)
            return self.enhance_image(image_bytes, enhancement_prompt, mime_type)
        except Exception as e:
            error_msg = f"Failed to decode base64 image: {str(e)}"
            logger.error(error_msg)
            return GeminiEnhancementResult(success=False, error=error_msg)
