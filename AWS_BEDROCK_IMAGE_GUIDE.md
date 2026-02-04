# AWS Bedrock Image Enhancement Guide

## 🚨 CRITICAL: Understanding Model Types

### TEXT UNDERSTANDING Models (CANNOT Generate Images)
These models can **ONLY ANALYZE** images - they CANNOT generate, modify, or enhance images:

- ✅ `amazon.nova-pro-v1:0` - Can analyze and describe images
- ✅ `amazon.nova-lite-v1:0` - Can analyze images (lighter version)
- ✅ `amazon.nova-2-lite-v1:0` - Can analyze images
- ✅ `amazon.nova-micro-v1:0` - Can analyze images (smallest)

**What they CAN do:**
- Describe image content
- Answer questions about images
- Extract text from images (OCR)
- Classify images
- Detect objects in images

**What they CANNOT do:**
- ❌ Remove backgrounds
- ❌ Upscale images
- ❌ Fix lighting
- ❌ Generate new images
- ❌ Modify existing images
- ❌ Apply filters or effects

### IMAGE GENERATION Models (CAN Generate/Modify Images)
These models can generate and manipulate images:

- 🎨 `amazon.nova-canvas-v1:0` - **BEST for image generation/manipulation**
- 🎨 `amazon.titan-image-generator-v2:0` - Legacy image generator
- 🎨 `amazon.titan-image-generator-v1` - Older version

**What they CAN do:**
- ✅ Remove backgrounds
- ✅ Replace backgrounds
- ✅ Inpainting (fill masked areas)
- ✅ Outpainting (extend images)
- ✅ Generate variations
- ✅ Fix lighting/colors
- ✅ Upscale images
- ✅ Generate images from text

---

## 🔑 Getting Access to Image Generation Models

### Current Situation
You currently have access to **TEXT UNDERSTANDING** models only. To use AWS Bedrock for image enhancement, you need access to **IMAGE GENERATION** models.

### How to Request Access

1. **Go to AWS Bedrock Console**
   ```
   https://console.aws.amazon.com/bedrock/
   ```

2. **Navigate to Model Access**
   - Click "Model access" in the left sidebar
   - Or go directly: https://console.aws.amazon.com/bedrock/home#/modelaccess

3. **Request Access to Image Models**
   - Find `Amazon Nova Canvas` - **RECOMMENDED**
   - Find `Amazon Titan Image Generator V2` - Alternative
   - Click "Request model access" or "Modify model access"
   - Select the models you want
   - Submit the request

4. **Wait for Approval**
   - Usually instant for most models
   - Some models may require business justification
   - Check your email for approval notification

5. **Verify Access**
   ```bash
   aws bedrock list-foundation-models --region us-east-1 \
     --by-output-modality IMAGE
   ```

---

## 💡 Image Enhancement with AWS Bedrock

### Available Operations (with IMAGE GENERATION models)

#### 1. Background Removal
```python
from src.bedrock_service import create_bedrock_service, Operation
from PIL import Image

service = create_bedrock_service()
image = Image.open("product.jpg")

# Remove background
result = service.invoke(
    operation=Operation.BACKGROUND_REMOVAL,
    image=image,
    model_id="amazon.nova-canvas-v1:0"
)

if result.success:
    result.image.save("product_no_bg.png")
    print(f"Cost: ${result.estimated_cost:.4f}")
```

#### 2. Background Replacement
```python
# Remove background and add white background
result = service.invoke(
    operation=Operation.BACKGROUND_REMOVAL,
    image=image,
    model_id="amazon.nova-canvas-v1:0",
    params={"background_color": (255, 255, 255)}
)
```

#### 3. Lighting Correction
```python
# Fix lighting issues
result = service.fix_lighting(
    image=image,
    prompt="professional studio lighting, perfect exposure, balanced colors",
    model_id="amazon.nova-canvas-v1:0"
)
```

#### 4. Image Upscaling
```python
# Upscale image with quality enhancement
result = service.upscale_image(
    image=image,
    mode="conservative",
    model_id="amazon.nova-canvas-v1:0"
)
```

