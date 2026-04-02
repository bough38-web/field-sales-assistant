import pandas as pd
import re
import unicodedata
import os
import json
from typing import Any
from sklearn.metrics.pairwise import cosine_similarity
from difflib import SequenceMatcher
from datetime import datetime, timedelta, timezone

def get_now_kst():
    """Returns current time in KST (UTC+9) as timezone-naive pd.Timestamp"""
    return pd.Timestamp.now(tz='Asia/Seoul').tz_localize(None)

def get_now_kst_str():
    """Returns KST time as formatted string"""
    return get_now_kst().strftime("%Y-%m-%d %H:%M:%S")

def safe_normalize(text: Any) -> str:
    """Robust Unicode normalization that handles nulls and non-string types safely."""
    if pd.isna(text) or text is None:
        return ""
    # Enforce NFC for consistency across Korean characters
    return unicodedata.normalize('NFC', str(text)).strip()

# Check for rapidfuzz for better performance, fallback to difflib
try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

# Coordinate Conversion
try:
    from pyproj import Transformer
    # EPSG:5174 (Modified Bessel Middle) to EPSG:4326 (WGS84 Lat/Lon)
    transformer = Transformer.from_crs("epsg:5174", "epsg:4326", always_xy=True)
    HAS_PYPROJ = True
except ImportError:
    HAS_PYPROJ = False
    transformer = None

def normalize_address(address):
    """
    Normalizes a Korean address string.
    Removes special characters, standardizes region names.
    """
    if pd.isna(address):
        return None
    
    address = str(address).strip()
    
    # Remove everything in brackets (e.g., (Apt 101), (Bldg B))
    address = re.sub(r'\([^)]*\)', '', address)
    
    # Standardize
    replacements = {
        '강원특별자치도': '강원도', '강원도': '강원도',
        '세종특별자치시': '세종시', '세종시': '세종시',
        '서울특별시': '서울시', '서울시': '서울시',
        '전라북도': '전북', '전북특별자치도': '전북',
        '전라남도': '전남',
        '경상북도': '경북',
        '경상남도': '경남',
        '충청북도': '충북',
        '충청남도': '충남'
    }
    for k, v in replacements.items():
        address = address.replace(k, v)
    
    address = address.replace('  ', ' ') # Double spaces
    address = address.replace('-', '')
    
    if len(address) < 8:  # Too short
        return None
        
    return address.strip()

def parse_coordinates_row(row, x_col, y_col):
    """
    Helper to parse and convert coordinates.
    """
    try:
        if not x_col or not y_col:
            return None, None
            
        x_val = row.get(x_col)
        y_val = row.get(y_col)
        
        if pd.isna(x_val) or pd.isna(y_val):
            return None, None
            
        x = float(x_val)
        y = float(y_val)
        
        # Heuristic: If values are small (lat/lon like), return as is
        if 120 < x < 140 and 30 < y < 45:
            return y, x # Lat, Lon
            
        # Conversion
        if HAS_PYPROJ:
            lon, lat = transformer.transform(x, y)
            # Sanity check for Korea
            if 30 < lat < 45 and 120 < lon < 140:
                return lat, lon
                
    except:
        return None, None
    return None, None

