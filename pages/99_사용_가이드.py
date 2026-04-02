import streamlit as st
import os
import unicodedata

st.set_page_config(page_title="이용 가이드", layout="wide", page_icon="📘")

# Robust Path Resolution
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
manual_filename = "premium_user_manual.html"
static_dir = os.path.join(BASE_DIR, "static")
manual_path = os.path.join(static_dir, manual_filename)

# [FIX] Robust find (Unicode Normalization)
if not os.path.exists(manual_path) and os.path.exists(static_dir):
    for f in os.listdir(static_dir):
        if unicodedata.normalize('NFC', f) == unicodedata.normalize('NFC', manual_filename):
            manual_path = os.path.join(static_dir, f)
            break

if os.path.exists(manual_path):
    with open(manual_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # Import embed function
    try:
        import sys
        if BASE_DIR not in sys.path:
            sys.path.append(BASE_DIR)
        from src.utils import embed_local_images
        html_content = embed_local_images(html_content, base_path=static_dir)
    except:
        pass  # If import fails, display without embedded images
    
    # Display manual
    st.components.v1.html(html_content, height=1200, scrolling=True)
else:
    st.error("❌ 사용 설명서를 찾을 수 없습니다.")
    st.info(f"찾은 경로: {manual_path}")
    if os.path.exists(static_dir):
        st.write("static 폴더 내용:")
        st.write(os.listdir(static_dir))
