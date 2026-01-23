import streamlit as st
import os
import sys
import unicodedata
from pathlib import Path

st.set_page_config(page_title="이용 가이드", layout="wide")
st.markdown("# 📘 이용 가이드")

# --- Robust File Finder for Mac/Korean Paths ---
def find_real_path(root_dir, target_name):
    """
    Finds a child file/dir in root_dir matching target_name (NFC normalized).
    Returns the *actual* path on filesystem (NFD likely).
    """
    if not os.path.exists(root_dir): return None
    
    target_nfc = unicodedata.normalize('NFC', target_name)
    
    for item in os.listdir(root_dir):
        item_nfc = unicodedata.normalize('NFC', item)
        if item_nfc == target_nfc:
            return os.path.join(root_dir, item)
    return None

def load_manual():
    # 1. Determine Root relative to this script
    # pages/99... -> parent -> parent = Root
    current_script = os.path.abspath(__file__)
    pages_dir = os.path.dirname(current_script)
    root_dir = os.path.dirname(pages_dir)
    
    # Optional Debug
    # st.caption(f"System Path Check: {root_dir}")
    
    # 2. Find 'reports' folder
    reports_real_path = find_real_path(root_dir, "reports")
    if not reports_real_path:
        # Fallback: Try CWD if script location is weird (e.g. symlinks)
        cwd = os.getcwd()
        reports_real_path = find_real_path(cwd, "reports")
    
    if not reports_real_path:
        st.error(f"❌ 'reports' 폴더를 찾을 수 없습니다.")
        st.code(f"Search Root: {root_dir}\nCWD: {os.getcwd()}")
        return

    # 3. Find manual file inside reports
    manual_real_path = find_real_path(reports_real_path, "premium_user_manual.html")
    
    if not manual_real_path:
        st.error(f"❌ 'premium_user_manual.html' 파일을 찾을 수 없습니다.")
        st.code(f"Inside: {reports_real_path}")
        st.write("폴더 내용:")
        st.write(os.listdir(reports_real_path))
        return

    # 4. Load & Display
    
    try:
        # Import src
        if root_dir not in sys.path:
            sys.path.append(root_dir)
        try:
            from src.utils import embed_local_images
        except ImportError:
            # Fallback for import if path issue
            st.warning("Module Import Failed, showing raw HTML")
            embed_local_images = lambda x, base_path: x

        with open(manual_real_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        
        # Embed images (Base Path must be the Real Path we found)
        html_content = embed_local_images(html_content, base_path=reports_real_path)
        
        st.components.v1.html(html_content, height=1200, scrolling=True)
        
    except Exception as e:
        st.error(f"내용을 불러오는 중 오류 발생: {e}")

if __name__ == "__main__":
    load_manual()