def get_best_match(address, choices, vectorizer, tfidf_matrix, threshold=0.7):
    """
    Finds the best matching address from a list of choices using TF-IDF and Levenshtein/RapidFuzz.
    """
    if pd.isna(address):
        return None

    # 1. TF-IDF Cosine Similarity (Fast Filter)
    try:
        # Use only first element if it's a list/series
        if isinstance(address, pd.Series): address = address.iloc[0]
            
        tfidf_vec = vectorizer.transform([str(address)])
        cosine_sim = cosine_similarity(tfidf_vec, tfidf_matrix).flatten()
        # Get top candidate
        best_idx = cosine_sim.argmax()
        best_cosine_score = cosine_sim[best_idx]
        
        # [FIX] Add Similarity Threshold to prevent incorrect matches
        # e.g. "Busan" matching "Gangneung" because both have "dong"
        # Threshold 0.4 seems reasonable for address matching
        if best_cosine_score < 0.4:
            return None
            
    except Exception:
        best_cosine_score = 0
        best_idx = -1

    # Optimization: If cosine score is very high, trust it.
    if best_cosine_score >= 0.85:
        return choices[best_idx]

    # 2. Refine with Edit Distance
    # Only check top N candidates from TF-IDF
    top_n = 5
    top_indices = cosine_sim.argsort()[-top_n:][::-1]
    
    best_score = 0
    best_match = None
    
    for idx in top_indices:
        choice = choices[idx]
        
        if HAS_RAPIDFUZZ:
            # RapidFuzz: 0-100 scale, normalize to 0-1
            score = fuzz.ratio(str(address), str(choice)) / 100.0
        else:
            # Difflib: 0-1 scale
            score = SequenceMatcher(None, str(address), str(choice)).ratio()
            
        if score > best_score:
            best_score = score
            best_match = choice
            
    # Combine signals: Max of cosine and edit distance logic
    # Actually, edit distance is usually better for small typos.
    final_score = max(best_score, best_cosine_score)
    
    if final_score >= threshold:
        return best_match
    
    return None

def calculate_area(row):
    val = row.get('소재지면적', 0)
    if pd.isna(val) or val == 0: val = row.get('총면적', 0)
    try:
        return round(float(val) / 3.3058, 1)
    except:
        return 0

