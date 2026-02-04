# 🖼️ Image Enhancement Pipeline

**Medikabazaar Hackathon Project** - A production-ready image enhancement service optimized for B2B e-commerce marketplace.

## 🎯 Key Outcomes (Per Business Requirements)

- ✅ **Background Removal & Replacement** - Clean white background for professional look
- ✅ **Light & Colour Correction** - AI-powered exposure and brightness adjustment
- ✅ **Image Upscaling & Denoising** - Super Resolution without pixelation
- ✅ **Standardization & Consistency** - Uniform sizing, aspect ratios, padding
- ✅ **Human-in-the-Loop QC** - Review workflow for high-value items
- ✅ **Low file size** - Smart compression maintains quality
- ✅ **Text clarity on zoom** - Lanczos upscaling preserves details

## 📊 Architecture Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   CloudFront    │────▶│   Import URLs   │────▶│   MySQL DB      │
│   (Source)      │     │   (Scripts)     │     │  (product_images)│
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
┌─────────────────┐     ┌─────────────────┐              │
│   Dashboard     │◀────│   FastAPI       │◀─────────────┤
│   (Streamlit)   │     │   (Real-time)   │              │
└─────────────────┘     └────────┬────────┘              │
                                 │                       │
                        ┌────────▼────────┐     ┌────────▼────────┐
                        │     Kafka       │────▶│     Worker      │
                        │   (Jobs Queue)  │     │  (Enhancement)  │
                        └─────────────────┘     └─────────────────┘
                                                         │
                        ┌─────────────────┐              │
                        │     Redis       │◀─────────────┘
                        │  (Job Status)   │
                        └─────────────────┘
```

## 🗄️ Database Schema (MySQL)

### Core Tables

| Table | Purpose |
|-------|---------|
| `product_groups` | Product categories/groups |
| `skus` | Individual SKUs with image counts |
| `product_images` | Main table: `product_group_id`, `sku_id`, `image_url`, `enhanced_image_url` |
| `image_metrics` | Quality scores before/after enhancement |
| `processing_jobs` | Batch job tracking |
| `enhancement_configs` | Per-category/SKU enhancement settings |
| `qc_review_logs` | Human QC review history |

### Key Fields in `product_images`

```sql
product_group_id    -- Product group identifier
sku_id              -- SKU identifier  
image_url           -- Original CloudFront URL
enhanced_image_url  -- Enhanced image URL
status              -- pending/processing/completed/failed
qc_status           -- pending/auto_approved/needs_review/approved/rejected
```

## 🚀 Quick Start

### 1. Setup MySQL Database

```bash
# Create database and tables
mysql -u root -p < scripts/init_mysql.sql
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your MySQL credentials
```

### 3. Install & Run

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database (from Python)
python -c "from src.database import init_db; init_db()"

# Start API server
uvicorn api.main:app --reload --port 8000

# Start dashboard (new terminal)
streamlit run dashboard/app.py

# Start Kafka worker (new terminal)
python workers/kafka_worker.py
```

### Using Docker

```bash
docker-compose up -d

# Access:
# - API: http://localhost:8000
# - Dashboard: http://localhost:8501
# - API Docs: http://localhost:8000/docs
```

## 📥 Import CloudFront URLs

### CSV Format (Recommended)

```csv
product_group_id,sku_id,image_url,image_type
PG-MEDICAL-001,MED-SKU-001,https://cloudfront.net/img1.jpg,primary
PG-MEDICAL-001,MED-SKU-001,https://cloudfront.net/img1-side.jpg,side
```

### Import Command

```bash
# Generate sample CSV template
python scripts/import_urls.py sample --output my_urls.csv

# Import from CSV
python scripts/import_urls.py csv my_urls.csv \
    --url-column image_url \
    --sku-column sku_id \
    --product-group-column product_group_id

# Import from JSON
python scripts/import_urls.py json images.json
```

### JSON Format

```json
[
  {
    "product_group_id": "PG-001",
    "sku_id": "SKU-001",
    "image_url": "https://cloudfront.net/image1.jpg",
    "image_type": "primary"
  }
]
```

## 🔌 API Endpoints

### Real-time Enhancement

