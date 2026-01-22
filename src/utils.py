import pandas as pd
import re
import unicodedata
from sklearn.metrics.pairwise import cosine_similarity
from difflib import SequenceMatcher

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

from typing import Optional, Any
import pandas as pd
import re

# ... existing code ...

def normalize_address(address: Optional[str]) -> Optional[str]:
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
    address = address.replace('강원특별자치도', '강원도')

    address = address.replace('세종특별자치시', '세종시')
    address = address.replace('서울특별시', '서울시')
    address = address.replace('  ', ' ') # Double spaces
    address = address.replace('-', '')
    
    if '*' in address or len(address) < 5:  # Too short or masked
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

def mask_name(name: Any) -> Optional[str]:
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
