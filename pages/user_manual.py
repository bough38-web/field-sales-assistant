import streamlit as st
import os
import streamlit.components.v1 as components
import base64
import re

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
manual_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "premium_user_manual.html")

def embed_images(html_content):
    """
    Replace relative image paths with base64 encoded data URIs.
    Target pattern: src="assets/filename.png"
    """
    static_assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "assets")

    def replace_match(match):
        filename = match.group(1)
        filepath = os.path.join(static_assets_dir, filename)

        if os.path.exists(filepath):
            try:
                with open(filepath, "rb") as f:
                    encoded_string = base64.b64encode(f.read()).decode()
                    ext = os.path.splitext(filename)[1].lower().replace('.', '')
                    # Determine mime type
                    mime_type = f"image/{ext}"
                    if ext == 'svg':
                        mime_type = 'image/svg+xml'
                    elif ext == 'jpg' or ext == 'jpeg':
                        mime_type = 'image/jpeg'
                    elif ext == 'png':
                        mime_type = 'image/png'
                    
                    return f'src="data:{mime_type};base64,{encoded_string}"'
            except Exception as e:
                # Log error to console but keep running
                print(f"Error embedding image {filename}: {e}")
                return match.group(0)
        else:
            # File not found
            print(f"Image not found: {filepath}")
            return match.group(0)

    # Regex to find src="assets/..."
    return re.sub(r'src="assets/([^"]+)"', replace_match, html_content)

if os.path.exists(manual_path):
    with open(manual_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
        
    # Embed images directly into HTML
    html_content = embed_images(html_content)
    
    components.html(html_content, height=1000, scrolling=True)
else:
    st.error("사용설명서 파일을 찾을 수 없습니다.")
