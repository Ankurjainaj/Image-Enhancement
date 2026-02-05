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

# Initialize session state for task approvals
if "show_reject_reasons" not in st.session_state:
    st.session_state.show_reject_reasons = {}

if "task_filter_status" not in st.session_state:
    st.session_state.task_filter_status = "All"

if "refresh_tasks" not in st.session_state:
    st.session_state.refresh_tasks = False


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
        logger.error(f"Failed to fetch image from {url}: {e}")
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


def render_my_tasks():
    """Render My Tasks tab with approval workflow"""
    st.subheader("✅ My Tasks - Approval Queue")
    
    st.markdown("""
    Review and approve enhanced images before publishing. 
    **Images are shown at 300x300px for quick review.**
    """)
    
    # Stats columns
    col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
    
    # Fetch unapproved tasks
    try:
        api_url = f"http://localhost:{config.api.port}"
        response = requests.get(
            f"{api_url}/api/v1/tasks/unapproved",
            params={"limit": 100}
        )
        response.raise_for_status()
        data = response.json()
        tasks = data.get("tasks", [])
        total_tasks = data.get("total", 0)
        
        with col_stat1:
            st.metric("📋 Pending Review", total_tasks)
        
        with col_stat2:
            st.metric("🖼️ Total Images", len(tasks))
        
        with col_stat3:
            if tasks:
                avg_improvement = 0
                count = 0
                for task in tasks:
                    orig = task.get("original_quality_score")
                    enh = task.get("enhanced_quality_score")
                    if orig is not None and enh is not None:
                        try:
                            avg_improvement += (float(enh) - float(orig))
                            count += 1
                        except:
                            pass
                avg_improvement = avg_improvement / count if count > 0 else 0
                st.metric("📈 Avg Quality Improvement", f"+{avg_improvement:.1f}%")
        
        with col_stat4:
            if tasks:
                total_processing_ms = sum(task.get("processing_time_ms", 0) for task in tasks)
                avg_time_ms = total_processing_ms / len(tasks)
                st.metric("⏱️ Avg Processing Time", f"{avg_time_ms:.0f}ms")
        
        if not tasks:
            st.success("🎉 No pending approvals! All images have been reviewed.")
            return
        
        st.divider()
        
        # Filter options
        col_filter1, col_filter2, col_filter3 = st.columns(3)
        
        with col_filter1:
            search_sku = st.text_input("🔍 Search by SKU ID", "")
        
        with col_filter2:
            sort_by = st.selectbox("Sort by:", ["Latest", "SKU ID", "Quality Improvement", "File Size"])
        
        with col_filter3:
            items_per_page = st.slider("Items per page:", 5, 50, 10)
        
        # Filter and sort tasks
        filtered_tasks = tasks
        
        if search_sku:
            filtered_tasks = [t for t in filtered_tasks if search_sku.lower() in t.get("sku_id", "").lower()]
        
        if sort_by == "SKU ID":
            filtered_tasks.sort(key=lambda x: x.get("sku_id", ""))
        elif sort_by == "Quality Improvement":
            filtered_tasks.sort(
                key=lambda x: float(x.get("enhanced_quality_score", 0) or 0) - float(x.get("original_quality_score", 0) or 0),
                reverse=True
            )
        elif sort_by == "File Size":
            filtered_tasks.sort(key=lambda x: x.get("enhanced_size_bytes", 0), reverse=True)
        # Latest is default (already sorted by created_at in API)
        
        st.info(f"📋 Showing {len(filtered_tasks)} tasks" + (f" matching '{search_sku}'" if search_sku else ""))
        
        # Pagination
        total_pages = (len(filtered_tasks) + items_per_page - 1) // items_per_page
        col_prev, col_page, col_next = st.columns([1, 4, 1])
        
        if "current_page" not in st.session_state:
            st.session_state.current_page = 1
        
        with col_prev:
            if st.button("⬅️ Previous"):
                st.session_state.current_page = max(1, st.session_state.current_page - 1)
        
        with col_page:
            st.markdown(f"**Page {st.session_state.current_page} of {total_pages}**", unsafe_allow_html=True)
        
        with col_next:
            if st.button("Next ➡️"):
                st.session_state.current_page = min(total_pages, st.session_state.current_page + 1)
        
        # Get paginated tasks
        start_idx = (st.session_state.current_page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        paginated_tasks = filtered_tasks[start_idx:end_idx]
        
        st.divider()
        
        # Create table header
        col_headers = st.columns([1.2, 1.2, 1.2, 1.2, 0.8, 0.8, 0.6])
        with col_headers[0]:
            st.markdown("**SKU ID**")
        with col_headers[1]:
            st.markdown("**Original**")
        with col_headers[2]:
            st.markdown("**Enhanced**")
        with col_headers[3]:
            st.markdown("**Scores**")
        with col_headers[4]:
            st.markdown("**Info**")
        with col_headers[5]:
            st.markdown("**Actions**")
        with col_headers[6]:
            st.markdown("**Status**")
        
        st.divider()
        
        # Iterate through paginated tasks
        for idx, task in enumerate(paginated_tasks):
            task_id = task.get("task_id", "")
            sku_id = task.get("sku_id", "N/A")
            original_url = task.get("original_url", "")
            enhanced_url = task.get("enhanced_url", "")
            
            # Quality metrics
            orig_blur = task.get("original_blur_score")
            enh_blur = task.get("enhanced_blur_score")
            orig_quality = task.get("original_quality_score")
            enh_quality = task.get("enhanced_quality_score")
            
            # Size metrics
            orig_size_bytes = task.get("original_size_bytes", 0)
            enh_size_bytes = task.get("enhanced_size_bytes", 0)
            orig_size_kb = orig_size_bytes / 1024 if orig_size_bytes else 0
            enh_size_kb = enh_size_bytes / 1024 if enh_size_bytes else 0
            
            # Dimensions
            orig_w = task.get("original_width", 0)
            orig_h = task.get("original_height", 0)
            enh_w = task.get("enhanced_width", 0)
            enh_h = task.get("enhanced_height", 0)
            
            # Create row
            col1, col2, col3, col4, col5, col6, col7 = st.columns([1.2, 1.2, 1.2, 1.2, 0.8, 0.8, 0.6])
            
            with col1:
                st.markdown(f"**`{sku_id}`**")
                st.caption(f"Type: {task.get('image_type', 'N/A')}")
            
            with col2:
                # Original image thumbnail with expander for full view
                if original_url:
                    try:
                        img_bytes = get_image_from_url(original_url, timeout=10)
                        if img_bytes:
                            img = Image.open(io.BytesIO(img_bytes))
                            img_display = img.copy()
                            img_display.thumbnail((300, 300), Image.Resampling.LANCZOS)
                            st.image(img_display, use_container_width=True)
                        else:
                            st.warning("❌ Cannot load")
                    except Exception as e:
                        st.warning(f"❌ Load error")
                        logger.error(f"Error loading image {original_url}: {e}")
                
                st.caption(f"📦 {orig_size_kb:.1f}KB")
                st.caption(f"📐 {orig_w}×{orig_h}px" if orig_w and orig_h else "📐 N/A")
            
            with col3:
                # Enhanced image thumbnail
                if enhanced_url:
                    try:
                        img_bytes = get_image_from_url(enhanced_url, timeout=10)
                        if img_bytes:
                            img = Image.open(io.BytesIO(img_bytes))
                            img_display = img.copy()
                            img_display.thumbnail((300, 300), Image.Resampling.LANCZOS)
                            st.image(img_display, use_container_width=True)
                        else:
                            st.warning("❌ Cannot load")
                    except Exception as e:
                        st.warning(f"❌ Load error")
                        logger.error(f"Error loading image {enhanced_url}: {e}")
                
                st.caption(f"📦 {enh_size_kb:.1f}KB")
                st.caption(f"📐 {enh_w}×{enh_h}px" if enh_w and enh_h else "📐 N/A")
            
            with col4:
                # Quality metrics with color coding
                st.markdown("**Quality:**")
                
                if orig_quality is not None:
                    try:
                        orig_q = float(orig_quality)
                        st.caption(f"Original: {orig_q:.1f}")
                    except:
                        pass
                
                if enh_quality is not None:
                    try:
                        enh_q = float(enh_quality)
                        improvement = enh_q - (float(orig_quality) if orig_quality else 0)
                        
                        if improvement > 0:
                            st.caption(f"✅ Enhanced: {enh_q:.1f} (+{improvement:.1f})")
                        else:
                            st.caption(f"⚠️ Enhanced: {enh_q:.1f} ({improvement:.1f})")
                    except:
                        pass
                
                # Show enhancements applied
                enhancements = task.get('enhancements_applied', [])
                if enhancements:
                    st.caption(f"🔧 {', '.join(enhancements)}")
            
            with col5:
                # Metrics & info
                st.caption(f"🔧 {len(task.get('enhancements_applied', []))} ops")
                st.caption(f"⏱️ {task.get('processing_time_ms', 0)}ms")
                if orig_size_kb > 0:
                    reduction_pct = (1 - enh_size_kb / orig_size_kb) * 100
                    st.caption(f"📉 {reduction_pct:.1f}% smaller")
            
            with col6:
                # Action buttons - stacked vertically
                col_approve, col_reject = st.columns(2)
                
                with col_approve:
                    if st.button("✅", key=f"approve_{task_id}", help="Approve this task"):
                        with st.spinner("Approving..."):
                            try:
                                api_url = f"http://localhost:{config.api.port}"
                                approve_response = requests.post(
                                    f"{api_url}/api/v1/tasks/{task_id}/approve"
                                )
                                if approve_response.status_code == 200:
                                    st.toast("✅ Approved!", icon="✅")
                                    st.session_state.refresh_tasks = not st.session_state.refresh_tasks
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error(f"Error: {approve_response.status_code}")
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
                
                with col_reject:
                    if st.button("❌", key=f"reject_btn_{task_id}", help="Reject this task"):
                        st.session_state[f"show_reject_{task_id}"] = True
            
            with col7:
                status_badge = task.get("qc_status", "PENDING")
                if status_badge == "APPROVED":
                    st.success("✅")
                elif status_badge == "REJECTED":
                    st.error("❌")
                else:
                    st.warning("⏳")
            
            # Reject reason input (inline)
            if st.session_state.get(f"show_reject_{task_id}"):
                st.warning(f"Rejecting task for {sku_id}")
                reason = st.text_area(
                    f"Why reject this image?",
                    key=f"reason_{task_id}",
                    height=80
                )
                col_confirm, col_cancel, col_space = st.columns([1, 1, 2])
                
                with col_confirm:
                    if st.button("✓ Confirm", key=f"confirm_reject_{task_id}"):
                        with st.spinner("Rejecting..."):
                            try:
                                api_url = f"http://localhost:{config.api.port}"
                                reject_response = requests.post(
                                    f"{api_url}/api/v1/tasks/{task_id}/reject",
                                    data={"rejection_reason": reason}
                                )
                                if reject_response.status_code == 200:
                                    st.toast("❌ Rejected!", icon="❌")
                                    st.session_state[f"show_reject_{task_id}"] = False
                                    st.session_state.refresh_tasks = not st.session_state.refresh_tasks
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error(f"Error: {reject_response.status_code}")
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
                
                with col_cancel:
                    if st.button("✕ Cancel", key=f"cancel_reject_{task_id}"):
                        st.session_state[f"show_reject_{task_id}"] = False
            
            st.divider()
        
    except Exception as e:
        st.error(f"Error loading tasks: {str(e)}")
        logger.error(f"Error in render_my_tasks: {e}", exc_info=True)


def render_approved_tasks():
    """Render approved tasks tab"""
    st.subheader("✅ Approved Images")
    st.markdown("View all approved and published images.")
    
    try:
        api_url = f"http://localhost:{config.api.port}"
        response = requests.get(f"{api_url}/api/v1/tasks/approved", params={"limit": 100})
        response.raise_for_status()
        data = response.json()
        tasks = data.get("tasks", [])
        total_tasks = data.get("total", 0)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("✅ Total Approved", total_tasks)
        with col2:
            if tasks:
                avg_size_reduction = sum(
                    (1 - t.get("enhanced_size_bytes", 0) / max(t.get("original_size_bytes", 1), 1)) * 100
                    for t in tasks if t.get("original_size_bytes")
                ) / len(tasks)
                st.metric("💾 Avg Size Reduction", f"{avg_size_reduction:.1f}%")
        with col3:
            if tasks:
                avg_time = sum(t.get("processing_time_ms", 0) for t in tasks) / len(tasks)
                st.metric("⏱️ Avg Processing Time", f"{avg_time:.0f}ms")
        
        if not tasks:
            st.info("No approved images yet.")
            return
        
        st.divider()
        
        # Search
        search_sku = st.text_input("🔍 Search by SKU ID", "", key="approved_search_sku")
        
        filtered_tasks = tasks
        if search_sku:
            filtered_tasks = [t for t in filtered_tasks if search_sku.lower() in t.get("sku_id", "").lower()]
        
        st.info(f"📋 Showing {len(filtered_tasks)} approved images")
        st.divider()
        
        # Table header
        col_headers = st.columns([1.5, 1.5, 1, 0.5])
        with col_headers[0]:
            st.markdown("**SKU ID**")
        with col_headers[1]:
            st.markdown("**Approved Date**")
        with col_headers[2]:
            st.markdown("**Reviewer**")
        with col_headers[3]:
            st.markdown("**View**")
        
        st.divider()
        
        # Display rows
        for task in filtered_tasks:
            task_id = task.get("task_id", "")
            sku_id = task.get("sku_id", "N/A")
            original_url = task.get("original_url", "")
            enhanced_url = task.get("enhanced_url", "")
            reviewed_at = task.get("qc_reviewed_at", "")
            reviewer = task.get("qc_reviewed_by", "N/A")
            
            col1, col2, col3, col4 = st.columns([1.5, 1.5, 1, 0.5])
            
            with col1:
                st.markdown(f"**`{sku_id}`**")
            
            with col2:
                if reviewed_at:
                    st.text(reviewed_at[:10])
                else:
                    st.text("N/A")
            
            with col3:
                st.text(reviewer)
            
            with col4:
                if st.button("👁️", key=f"view_{task_id}", help="View images"):
                    st.session_state[f"show_images_{task_id}"] = not st.session_state.get(f"show_images_{task_id}", False)
            
            # Show images if toggled
            if st.session_state.get(f"show_images_{task_id}", False):
                with st.spinner("Loading images..."):
                    img_col1, img_col2 = st.columns(2)
                    
                    with img_col1:
                        st.caption("**Original**")
                        if original_url:
                            try:
                                img_bytes = get_image_from_url(original_url, timeout=10)
                                if img_bytes:
                                    img = Image.open(io.BytesIO(img_bytes))
                                    st.image(img, use_container_width=True)
                                    st.caption(f"🔗 {original_url}")
                                else:
                                    st.warning("❌ Cannot load")
                            except Exception as e:
                                st.warning(f"❌ Load error: {str(e)[:50]}")
                    
                    with img_col2:
                        st.caption("**Enhanced**")
                        if enhanced_url:
                            try:
                                img_bytes = get_image_from_url(enhanced_url, timeout=10)
                                if img_bytes:
                                    img = Image.open(io.BytesIO(img_bytes))
                                    st.image(img, use_container_width=True)
                                    st.caption(f"🔗 {enhanced_url}")
                                else:
                                    st.warning("❌ Cannot load")
                            except Exception as e:
                                st.warning(f"❌ Load error: {str(e)[:50]}")
            
            st.divider()
    
    except Exception as e:
        st.error(f"Error loading approved tasks: {str(e)}")
        logger.error(f"Error in render_approved_tasks: {e}", exc_info=True)


def render_batch_process():
    """Render batch processing tab"""
    st.subheader("📦 Batch Process")
    st.markdown("Process multiple images in batch mode")
    
    # Input section
    st.markdown("### Input")
    
    input_type = st.radio("Select input type:", ["AUTO", "SKU IDs", "Image URLs"], horizontal=True)
    
    if input_type == "AUTO":
        st.info("🤖 AUTO mode will automatically select pending images from the database")
        limit = st.number_input("Max images to process", min_value=1, max_value=1000, value=100)
        batch_size = st.number_input("Batch size (images per batch)", min_value=1, max_value=50, value=10)
        st.caption("Smaller batch sizes reduce server load")
    elif input_type == "SKU IDs":
        sku_input = st.text_area(
            "Enter SKU IDs (one per line)",
            height=150,
            placeholder="SKU-001\nSKU-002\nSKU-003"
        )
        sku_ids = [s.strip() for s in sku_input.split('\n') if s.strip()]
        st.info(f"📊 {len(sku_ids)} SKU IDs entered")
        batch_size = st.number_input("Batch size", min_value=1, max_value=50, value=10)
    else:
        url_input = st.text_area(
            "Enter Image URLs (one per line)",
            height=150,
            placeholder="https://example.com/image1.jpg\nhttps://example.com/image2.jpg"
        )
        image_urls = [u.strip() for u in url_input.split('\n') if u.strip()]
        st.info(f"📊 {len(image_urls)} URLs entered")
        batch_size = st.number_input("Batch size", min_value=1, max_value=50, value=10)
    
    mode = st.selectbox("Enhancement Mode", ["auto", "full", "light_correction", "upscale"])
    
    if st.button("🚀 Start Batch Processing", type="primary", use_container_width=True):
        try:
            api_url = f"http://localhost:{config.api.port}"
            
            payload = {"mode": mode, "batch_size": batch_size}
            
            if input_type == "AUTO":
                payload["auto_mode"] = True
                payload["limit"] = limit
            elif input_type == "SKU IDs":
                if not sku_ids:
                    st.error("Please enter at least one SKU ID")
                    return
                payload["sku_ids"] = sku_ids
            else:
                if not image_urls:
                    st.error("Please enter at least one image URL")
                    return
                payload["image_urls"] = image_urls
            
            with st.spinner("Creating batch job..."):
                response = requests.post(f"{api_url}/api/v1/batch/process", json=payload)
                
                if response.status_code == 200:
                    result = response.json()
                    st.success(f"✅ Batch job created! Job ID: {result['job_id']}")
                    st.info(f"📊 Total images: {result['total_images']} | Batch size: {result['batch_size']}")
                    st.session_state.refresh_batch_jobs = True
                else:
                    st.error(f"Error: {response.text}")
        except Exception as e:
            st.error(f"Error: {str(e)}")
    
    st.divider()
    
    # Jobs list
    st.markdown("### Batch Jobs")
    
    col_refresh, col_auto = st.columns([1, 3])
    with col_refresh:
        if st.button("🔄 Refresh"):
            st.session_state.refresh_batch_jobs = True
    
    try:
        api_url = f"http://localhost:{config.api.port}"
        response = requests.get(f"{api_url}/api/v1/batch/jobs")
        
        if response.status_code == 404:
            st.warning("⚠️ Batch jobs endpoint not available. Please restart the API server.")
            return
        
        response.raise_for_status()
        data = response.json()
        jobs = data.get("jobs", [])
        
        if not jobs:
            st.info("No batch jobs yet")
            return
        
        # Display jobs
        for job in jobs:
            job_id = job.get("job_id", "")
            status = job.get("status", "unknown")
            total = job.get("total_images", 0)
            processed = job.get("processed_count", 0)
            success = job.get("success_count", 0)
            failed = job.get("failed_count", 0)
            progress = job.get("progress_percent", 0)
            
            with st.expander(f"📊 Job {job_id[:8]}... - {status.upper()}", expanded=(status == "processing")):
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total", total)
                with col2:
                    st.metric("Processed", processed)
                with col3:
                    st.metric("Success", success)
                with col4:
                    st.metric("Failed", failed)
                
                # Progress bar
                st.progress(progress / 100 if progress else 0)
                st.caption(f"Progress: {progress:.1f}%")
                
                # Timestamps
                st.caption(f"📅 Created: {job.get('created_at', 'N/A')[:19]}")
                if job.get('started_at'):
                    st.caption(f"▶️ Started: {job.get('started_at', 'N/A')[:19]}")
                if job.get('completed_at'):
                    st.caption(f"✅ Completed: {job.get('completed_at', 'N/A')[:19]}")
                
                # Status badge
                if status == "completed":
                    st.success("✅ Completed")
                elif status == "processing":
                    st.info("⏳ Processing...")
                elif status == "failed":
                    st.error(f"❌ Failed: {job.get('error_message', 'Unknown error')}")
                elif status == "queued":
                    st.warning("⏱️ Queued")
    
    except Exception as e:
        st.error(f"Error loading batch jobs: {str(e)}")
        logger.error(f"Error in render_batch_process: {e}", exc_info=True)


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
    
    # Main content - KPI cards
    render_kpi_cards()
    
    st.markdown("---")
    
    # Tabs for different views
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "🚀 Quick Enhance",
        "📊 Analytics", 
        "✅ My Tasks",
        "✅ Approved",
        "📦 Batch Process",
        "📦 Batch Import",
        "🕐 History",
        "📋 Batch Jobs"
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
        render_my_tasks()
    
    with tab4:
        render_approved_tasks()
    
    with tab5:
        render_batch_process()
    
    with tab6:
        render_batch_import()
    
    with tab7:
        render_recent_images()
    
    with tab8:
        st.header("📋 Batch Jobs")
        
        try:
            response = requests.get(f"http://localhost:{config.api.port}/api/v1/batch/jobs?limit=100")
            if response.status_code == 200:
                data = response.json()
                jobs = data.get("jobs", [])
                
                if jobs:
                    df = pd.DataFrame(jobs)
                    
                    for col in ['created_at', 'started_at', 'completed_at']:
                        if col in df.columns:
                            df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')
                    
                    display_cols = ['job_id', 'status', 'total_images', 'processed_count', 'success_count', 'failed_count', 'skipped_count', 'progress_percent', 'created_at', 'started_at', 'completed_at']
                    available_cols = [col for col in display_cols if col in df.columns]
                    
                    st.dataframe(df[available_cols], use_container_width=True, height=600)
                    st.caption(f"📊 Total Jobs: {len(jobs)}")
                else:
                    st.info("ℹ️ No batch jobs found")
            else:
                st.error(f"❌ API Error {response.status_code}: {response.text}")
        except requests.exceptions.ConnectionError:
            st.warning("⚠️ Cannot connect to API server. Please restart the API server.")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
    
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