# --- System Configuration ---
# --- System Configuration ---
# [FIX] Move dynamic data outside project to prevent reload loops
# DATA_DIR = "data"
DATA_DIR = os.path.join(os.path.expanduser("~"), ".sales_assistant_data")
os.makedirs(DATA_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(DATA_DIR, "system_config.json")

def load_system_config():
    """Load system configuration (notices, data dates)"""
    default_config = {
        "notice_title": "",
        "notice_content": "",
        "show_notice": False,
        "data_standard_date": "",
        "maintenance_mode": False
    }
    if not os.path.exists(CONFIG_FILE):
        return default_config
    
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return default_config

def save_system_config(config):
    """Save system configuration"""
    try:
        # Ensure data directory exists
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

import base64
def embed_local_images(html_content, base_path=""):
    """
    Replace local image src with base64 embedded data.
    Assumes images are in 'assets/'.
    """
    def replace_match(match):
        src = match.group(1)
        # Check if local file
        if not src.startswith("http") and not src.startswith("data:"):
            # Construct full path
            # If src is 'assets/img.png', and base_path is project root, it should work.
            full_path = src
            if base_path:
                full_path = os.path.join(base_path, src)
            
            if os.path.exists(full_path):
                try:
                    ext = full_path.split('.')[-1].lower()
                    mime_type = f"image/{ext}"
                    if ext == 'jpg': mime_type = "image/jpeg"
                    if ext == 'svg': mime_type = "image/svg+xml"
                    
                    with open(full_path, "rb") as f:
                        encoded = base64.b64encode(f.read()).decode()
                        return f'src="data:{mime_type};base64,{encoded}"'
                except Exception as e:
                    print(f"Error checking image {full_path}: {e}")
                    pass
        return match.group(0) # No change

    # Regex to find src="..."
    # We look for src="([^"]+)"
    pattern = r'src="([^"]+)"'
    return re.sub(pattern, replace_match, html_content)

def generate_record_key(title, addr):
    """
    Generate a normalized, consistent record key from Title and Address.
    This function MUST be used by both the frontend (app.py) and backend (activity_logger.py)
    to ensure data consistency.
    """
    def clean(s):
        if s is None: return ""
        s = str(s)
        if s.lower() == 'nan': return ""
        # Normalize unicode (e.g. separate jamo)
        s = unicodedata.normalize('NFC', s)
        
        # [IMPROVED] Address Semantic Normalization
        # Replace common long forms with short forms to ensure "서울특별시" == "서울"
        # Only apply this to the address part, but here 's' could be title too.
        # However, titles unlikely to have these exact strings unless coincidence.
        # Safer to apply replacement only if recognized as address components.
        # For simplicity and robustness, we replace globally as these are district names.
        
        # [IMPROVED] Comprehensive address normalization including all official government variations
        replacements = {
            # Seoul (서울)
            "서울특별시": "서울", "서울시": "서울",
            
            # Gyeonggi (경기)
            "경기도": "경기", "기도": "경기",
            
            # Metropolitan Cities (광역시 / 특별광역시)
            "인천특별광역시": "인천", "인천광역시": "인천", "인천시": "인천",
            "부산광역시": "부산", "부산시": "부산",
            "대구광역시": "대구", "대구시": "대구",
            "광주광역시": "광주", "광주시": "광주",
            "대전광역시": "대전", "대전시": "대전",
            "울산광역시": "울산", "울산시": "울산",
            
            # Special Self-Governing City/Province (특별자치시/도)
            "세종특별자치시": "세종", "세종시": "세종",
            "제주특별자치도": "제주", "제주도": "제주", "제주시": "제주",
            "강원특별자치도": "강원", "강원도": "강원",
            "전북특별자치도": "전북", "전라북도": "전북",
            
            # Provinces (도)
            "충청북도": "충북", "충북도": "충북", "충청북도 ": "충북 ",
            "충청남도": "충남", "충남도": "충남", "충청남도 ": "충남 ",
            "전라남도": "전남", "전남도": "전남", "전라남도 ": "전남 ",
            "경상북도": "경북", "경북도": "경북", "경상북도 ": "경북 ",
            "경상남도": "경남", "경남도": "경남", "경상남도 ": "경남 ",
            "전북특별자치도": "전북", "전라북도": "전북", "전북도": "전북"
        }
        
        # Pre-clean strict logic: remove spaces first? No, replacements might need boundaries if we were regexing.
        # But here we do simple string replace. "서울특별시" -> "서울" works even if attached.
        
        for k, v in replacements.items():
            s = s.replace(k, v)
            
        # Remove quotes for robustness, but KEEP spaces to match legacy keys
        s = s.replace('"', '').replace("'", "").replace('\n', '')
        # Only collapse multiple spaces to single space
        s = re.sub(r'\s+', ' ', s)
        return s.strip()

    c_title = clean(title)
    c_addr = clean(addr)
    return f"{c_title}_{c_addr}"

def get_manager_password(manager_name):
    """
    Generate simple password for manager.
    Uses first 3 characters (in lowercase romanization approximation) + 1234
    """
    first_syllable_map = {
        '김': 'kim', '이': 'lee', '박': 'park', '최': 'choi', '정': 'jung',
        '강': 'kang', '조': 'jo', '윤': 'yoon', '장': 'jang', '임': 'lim',
        '한': 'han', '오': 'oh', '서': 'seo', '신': 'shin', '권': 'kwon',
        '황': 'hwang', '안': 'ahn', '송': 'song', '류': 'ryu', '홍': 'hong',
        '전': 'jeon', '고': 'go', '문': 'moon', '양': 'yang', '손': 'son',
        '배': 'bae', '백': 'baek', '허': 'heo', '남': 'nam', '심': 'shim'
    }
    
    if manager_name and len(manager_name) > 0:
        first_char = manager_name[0]
        prefix = first_syllable_map.get(first_char, 'user')
        return f"{prefix}1234"
    return "user1234"

def mask_name(name):
    """
    Masks Korean names: 홍길동 -> 홍**, 이철 -> 이*
    """
    if not name or pd.isna(name):
        return name
    name_str = str(name)
    if len(name_str) <= 1:
        return name_str
    if len(name_str) == 2:
        return name_str[0] + "*"
    return name_str[0] + "*" * (len(name_str) - 2) + name_str[-1]
