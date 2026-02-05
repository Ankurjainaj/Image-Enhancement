"""
Streamlit Dashboard for Image Enhancement
Demo interface showing before/after comparisons and stats
"""
import io
import sys
import time
import base64
from pathlib import Path
from datetime import datetime
from typing import Optional

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from PIL import Image
# Add parent directory to path so `src` package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logging_config import setup_logging
import logging

# Initialize logging for dashboard
setup_logging(level="INFO")
logger = logging.getLogger(__name__)

from src.config import get_config, ProcessingStatus, EnhancementMode
from src.database import init_db, get_db, ImageRepository, ImageRecord
from src.enhancer import ImageEnhancer
from src.quality import QualityAssessor

# Page config
st.set_page_config(
    page_title="Image Enhancement Pipeline",
    page_icon="🖼️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize
config = get_config()
init_db()
enhancer = ImageEnhancer()
assessor = QualityAssessor()


# Custom CSS for Professional Demo Look
st.markdown("""
<style>
    /* Import Google Font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* Global styling */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Main header gradient */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem 2.5rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        box-shadow: 0 10px 40px rgba(102, 126, 234, 0.3);
    }
    
    .main-header h1 {
        color: white;
        font-size: 2.5rem;
        font-weight: 700;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    
    .main-header p {
        color: rgba(255, 255, 255, 0.9);
        font-size: 1.1rem;
        margin: 0.5rem 0 0 0;
    }
    
    /* Metric Cards with gradient backgrounds */
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.25);
        transition: transform 0.2s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
    }
    
    .success-metric {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        box-shadow: 0 4px 15px rgba(17, 153, 142, 0.25);
    }
    
    .warning-metric {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        box-shadow: 0 4px 15px rgba(240, 147, 251, 0.25);
    }
    
    .info-metric {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        box-shadow: 0 4px 15px rgba(79, 172, 254, 0.25);
    }
    
    /* Streamlit metric overrides */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
    }
    
    [data-testid="stMetricDelta"] {
        font-size: 0.9rem;
    }
    
    /* Remove default styling that conflicts with dark mode */
    div[data-testid="stMetric"] {
        background: transparent !important;
        padding: 1rem;
        border-radius: 12px;
        border: 1px solid rgba(128, 128, 128, 0.3);
        box-shadow: none;
    }
    
    [data-testid="stMetricLabel"] {
        color: inherit !important;
    }
    
    /* Comparison container */
    .comparison-container {
        display: flex;
        gap: 20px;
        justify-content: center;
    }
    
    /* Image comparison styling */
    .image-box {
        background: white;
        padding: 1rem;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        border: 1px solid #e9ecef;
    }
    
    .image-label {
        font-weight: 600;
        color: #495057;
        margin-bottom: 0.5rem;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background: transparent;
    }
    
    section[data-testid="stSidebar"] > div {
        padding-top: 2rem;
    }
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        border-radius: 8px;
        transition: all 0.2s ease;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
    }
    
    /* Download button */
    .stDownloadButton > button {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        color: white;
        border: none;
        font-weight: 600;
        box-shadow: 0 4px 15px rgba(17, 153, 142, 0.3);
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: rgba(128, 128, 128, 0.2);
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: 500;
        color: inherit;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white !important;
    }
    
    /* Footer */
    .footer {
        text-align: center;
        padding: 2rem;
        color: #6c757d;
        font-size: 0.9rem;
        border-top: 1px solid #e9ecef;
        margin-top: 3rem;
    }
    
    .footer a {
        color: #667eea;
        text-decoration: none;
        font-weight: 500;
    }
    
    /* Divider styling */
    hr {
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, #e9ecef, transparent);
        margin: 2rem 0;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


def get_image_from_url(url: str, timeout: int = 30) -> Optional[bytes]:
    """Fetch image from URL"""
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.content
    except Exception as e:
        st.error(f"Failed to fetch image: {e}")
        return None


def display_comparison(original_bytes: bytes, enhanced_bytes: bytes, metrics: dict):
    """Display before/after comparison"""
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📷 Original")
        st.image(original_bytes, use_container_width=True)
        st.caption(f"Size: {len(original_bytes)/1024:.1f} KB | "
                  f"Blur Score: {metrics.get('original_blur', 'N/A'):.1f}")
    
    with col2:
        st.subheader("✨ Enhanced")
        st.image(enhanced_bytes, use_container_width=True)
        st.caption(f"Size: {len(enhanced_bytes)/1024:.1f} KB | "
                  f"Blur Score: {metrics.get('enhanced_blur', 'N/A'):.1f}")


def render_kpi_cards():
    """Render KPI cards at the top"""
    db = get_db()
    try:
        stats = ImageRepository(db).get_statistics()
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric(
                "📊 Total Images",
                f"{stats['total_images']:,}",
                help="Total images in database"
            )
        
        with col2:
            processed = stats['status_counts'].get('completed', 0)
            st.metric(
                "✅ Processed",
                f"{processed:,}",
                delta=f"{processed/max(stats['total_images'], 1)*100:.1f}%"
            )
        
        with col3:
            pending = stats['status_counts'].get('pending', 0)
            st.metric(
                "⏳ Pending",
                f"{pending:,}",
                delta=None
            )
        
        with col4:
            improvement = stats.get('avg_quality_improvement')
            st.metric(
                "📈 Avg Improvement",
                f"+{improvement:.1f}%" if improvement else "N/A",
                help="Average quality improvement"
            )
        
        with col5:
            size_reduction = stats.get('avg_size_reduction')
            st.metric(
                "💾 Avg Size Reduction",
                f"-{size_reduction:.1f}%" if size_reduction else "N/A",
                help="Average file size reduction"
            )
    finally:
        db.close()


def render_quality_distribution():
    """Render quality distribution chart"""
    db = get_db()
    try:
        stats = ImageRepository(db).get_statistics()
        quality_dist = stats.get('quality_distribution', {})
        
        if quality_dist and any(quality_dist.values()):
            df = pd.DataFrame([
                {"Quality": k.replace("_", " ").title(), "Count": v}
                for k, v in quality_dist.items()
            ])
            
            colors = {
                "Excellent": "#10B981",
                "Good": "#3B82F6",
                "Acceptable": "#F59E0B",
                "Poor": "#EF4444",
                "Very Poor": "#7C3AED"
            }
            
            fig = px.pie(
                df, 
                values='Count', 
                names='Quality',
                color='Quality',
                color_discrete_map=colors,
                hole=0.4
            )
            fig.update_layout(
                title="Quality Distribution (Original Images)",
                showlegend=True
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No quality data available yet. Process some images first!")
    finally:
        db.close()


def render_recent_images():
    """Render recently processed images"""
    db = get_db()
    try:
        images = db.query(ImageRecord).filter(
            ImageRecord.status == ProcessingStatus.COMPLETED.value
        ).order_by(ImageRecord.processed_at.desc()).limit(10).all()
        
        if images:
            st.subheader("🕐 Recently Processed")
            
            for img in images:
                with st.expander(f"Image: {img.id[:8]}... | {img.processed_at.strftime('%Y-%m-%d %H:%M') if img.processed_at else 'N/A'}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**Original URL:**")
                        st.code(img.image_url[:100] + "..." if len(img.image_url) > 100 else img.image_url)
                        st.write(f"Size: {img.original_size_bytes/1024:.1f} KB" if img.original_size_bytes else "N/A")
                        st.write(f"Format: {img.original_format}" if img.original_format else "N/A")
                    
                    with col2:
                        if img.enhanced_image_url:
                            st.write("**Enhanced URL:**")
                            st.code(img.enhanced_image_url[:100] + "..." if len(img.enhanced_image_url) > 100 else img.enhanced_image_url)
                            st.write(f"Size: {img.enhanced_size_bytes/1024:.1f} KB" if img.enhanced_size_bytes else "N/A")
                            st.write(f"Format: {img.enhanced_format}" if img.enhanced_format else "N/A")
        else:
            st.info("No processed images yet.")
    finally:
        db.close()


def render_single_enhancement():
    """Render single image enhancement UI"""
    st.subheader("🚀 Quick Enhancement")
    
    tab1, tab2 = st.tabs(["📤 Upload", "🔗 URL"])
    
    with tab1:
        uploaded_file = st.file_uploader(
            "Upload an image",
            type=['jpg', 'jpeg', 'png', 'webp'],
            help="Upload a product image to enhance"
        )
        
        if uploaded_file:
            st.markdown("#### 🛠️ Enhancement Options")
            st.caption("Select the enhancements to apply (based on B2B marketplace requirements)")
            
            # Checkboxes for enhancement options in 2 rows
            col1, col2 = st.columns(2)
            with col1:
                bg_remove = st.checkbox("🖼️ Background Removal", value=True, 
                    help="Remove cluttered backgrounds, replace with clean white")
                light_correct = st.checkbox("💡 Light & Color Correction", value=True,
                    help="Fix exposure, brightness, and color balance")
                use_gemini = st.checkbox("🤖 Gemini AI Enhancement", value=False,
                    help="Use Google Gemini for intelligent image enhancement")
            with col2:
                upscale_denoise = st.checkbox("🔍 Upscale & Denoise", value=False,
                    help="Super resolution to increase image quality without pixelation")
                standardize = st.checkbox("📐 Standardization", value=False,
                    help="Uniform sizing, aspect ratio, and padding")
            
            # Target size slider
            target_size = st.slider(
                "Target Size (KB)",
                min_value=50,
                max_value=1000,
                value=500,
                step=50
            )
            
            # Determine mode based on checkboxes
            def get_enhancement_mode():
                # If all major ones selected, use FULL
                if bg_remove and light_correct and upscale_denoise and standardize:
                    return EnhancementMode.FULL
                # If multiple selected, use FULL but process will apply selected
                if sum([bg_remove, light_correct, upscale_denoise, standardize]) > 1:
                    return EnhancementMode.FULL
                # Single selections
                if bg_remove:
                    return EnhancementMode.BACKGROUND_REMOVE
                if light_correct:
                    return EnhancementMode.LIGHT_CORRECTION
                if upscale_denoise:
                    return EnhancementMode.UPSCALE_DENOISE
                if standardize:
                    return EnhancementMode.STANDARDIZE
                return EnhancementMode.AUTO
            
            mode = get_enhancement_mode()
            
            if st.button("✨ Enhance Image", type="primary", use_container_width=True):
                with st.spinner("Processing..."):
                    original_bytes = uploaded_file.read()
                    
                    # Assess original
                    original_quality = assessor.quick_assess(original_bytes)
                    
                    if use_gemini:
                        # Use Gemini enhancement
                        try:
                            response = requests.post(
                                "http://localhost:8000/api/v1/enhance/gemini",
                                files={"file": (uploaded_file.name, original_bytes, uploaded_file.type)},
                                data={"enhancement_prompt": "true color reproduction, neutral white balance, color consistency across product, enhance the quality"},
                                timeout=300
                            )
                            
                            if response.status_code == 200:
                                result_data = response.json()
                                enhanced_bytes = base64.b64decode(result_data.get('enhanced_image_base64'))
                                enhanced_quality = assessor.quick_assess(enhanced_bytes)
                                elapsed = result_data.get('processing_time_ms', 0) / 1000
                                
                                # Display comparison
                                display_comparison(
                                    original_bytes,
                                    enhanced_bytes,
                                    {
                                        'original_blur': original_quality.get('blur_score', 0),
                                        'enhanced_blur': enhanced_quality.get('blur_score', 0)
                                    }
                                )
                                
                                # Metrics
                                st.divider()
                                col1, col2, col3 = st.columns(3)
                                
                                with col1:
                                    reduction = (1 - len(enhanced_bytes)/len(original_bytes)) * 100
                                    st.metric("Size Reduction", f"-{reduction:.1f}%")
                                
                                with col2:
                                    blur_improvement = ((enhanced_quality.get('blur_score', 0) - original_quality.get('blur_score', 0)) 
                                                       / max(original_quality.get('blur_score', 1), 1)) * 100
                                    st.metric("Sharpness Boost", f"+{blur_improvement:.1f}%")
                                
                                with col3:
                                    st.metric("Processing Time", f"{elapsed:.0f}ms")
                                
                                st.info(f"🤖 Model: {result_data.get('model_version', 'Gemini')}")
                                
                                # Download button
                                st.download_button(
                                    "📥 Download Enhanced Image",
                                    enhanced_bytes,
                                    file_name=f"gemini_enhanced_{uploaded_file.name}",
                                    mime="image/jpeg",
                                    use_container_width=True
                                )
                            else:
                                st.error(f"Gemini enhancement failed: {response.text}")
                        except Exception as e:
                            st.error(f"Error calling Gemini API: {str(e)}")
                    else:
                        # Call API endpoint for enhancement with S3 upload
                        try:
                            response = requests.post(
                                "http://localhost:8000/api/v1/enhance/upload",
                                files={"file": (uploaded_file.name, original_bytes, uploaded_file.type)},
                                data={
                                    "mode": mode.value,
                                    "target_size_kb": target_size,
                                    "output_format": "JPEG"
                                },
                                timeout=300
                            )
                            
                            if response.status_code == 200:
                                result_data = response.json()
                                
                                if result_data.get('success'):
                                    # Fetch enhanced image from URL
                                    enhanced_url = result_data.get('enhanced_url')
                                    enhanced_response = requests.get(enhanced_url, timeout=30)
                                    enhanced_bytes = enhanced_response.content
                                    enhanced_quality = assessor.quick_assess(enhanced_bytes)
                                    
                                    # Display comparison
                                    display_comparison(
                                        original_bytes,
                                        enhanced_bytes,
                                        {
                                            'original_blur': original_quality.get('blur_score', 0),
                                            'enhanced_blur': enhanced_quality.get('blur_score', 0)
                                        }
                                    )
                                    
                                    # Metrics
                                    st.divider()
                                    col1, col2, col3, col4 = st.columns(4)
                                    
                                    with col1:
                                        st.metric("Size Reduction", f"-{result_data.get('size_reduction_percent', 0):.1f}%")
                                    
                                    with col2:
                                        quality_improvement = result_data.get('quality_improvement', 0)
                                        st.metric("Quality Improvement", f"+{quality_improvement:.1f}%" if quality_improvement else "N/A")
                                    
                                    with col3:
                                        st.metric("Processing Time", f"{result_data.get('processing_time_ms', 0):.0f}ms")
                                    
                                    with col4:
                                        st.metric("Database ID", result_data.get('database_id', 'N/A')[:8])
                                    
                                    # Show S3 URLs
                                    st.info(f"📁 Original URL: {result_data.get('original_url', 'N/A')}")
                                    st.info(f"✨ Enhanced URL: {result_data.get('enhanced_url', 'N/A')}")
                                    
                                    # Download button
                                    st.download_button(
                                        "📥 Download Enhanced Image",
                                        enhanced_bytes,
                                        file_name=f"enhanced_{uploaded_file.name}",
                                        mime="image/jpeg",
                                        use_container_width=True
                                    )
                                else:
                                    st.error(f"Enhancement failed: {result_data.get('error', 'Unknown error')}")
                            else:
                                st.error(f"API Error ({response.status_code}): {response.text}")
                        except Exception as e:
                            st.error(f"Error calling enhancement API: {str(e)}")
    
    with tab2:
        url = st.text_input(
            "Image URL",
            placeholder="https://your-cloudfront-domain.com/image.jpg",
            help="Enter a CloudFront or any public image URL"
        )
        
        if url:
            st.markdown("#### 🛠️ Enhancement Options")
            st.caption("Select the enhancements to apply")
            
            # Checkboxes for enhancement options
            col1, col2 = st.columns(2)
            with col1:
                url_bg_remove = st.checkbox("🖼️ Background Removal", value=True, key="url_bg",
                    help="Remove cluttered backgrounds, replace with clean white")
                url_light_correct = st.checkbox("💡 Light & Color Correction", value=True, key="url_light",
                    help="Fix exposure, brightness, and color balance")
            with col2:
                url_upscale_denoise = st.checkbox("🔍 Upscale & Denoise", value=False, key="url_upscale",
                    help="Super resolution to increase image quality")
                url_standardize = st.checkbox("📐 Standardization", value=False, key="url_std",
                    help="Uniform sizing, aspect ratio, and padding")
            
            target_size = st.slider(
                "Target Size (KB)",
                min_value=50,
                max_value=1000,
                value=500,
                step=50,
                key="url_target"
            )
            
            # Determine mode based on checkboxes
            def get_url_mode():
                if url_bg_remove and url_light_correct and url_upscale_denoise and url_standardize:
                    return EnhancementMode.FULL
                if sum([url_bg_remove, url_light_correct, url_upscale_denoise, url_standardize]) > 1:
                    return EnhancementMode.FULL
                if url_bg_remove:
                    return EnhancementMode.BACKGROUND_REMOVE
                if url_light_correct:
                    return EnhancementMode.LIGHT_CORRECTION
                if url_upscale_denoise:
                    return EnhancementMode.UPSCALE_DENOISE
                if url_standardize:
                    return EnhancementMode.STANDARDIZE
                return EnhancementMode.AUTO
            
            mode = get_url_mode()
            
            if st.button("✨ Enhance from URL", type="primary", use_container_width=True):
                with st.spinner("Fetching and processing..."):
                    try:
                        response = requests.post(
                            "http://localhost:8000/api/v1/enhance/url",
                            json={"url": url, "mode": mode.value, "target_size_kb": target_size, "output_format": "JPEG"},
                            timeout=300
                        )
                        if response.status_code == 200:
                            result_data = response.json()
                            if result_data.get('success'):
                                enhanced_response = requests.get(result_data['enhanced_url'], timeout=30)
                                original_response = requests.get(result_data['original_url'], timeout=30)
                                enhanced_bytes = enhanced_response.content
                                original_bytes = original_response.content
                                original_quality = assessor.quick_assess(original_bytes)
                                enhanced_quality = assessor.quick_assess(enhanced_bytes)
                                display_comparison(original_bytes, enhanced_bytes, {'original_blur': original_quality.get('blur_score', 0), 'enhanced_blur': enhanced_quality.get('blur_score', 0)})
                                st.divider()
                                col1, col2, col3, col4 = st.columns(4)
                                with col1:
                                    st.metric("Size Reduction", f"-{result_data.get('size_reduction_percent', 0):.1f}%")
                                with col2:
                                    st.metric("Processing Time", f"{result_data.get('processing_time_ms', 0):.0f}ms")
                                with col3:
                                    st.metric("Database ID", result_data.get('database_id', 'N/A')[:8])
                                with col4:
                                    st.metric("S3 Status", "✓ Saved")
                                st.info(f"📁 Original S3: {result_data.get('original_url', 'N/A')}")
                                st.info(f"✨ Enhanced S3: {result_data.get('enhanced_url', 'N/A')}")
                                st.download_button("📥 Download Enhanced Image", enhanced_bytes, file_name="enhanced_image.jpg", mime="image/jpeg", use_container_width=True)
                            else:
                                st.error(f"Enhancement failed: {result_data.get('error')}")
                        else:
                            st.error(f"API Error ({response.status_code}): {response.text}")
                    except Exception as e:
                        st.error(f"Error calling API: {str(e)}")


def render_batch_import():
    """Render batch import UI"""
    st.subheader("📦 Batch Import")
    
    st.markdown("""
    Import CloudFront URLs for batch processing:
    - **CSV**: Upload a CSV with a 'url' column
    - **Text**: Upload a text file with one URL per line
    - **Manual**: Paste URLs directly
    """)
    
    tab1, tab2, tab3 = st.tabs(["📄 CSV", "📝 Text", "✍️ Manual"])
    
    with tab1:
        csv_file = st.file_uploader("Upload CSV", type=['csv'], key="csv_upload")
        if csv_file:
            df = pd.read_csv(csv_file)
            st.write(f"Found {len(df)} rows")
            st.dataframe(df.head())
            
            url_col = st.selectbox("Select URL column", df.columns)
            
            if st.button("Import from CSV", type="primary"):
                with st.spinner("Importing..."):
                    db = get_db()
                    try:
                        repo = ImageRepository(db)
                        urls = df[url_col].dropna().tolist()
                        
                        imported = 0
                        for url in urls:
                            url = str(url).strip()
                            if url and not repo.get_by_url(url):
                                repo.create(
                                    sku_id=f"import-{imported}",
                                    image_url=url,
                                    status=ProcessingStatus.PENDING.value
                                )
                                imported += 1
                        
                        st.success(f"Imported {imported} new URLs")
                    finally:
                        db.close()
    
    with tab2:
        text_file = st.file_uploader("Upload text file", type=['txt'], key="txt_upload")
        if text_file:
            content = text_file.read().decode('utf-8')
            urls = [line.strip() for line in content.split('\n') if line.strip()]
            st.write(f"Found {len(urls)} URLs")
            
            if st.button("Import from Text", type="primary"):
                with st.spinner("Importing..."):
                    db = get_db()
                    try:
                        repo = ImageRepository(db)
                        imported = 0
                        for url in urls:
                            if not repo.get_by_url(url):
                                repo.create(
                                    sku_id=f"import-{imported}",
                                    image_url=url,
                                    status=ProcessingStatus.PENDING.value
                                )
                                imported += 1
                        st.success(f"Imported {imported} new URLs")
                    finally:
                        db.close()
    
    with tab3:
        urls_text = st.text_area(
            "Paste URLs (one per line)",
            height=200,
            placeholder="https://cloudfront.net/image1.jpg\nhttps://cloudfront.net/image2.jpg"
        )
        
        if urls_text and st.button("Import URLs", type="primary"):
            with st.spinner("Importing..."):
                urls = [line.strip() for line in urls_text.split('\n') if line.strip()]
                
                db = get_db()
                try:
                    repo = ImageRepository(db)
                    imported = 0
                    for url in urls:
                        if not repo.get_by_url(url):
                            repo.create(
                                sku_id=f"import-{imported}",
                                image_url=url,
                                status=ProcessingStatus.PENDING.value
                            )
                            imported += 1
                    st.success(f"Imported {imported} new URLs")
                finally:
                    db.close()


def main():
    """Main dashboard"""
    # Professional Header with gradient background
    st.markdown("""
    <div class="main-header">
        <h1>🖼️ Image Enhancement Pipeline</h1>
        <p>AI-Powered B2B Marketplace Image Optimization • MedikaBazaar</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("### 🎛️ Control Panel")
        st.markdown("---")
        
        # Status indicator
        st.markdown("#### 📡 System Status")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("🟢 **API**")
        with col2:
            st.markdown("🟢 **DB**")
        
        st.markdown("---")
        
        st.markdown("#### 🔗 API Endpoints")
        st.code("POST /api/v1/enhance/url", language=None)
        st.code("POST /api/v1/enhance/upload", language=None)
        
        st.markdown("---")
        
        st.markdown("#### 📚 Documentation")
        st.markdown("• [📄 API Docs](http://localhost:8000/docs)")
        st.markdown("• [❤️ Health Check](http://localhost:8000/health)")
        st.markdown("• [📊 Stats](http://localhost:8000/api/v1/stats)")
        
        st.markdown("---")
        
        if st.button("🔄 Refresh Dashboard", use_container_width=True):
            st.rerun()
        
        st.markdown("---")
        st.markdown(
            "<div style='text-align: center; color: #6c757d; font-size: 0.8rem;'>"
            "v2.0.0 • Built with ❤️"
            "</div>",
            unsafe_allow_html=True
        )
    
    # Main content - KPI cards
    render_kpi_cards()
    
    st.markdown("---")
    
    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs([
        "🚀 Quick Enhance",
        "📊 Analytics", 
        "📦 Batch Import",
        "🕐 History"
    ])
    
    with tab1:
        render_single_enhancement()
    
    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            render_quality_distribution()
        with col2:
            # Processing stats over time (if data available)
            db = get_db()
            try:
                from sqlalchemy import func
                # Query only date and count - quality_improvement is in ImageMetrics table
                results = db.query(
                    func.date(ImageRecord.processed_at).label('date'),
                    func.count(ImageRecord.id).label('count')
                ).filter(
                    ImageRecord.processed_at.isnot(None)
                ).group_by(
                    func.date(ImageRecord.processed_at)
                ).order_by(
                    func.date(ImageRecord.processed_at)
                ).all()
                
                if results:
                    df = pd.DataFrame([
                        {'Date': r.date, 'Count': r.count}
                        for r in results
                    ])
                    
                    fig = px.bar(
                        df, x='Date', y='Count', 
                        title="📈 Images Processed Per Day",
                        color_discrete_sequence=['#667eea']
                    )
                    fig.update_layout(
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("📊 No processing data available yet. Enhance some images to see analytics!")
            finally:
                db.close()
    
    with tab3:
        render_batch_import()
    
    with tab4:
        render_recent_images()
    
    # Professional Footer
    st.markdown("""
    <div class="footer">
        <p><strong>Image Enhancement Pipeline</strong> • Powered by AI</p>
        <p>Background Removal • Light Correction • Super Resolution • Standardization</p>
        <p style="margin-top: 1rem;">© 2024 MedikaBazaar • B2B Healthcare Marketplace</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()

