#!/usr/bin/env python3
"""
Demo Script - Test Image Enhancement Pipeline
Run this to verify the enhancement engine works correctly
"""
import sys
import time
import io
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def create_test_image():
    """Create a simple test image with text"""
    from PIL import Image, ImageDraw, ImageFont
    
    # Create a 800x600 image with some text
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)
    
    # Add gradient background
    for y in range(600):
        r = int(255 - (y / 600) * 50)
        g = int(255 - (y / 600) * 30)
        b = int(255 - (y / 600) * 20)
        draw.line([(0, y), (800, y)], fill=(r, g, b))
    
    # Add text
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    except:
        font = ImageFont.load_default()
        small_font = font
    
    draw.text((50, 50), "Product Name", fill='black', font=font)
    draw.text((50, 120), "SKU: MED-12345", fill='gray', font=small_font)
    draw.text((50, 160), "Medical Supply Item", fill='darkgray', font=small_font)
    
    # Add a rectangle (product shape)
    draw.rectangle([300, 200, 700, 500], outline='black', width=2)
    draw.text((350, 300), "PRODUCT\nIMAGE", fill='lightgray', font=font)
    
    # Add some noise to simulate real product photo
    import random
    pixels = img.load()
    for _ in range(5000):
        x = random.randint(0, 799)
        y = random.randint(0, 599)
        r, g, b = pixels[x, y]
        noise = random.randint(-20, 20)
        pixels[x, y] = (
            max(0, min(255, r + noise)),
            max(0, min(255, g + noise)),
            max(0, min(255, b + noise))
        )
    
    return img


def main():
    print("=" * 60)
    print("🖼️  IMAGE ENHANCEMENT PIPELINE - DEMO")
    print("=" * 60)
    
    # Import components
    print("\n📦 Loading components...")
    from src.enhancer import ImageEnhancer
    from src.quality import QualityAssessor
    from src.database import init_db
    from src.logging_config import setup_logging
    
    # Setup logging
    setup_logging(level="INFO", log_to_file=True, log_to_console=True)
    
    # Initialize
    enhancer = ImageEnhancer()
    assessor = QualityAssessor()
    init_db()
    print("✅ Components loaded successfully")
    
    # Create test image
    print("\n🎨 Creating test image...")
    test_img = create_test_image()
    
    # Save original
    original_buffer = io.BytesIO()
    test_img.save(original_buffer, format='JPEG', quality=85)
    original_bytes = original_buffer.getvalue()
    print(f"✅ Test image created: {len(original_bytes)/1024:.1f} KB")
    
    # Assess original quality
    print("\n📊 Assessing original quality...")
    original_quality = assessor.quick_assess(original_bytes)
    print(f"   Blur Score: {original_quality['blur_score']:.1f}")
    print(f"   Brightness: {original_quality['brightness']:.1f}")
    print(f"   Resolution: {original_quality['width']}x{original_quality['height']}")
    print(f"   Needs Enhancement: {original_quality['needs_enhancement']}")
    
    # Test each enhancement mode
    print("\n🔧 Testing enhancement modes...")
    modes = ['auto', 'sharpen', 'denoise', 'optimize', 'full']
    results = []
    
    for mode in modes:
        print(f"\n   Testing mode: {mode}")
        start = time.time()
        
        from src.config import EnhancementMode
        result = enhancer.enhance(
            original_bytes,
            mode=EnhancementMode(mode),
            target_size_kb=300
        )
        
        elapsed = time.time() - start
        
        if result.success:
            enhanced_bytes = enhancer.get_enhanced_bytes(result, "JPEG", 300)
            enhanced_quality = assessor.quick_assess(enhanced_bytes)
            
            size_reduction = (1 - len(enhanced_bytes) / len(original_bytes)) * 100
            blur_improvement = ((enhanced_quality['blur_score'] - original_quality['blur_score']) 
                               / max(original_quality['blur_score'], 1)) * 100
            
            results.append({
                'mode': mode,
                'time_ms': int(elapsed * 1000),
                'size_reduction': size_reduction,
                'blur_improvement': blur_improvement,
                'enhancements': result.enhancements_applied
            })
            
            print(f"   ✅ Success: {elapsed*1000:.0f}ms | Size: -{size_reduction:.1f}% | Sharpness: +{blur_improvement:.1f}%")
        else:
            print(f"   ❌ Failed: {result.error}")
    
    # Summary
    print("\n" + "=" * 60)
    print("📈 RESULTS SUMMARY")
    print("=" * 60)
    print(f"{'Mode':<12} {'Time':<10} {'Size':<12} {'Sharpness':<12} {'Enhancements'}")
    print("-" * 60)
    
    for r in results:
        print(f"{r['mode']:<12} {r['time_ms']:>6}ms   {r['size_reduction']:>+6.1f}%     {r['blur_improvement']:>+6.1f}%     {len(r['enhancements'])} steps")
    
    # Save best result
    print("\n💾 Saving enhanced images...")
    output_dir = Path("data/demo_output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save original
    with open(output_dir / "original.jpg", "wb") as f:
        f.write(original_bytes)
    
    # Save enhanced (auto mode)
    from src.config import EnhancementMode
    result = enhancer.enhance(original_bytes, mode=EnhancementMode.AUTO, target_size_kb=300)
    if result.success:
        enhanced_bytes = enhancer.get_enhanced_bytes(result, "JPEG", 300)
        with open(output_dir / "enhanced_auto.jpg", "wb") as f:
            f.write(enhanced_bytes)
    
    print(f"✅ Images saved to: {output_dir.absolute()}")
    
    # API test info
    print("\n" + "=" * 60)
    print("🚀 NEXT STEPS")
    print("=" * 60)
    print("""
1. Start the API server:
   uvicorn api.main:app --reload --port 8000

2. Start the dashboard:
   streamlit run dashboard/app.py

3. Test the API:
   curl -X POST "http://localhost:8000/api/v1/enhance/url" \\
     -H "Content-Type: application/json" \\
     -d '{"url": "https://your-cloudfront-url/image.jpg"}'

4. Import your CloudFront URLs:
   python scripts/import_urls.py csv your_urls.csv --url-column url
""")
    
    print("\n✨ Demo completed successfully!")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