```bash
# Enhance from URL with background removal
curl -X POST "http://localhost:8000/api/v1/enhance/url" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-cloudfront.net/image.jpg",
    "mode": "auto",
    "remove_background": true,
    "target_size_kb": 500
  }'

# Upload and enhance
curl -X POST "http://localhost:8000/api/v1/enhance/upload" \
  -F "file=@product.jpg" \
  -F "mode=full" \
  -F "remove_background=true"
```

### Batch Processing

```bash
# Import URLs
curl -X POST "http://localhost:8000/api/v1/import" \
  -H "Content-Type: application/json" \
  -d '{
    "images": [
      {"sku_id": "SKU-001", "image_url": "https://...", "product_group_id": "PG-001"}
    ]
  }'

# Create batch job
curl -X POST "http://localhost:8000/api/v1/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "sku_id": "SKU-001",
    "mode": "full",
    "remove_background": true
  }'

# Check job status
curl "http://localhost:8000/api/v1/batch/{job_id}"
```

### QC Review (Human-in-the-Loop)

```bash
# Get images needing QC review
curl "http://localhost:8000/api/v1/qc/pending"

# Approve/reject image
curl -X POST "http://localhost:8000/api/v1/qc/{image_id}/review" \
  -d '{"status": "approved", "reviewer_id": "user123", "notes": "LGTM"}'
```

## 🎛️ Enhancement Features

### Available Enhancements

| Feature | Description | Default |
|---------|-------------|---------|
| Background Removal | Remove cluttered backgrounds | ✅ Enabled |
| White Background | Replace with #FFFFFF | ✅ Enabled |
| Upscaling | Lanczos super-resolution | When < 1500px |
| Denoising | Bilateral filter | ✅ Enabled |
| Sharpening | Unsharp mask for text | ✅ Enabled |
| Color Correction | Auto brightness/contrast | ✅ Enabled |
| Standardization | Uniform sizing & padding | Optional |

### Enhancement Modes

| Mode | Description |
|------|-------------|
| `auto` | Analyzes image, applies optimal enhancements |
| `full` | Applies all enhancements |
| `sharpen` | Focus on text/edge clarity |
| `denoise` | Reduce noise while preserving details |
| `upscale` | Increase resolution (2x default) |
| `optimize` | Compress without enhancement |

## 📊 QC Workflow

```
Image Enhanced
     │
     ▼
┌────────────────┐
│ QC Score Check │
└───────┬────────┘
        │
   ┌────┴────┐
   │         │
   ▼         ▼
Score>75  Score≤75
   │         │
   ▼         ▼
AUTO_      NEEDS_
APPROVED   REVIEW
             │
             ▼
      Human Review
             │
      ┌──────┴──────┐
      │             │
      ▼             ▼
  APPROVED     REJECTED
                   │
                   ▼
               REWORK
```

## 💰 Cost Analysis

### Self-Hosted vs. Cloud Solutions

| Solution | Cost for 50K images |
|----------|---------------------|
| This solution (EC2) | ~$5-10 |
| ImageKit e-upscale | ~$500+ |
| AWS Bedrock | ~$1,500+ |
| Manual editing | ~$5,000+ |

**Savings: 95%+**

## 📁 Project Structure

```
image-enhancer-v2/
├── src/                    # Core library
│   ├── config.py          # Configuration
│   ├── database.py        # MySQL models & repositories
│   ├── enhancer.py        # Enhancement engine (+ background removal)
│   ├── quality.py         # Quality assessment
│   └── kafka_service.py   # Kafka producer/consumer
├── api/                    # FastAPI REST API
├── workers/               # Kafka workers
├── dashboard/             # Streamlit UI
├── scripts/               
│   ├── import_urls.py     # URL importer
│   └── init_mysql.sql     # Database schema
├── docker-compose.yml     
└── requirements.txt       
```

## 🔧 Configuration

### MySQL Connection

```bash
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=image_enhancer
```

### Enhancement Defaults

```bash
DEFAULT_BACKGROUND_COLOR=#FFFFFF
TARGET_MIN_DIMENSION=1500
AUTO_APPROVE_THRESHOLD=75.0
ENABLE_BACKGROUND_REMOVAL=true
```

## 📝 License

MIT License - Medikabazaar Hackathon 2024
