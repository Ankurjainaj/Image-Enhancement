#!/bin/bash
# Quick Start Script - Test All Fixes

echo "🚀 Image Enhancement Pipeline - Quick Start"
echo "==========================================="
echo ""

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️  Virtual environment not activated"
    echo "   Run: source enhance-multimodal/bin/activate"
    exit 1
fi

echo "✅ Virtual environment: $VIRTUAL_ENV"
echo ""

# Check dependencies
echo "📦 Checking dependencies..."
python -c "import pillow_avif" 2>/dev/null && echo "✅ AVIF support installed" || echo "❌ AVIF support missing (run: pip install pillow-avif-plugin)"
python -c "import streamlit" 2>/dev/null && echo "✅ Streamlit installed" || echo "❌ Streamlit missing"
python -c "import cv2" 2>/dev/null && echo "✅ OpenCV installed" || echo "❌ OpenCV missing"
echo ""

# Test image format detection
echo "🧪 Testing image format support..."
if [ -f "test_image_format.py" ]; then
    echo "   Test script available: python test_image_format.py <image-path>"
else
    echo "   ⚠️  test_image_format.py not found"
fi
echo ""

# Check services
echo "🔍 Checking services..."
echo ""
echo "1️⃣  API Server:"
echo "   Start: uvicorn api.main:app --reload --port 8000"
echo "   Docs:  http://localhost:8000/docs"
echo ""
echo "2️⃣  Dashboard:"
echo "   Start: streamlit run dashboard/app.py"
echo "   URL:   http://localhost:8501"
echo ""
echo "3️⃣  Database:"
echo "   Init:  python -c 'from src.database import init_db; init_db()'"
echo ""

# Quick test
echo "🎯 Quick Test Commands:"
echo ""
echo "# Test AVIF image:"
echo "python test_image_format.py your-image.avif"
echo ""
echo "# Run demo:"
echo "python demo.py"
echo ""
echo "# Test API (after starting server):"
echo "curl http://localhost:8000/health"
echo ""

echo "✨ All checks complete!"
echo ""
echo "📚 Documentation:"
echo "   - AVIF_SUPPORT.md - AVIF format details"
echo "   - FIXES_SUMMARY.md - All fixes applied"
echo "   - README.md - Full project documentation"
