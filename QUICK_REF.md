# 🚀 Quick Reference Card

## Start Services
```bash
# Terminal 1: API
uvicorn api.main:app --reload --port 8000

# Terminal 2: Dashboard  
streamlit run dashboard/app.py

# Terminal 3: Worker (optional)
python workers/kafka_worker.py
```

## Test Image
```bash
python test_image_format.py your-image.avif
```

## URLs
- Dashboard: http://localhost:8501
- API Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

## Bedrock Models (Available)
```
amazon.nova-pro-v1:0      # Best quality ($0.03)
amazon.nova-lite-v1:0     # Fast & cheap ($0.01)
amazon.nova-2-lite-v1:0   # Alternative lite ($0.01)
amazon.nova-micro-v1:0    # Ultra-cheap ($0.005)
```

## Environment Variables
```bash
BEDROCK_BG_MODEL=amazon.nova-pro-v1:0
BEDROCK_UPSCALE_MODEL=amazon.nova-lite-v1:0
BEDROCK_LIGHTING_MODEL=amazon.nova-pro-v1:0
MAX_DAILY_COST=100.0
```

## Supported Formats
✅ JPEG, PNG, GIF, WEBP, BMP, TIFF, **AVIF**

## Cost Per 1000 Images
- Recommended: ~$80
- Budget: ~$30
- Premium: ~$120

## Documentation
- `README.md` - Full guide
- `BEDROCK_MODELS.md` - Model config
- `AVIF_SUPPORT.md` - Format support
- `COMPLETE_SUMMARY.md` - Everything

## Quick Test
```bash
python demo.py
```