#### 5. Image Variation (Enhancement)
```python
# Create enhanced variation
result = service.create_variation(
    image=image,
    prompt="ultra high quality, sharp details, professional product photo",
    similarity=0.85,  # High similarity = preserve original
    model_id="amazon.nova-canvas-v1:0"
)
```

#### 6. Inpainting (Fix Specific Areas)
```python
# Fix specific areas using mask
mask = Image.open("mask.png")  # White = areas to fix

result = service.inpaint(
    image=image,
    prompt="clean white background",
    mask_image=mask,
    model_id="amazon.nova-canvas-v1:0"
)

# Or use text-based masking
result = service.inpaint(
    image=image,
    prompt="remove watermark",
    mask_prompt="watermark in corner",
    model_id="amazon.nova-canvas-v1:0"
)
```

#### 7. Outpainting (Extend Image)
```python
# Extend image borders
result = service.invoke(
    operation=Operation.OUTPAINTING,
    image=image,
    model_id="amazon.nova-canvas-v1:0",
    params={
        "prompt": "seamless extension with white background",
        "mode": "DEFAULT"
    }
)
```

---

## 🎯 Recommended Workflow for Product Images

### Full Enhancement Pipeline
```python
from src.bedrock_service import create_bedrock_service, Operation
from PIL import Image

service = create_bedrock_service()
image = Image.open("product.jpg")

# Step 1: Remove background
print("Step 1: Removing background...")
result = service.remove_background(image)
if not result.success:
    print(f"Failed: {result.error}")
    exit()
image = result.image
print(f"Cost: ${result.estimated_cost:.4f}")

# Step 2: Fix lighting
print("Step 2: Fixing lighting...")
result = service.fix_lighting(
    image,
    prompt="professional studio lighting, perfect white balance"
)
if result.success:
    image = result.image
    print(f"Cost: ${result.estimated_cost:.4f}")

# Step 3: Upscale
print("Step 3: Upscaling...")
result = service.upscale_image(image, mode="conservative")
if result.success:
    image = result.image
    print(f"Cost: ${result.estimated_cost:.4f}")

# Save final result
image.save("product_enhanced.png")
print(f"Total cost: ${service.get_usage_stats()['daily_cost_usd']:.4f}")
```

---

## 💰 Cost Comparison

### Per Image Enhancement (Estimated)

| Operation | Nova Canvas | Titan V2 | Local (OpenCV) |
|-----------|-------------|----------|----------------|
| Background Removal | $0.04 | $0.01 | $0.00 |
| Lighting Fix | $0.04 | N/A | $0.00 |
| Upscaling | $0.04 | $0.01 | $0.00 |
| Full Pipeline | $0.12 | $0.03 | $0.00 |

### For 1,000 Images

| Solution | Cost | Quality | Speed |
|----------|------|---------|-------|
| AWS Bedrock (Nova Canvas) | $120 | ⭐⭐⭐⭐⭐ | Fast |
| AWS Bedrock (Titan V2) | $30 | ⭐⭐⭐⭐ | Fast |
| Local (OpenCV) | $0 | ⭐⭐⭐ | Very Fast |
| Manual Editing | $5,000+ | ⭐⭐⭐⭐⭐ | Very Slow |

---

## 🔧 Configuration

### Environment Variables
```bash
# Enable Bedrock
ENABLE_BEDROCK=true

# Set daily cost limit
MAX_DAILY_AI_COST=10.0

# Choose models (after getting access)
BEDROCK_BG_MODEL=amazon.nova-canvas-v1:0
BEDROCK_UPSCALE_MODEL=amazon.nova-canvas-v1:0
BEDROCK_LIGHTING_MODEL=amazon.nova-canvas-v1:0
BEDROCK_VARIATION_MODEL=amazon.nova-canvas-v1:0

# AWS Credentials
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
```

### Cost Controls
```python
# Set daily limit
service = create_bedrock_service()
service.config.hybrid.max_daily_cost = 10.0

# Check usage
stats = service.get_usage_stats()
print(f"Used: ${stats['daily_cost_usd']:.2f} / ${stats['max_cost']:.2f}")
print(f"Remaining: ${stats['remaining']:.2f}")

# Check if available
if not service.is_available():
    print("Bedrock unavailable - using local processing")
```

---

