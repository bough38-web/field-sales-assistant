import streamlit as st
import os
import streamlit.components.v1 as components

# Configure page to look like a standalone document
st.set_page_config(
    page_title="영업기회 가이드 | Field Sales Assistant",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Hide Streamlit elements to make it look like a pure HTML page
st.markdown("""
<style>
    /* Hide Streamlit header, footer, and hamburger menu */
    header {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Remove padding to use full screen */
    .block-container {
        padding-top: 0rem !important;
        padding-bottom: 0rem !important;
        padding-left: 0rem !important;
        padding-right: 0rem !important;
        max-width: 100% !important;
    }
    
    /* Hide sidebar completely */
    [data-testid="stSidebar"] { display: none; }
    
    /* Ensure iframe takes full height */
    iframe {
        height: 100vh !important;
        width: 100% !important;
    }
</style>
""", unsafe_allow_html=True)

# Path to the manual
# We use the one in static to ensure assets are resolved if we used static linking,
# but for component.html, we need to read the content.
# Images in the HTML rely on specific paths. 
# If the HTML expects "assets/...", it will look relative to the iframe's context.
# Streamlit components interact trickily with relative paths.
# Best bet: Read code, replace asset paths with base64 OR absolute URL if possible.
# But for now, let's try reading the file and rendering.

manual_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports", "premium_user_manual.html")

if os.path.exists(manual_path):
    with open(manual_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
        
    # [FIX] Handle image paths for Streamlit Component
    # Since component runs in an iframe, relative paths like "assets/img.png" 
    # might not work unless served correctly.
    # However, we have correct static serving enabled now for 'static/'.
    # So we can replace "assets/" with "/app/static/assets/" or similar.
    
    # 1. Update image src to point to the served static files
    # Streamlit serves static files at /app/static/ if configured.
    # Let's try replacing "assets/" with "static/assets/" assuming root context.
    
    # Actually, simpler: Embed the HTML raw.
    # If standard static serving is on, and we are at localhost:8501/user_manual
    # Relative path "assets/..." would look for localhost:8501/assets/... which fails.
    # loading it as /app/static/assets/... 
    
    # Let's assume the user enabled static serving in config.toml as we did.
    # So http://localhost:8501/app/static/assets/image.png should exist.
    html_content = html_content.replace('src="assets/', 'src="/app/static/assets/')
    
    components.html(html_content, height=1000, scrolling=True)
else:
    st.error("사용설명서 파일을 찾을 수 없습니다.")