## 🚦 Current System Behavior

### Without Image Generation Access
```
User Request → Analyze Image → Route to AI or Local
                                      ↓
                              Try Bedrock Model
                                      ↓
                              ❌ Model cannot generate images
                                      ↓
                              Fall back to LOCAL processing
                                      ↓
                              Use OpenCV/PIL
```

### With Image Generation Access
```
User Request → Analyze Image → Route to AI or Local
                                      ↓
                              Try Bedrock Model
                                      ↓
                              ✅ Model generates enhanced image
                                      ↓
                              Return enhanced image
                                      ↓
                              Track cost
```

---

## 📊 Monitoring & Logging

### Check Model Calls
```python
# Get usage stats
stats = service.get_usage_stats()
print(stats)
# {
#   'daily_cost_usd': 0.12,
#   'calls': 3,
#   'max_cost': 10.0,
#   'remaining': 9.88,
#   'available': True
# }

# Cost by model
by_model = service.get_cost_by_model()
print(by_model)
# {'amazon.nova-canvas-v1:0': 0.12}

# Cost by operation
by_op = service.get_cost_by_operation()
print(by_op)
# {'background_removal': 0.04, 'lighting_fix': 0.04, 'upscale': 0.04}
```

### Log Output
```
============================================================
🤖 BedrockService Initialized (Multi-Model)
   Region: us-east-1
   BG: amazon.nova-canvas-v1:0
   Upscale: amazon.nova-canvas-v1:0
   Lighting: amazon.nova-canvas-v1:0
============================================================

============================================================
🚀 BEDROCK MODEL CALL
   Operation: background_removal
   Model: amazon.nova-canvas-v1:0
   Provider: amazon-nova
   Model Type: IMAGE GENERATION
   Estimated Cost: $0.0400
   Input Image: 1024x768 (RGB)
------------------------------------------------------------
📤 Sending request to Bedrock...
✅ SUCCESS
   Output Image: 1024x768 (RGBA)
   Latency: 2341ms
   Cost: $0.0400
💰 Running Total: $0.0400 (1 calls today)
============================================================
```

---

## ❓ FAQ

### Q: Can I use Nova Pro/Lite for image enhancement?
**A:** No. Nova Pro/Lite/Micro are TEXT UNDERSTANDING models. They can only analyze images, not generate or modify them.

### Q: Which model should I use for image enhancement?
**A:** `amazon.nova-canvas-v1:0` is the best choice for all image generation/manipulation tasks.

### Q: How do I get access to Nova Canvas?
**A:** Go to AWS Bedrock Console → Model Access → Request access to "Amazon Nova Canvas"

### Q: What if I don't have access to image generation models?
**A:** The system will automatically fall back to local OpenCV processing. It's free but lower quality.

### Q: How much does it cost?
**A:** ~$0.04 per operation with Nova Canvas. Full pipeline (3 operations) = ~$0.12 per image.

### Q: Can I set a daily budget?
**A:** Yes, set `MAX_DAILY_AI_COST` environment variable. Default is $10/day.

### Q: What happens when I hit the daily limit?
**A:** System automatically falls back to local processing for remaining images.

---

## 🔗 Resources

- **AWS Bedrock Console**: https://console.aws.amazon.com/bedrock/
- **Model Access**: https://console.aws.amazon.com/bedrock/home#/modelaccess
- **Nova Canvas Docs**: https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-nova-canvas.html
- **Titan Image Docs**: https://docs.aws.amazon.com/bedrock/latest/userguide/titan-image-models.html
- **Pricing**: https://aws.amazon.com/bedrock/pricing/

---

## ✅ Next Steps

1. **Request Model Access**
   - Go to AWS Bedrock Console
   - Request access to `amazon.nova-canvas-v1:0`
   - Wait for approval (usually instant)

2. **Update Configuration**
   ```bash
   # .env file
   ENABLE_BEDROCK=true
   BEDROCK_BG_MODEL=amazon.nova-canvas-v1:0
   ```

3. **Test Image Enhancement**
   ```bash
   python demo.py
   ```

4. **Monitor Costs**
   - Check logs for cost tracking
   - Review daily usage stats
   - Adjust MAX_DAILY_AI_COST as needed
