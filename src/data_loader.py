
import pandas as pd
import os
import zipfile
import glob
import streamlit as st
import requests
import xml.etree.ElementTree as ET
import unicodedata
import shutil
import numpy as np
from typing import Optional, Tuple, List, Dict, Any, Union
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import json
import re

# Import from local utils
from src.utils import normalize_address, parse_coordinates_row, get_best_match, calculate_area, transformer, HAS_PYPROJ

def normalize_str(s: Any) -> Optional[str]:
    if pd.isna(s): return s
    # [STRICT] Enforce NFC and standardized naming
    b_norm = unicodedata.normalize('NFC', str(s)).strip()
    
    # Standardize Seoul/Metropolitan names
    replacements = {
        "서울특별시": "서울", "서울시": "서울",
        "경기도": "경기", "경기": "경기",
        "인천광역시": "인천", "인천시": "인천",
        "강원특별자치도": "강원", "강원도": "강원",
        "충청북도": "충북", "충북": "충북",
        "충청남도": "충남", "충남": "충남",
        "전라북도": "전북", "전북": "전북", "전북특별자치도": "전북",
        "전라남도": "전남", "전남": "전남",
        "경상북도": "경북", "경북": "경북",
        "경상남도": "경남", "경남": "경남",
        "제주특별자치도": "제주", "제주도": "제주",
        "부산광역시": "부산", "부산시": "부산",
        "대구광역시": "대구", "대구시": "대구",
        "광주광역시": "광주", "광주시": "광주",
        "대전광역시": "대전", "대전시": "대전",
        "울산광역시": "울산", "울산시": "울산",
        "세종특별자치시": "세종", "세종시": "세종"
    }
    for k, v in replacements.items():
        if b_norm == k: return v
        
    # Load branches from config
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'branch_config.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            known_branches = [b['name'].replace('지사', '') for b in config['branches']]
    except:
        known_branches = ['중앙', '강북', '서대문', '고양', '의정부', '남양주', '강릉', '원주', '춘천']
        
    if b_norm in known_branches:
        return b_norm + '지사'
    return b_norm

# [FEATURE] Dedicated City-to-Branch Fallback Map for Unassigned Regions
CITY_FALLBACK_MAP = {
    '파주시': '고양지사',
    '고양시': '고양지사',
    '강릉시': '강릉지사',
    '속초시': '강릉지사',
    '양양군': '강릉지사',
    '고성군': '강릉지사',
    '원주시': '원주지사',
    '횡성군': '원주지사',
    '춘천시': {'branch': '원주지사', 'mgr': '김상태'},
    '의정부시': '의정부지사',
    '남양주시': '남양주지사',
    '포천시': '의정부지사',
    '양주시': '의정부지사',
    '동두천시': '의정부지사',
    '연천군': '의정부지사',
    '가평군': '남양주지사',
    '구리시': '남양주지사',
    '용산구': '중앙지사',
    '성북구': '중앙지사',
    '종로구': '중앙지사',
    '중구': '중앙지사',
    '동대문구': '중앙지사',
    '성동구': '중앙지사',
    '강북구': '강북지사',
    '도봉구': '강북지사',
    '노원구': '강북지사',
    '서대문구': '서대문지사',
    '마포구': '서대문지사',
    '은평구': '서대문지사'
}

def _process_and_merge_district_data(target_df: pd.DataFrame, district_file_path_or_obj: Any) -> Tuple[pd.DataFrame, List[Dict], Optional[str]]:
    """
    Common logic to process district file, match addresses, and merge with target_df.
    Updated for precise (City, Gu, Dong) matching.
    """
    # 1. Load District File
    try:
        if isinstance(district_file_path_or_obj, pd.DataFrame):
            df_district = district_file_path_or_obj
        elif isinstance(district_file_path_or_obj, str) and district_file_path_or_obj.startswith("http"):
            import io
            response = requests.get(district_file_path_or_obj, timeout=15)
            response.raise_for_status()
            df_district = pd.read_excel(io.BytesIO(response.content))
        else:
            df_district = pd.read_excel(district_file_path_or_obj)
    except Exception as e:
        return target_df, [], f"Error reading District file: {e}"

    # 2. Normalize District Data with Robust Column Mapping
    region_cols = ['주소시', '주소군구', '주소동']
    has_regional_cols = all(c in df_district.columns for c in region_cols)
    
    mapping_dict = {}
    if has_regional_cols:
        # Build strict mapping dictionary from regional columns
        for _, r in df_district.iterrows():
            city = normalize_str(r['주소시'])
            gu = normalize_str(r['주소군구'])
            dong = normalize_str(r['주소동'])
            if city and gu and dong:
                key = (city, gu, dong)
                mapping_dict[key] = {
                    '관리지사': normalize_str(r.get('관리지사', '미지정')),
                    'SP담당': normalize_str(r.get('SP담당', '미지정'))
                }
    else:
        # Fallback to column searching if exact columns missing
        addr_col = next((c for c in df_district.columns if any(p in c for p in ['설치주소', '도로명주소', '소재지주소', '주소'])), None)
        if addr_col:
            df_district['full_address_norm'] = df_district[addr_col].astype(str).apply(normalize_address)
            # Create a simplified mapping if possible, though exact match is preferred by USER
            pass

    # 3. Apply Mapping to Target Data (Exact Match on Address Parts)
    results = []
    for i in range(len(target_df)):
        addr_str = str(target_df.iloc[i].get('소재지전체주소', '')).strip()
        addr_parts = addr_str.split()
        matched_info = None

        if mapping_dict and len(addr_parts) >= 2:
            # [DEEP VALIDATION] Sliding Window Approach
            # Check all possible (City, Gu, Dong) combinations within the first 6 words.
            # This handles addresses like "Gyeonggi-do Goyang-si Ilsandong-gu Janghang-dong"
            # combinations: (Gyeonggi, Goyang, Ilsandong), (Goyang, Ilsandong, Janghang), etc.
            
            for start in range(min(4, len(addr_parts) - 1)):
                if matched_info: break
                
                c = normalize_str(addr_parts[start])
                
                # Case 1: Triple check (C, G, D) with combined parts (Si + Gu)
                if len(addr_parts) >= start + 3:
                    g = normalize_str(addr_parts[start+1])
                    d = normalize_str(addr_parts[start+2])
                    
                    # Try direct (C, G, D)
                    keys_to_try = [(c, g, d)]
                    
                    # Try combined (C, G1+G2, D) - handles "Goyang-si Ilsandong-gu"
                    if len(addr_parts) >= start + 4:
                        g_combined = normalize_str(addr_parts[start+1] + " " + addr_parts[start+2])
                        d_next = normalize_str(addr_parts[start+3])
                        keys_to_try.append((c, g_combined, d_next))
                    
                    for k_try in keys_to_try:
                        if k_try in mapping_dict:
                            matched_info = mapping_dict[k_try]
                            break
                    if matched_info: break
                    
                    # Case 2: Base Dong Match (on any of the above keys)
                    for k_try in keys_to_try:
                        tc, tg, td = k_try
                        td_str = str(td)
                        td_base = re.sub(r'\d+동$', '동', td_str) if td_str.endswith('동') else td_str
                        for (mc, mg, md), info in mapping_dict.items():
                            if mc == tc and mg == tg:
                                md_str = str(md)
                                md_base = re.sub(r'\d+동$', '동', md_str) if md_str.endswith('동') else md_str
                                if md_base == td_base:
                                    matched_info = info
                                    break
                        if matched_info: break
                    if matched_info: break

                    # Case 4: Wildcard/Masked Match (e.g. "Seongsu-dong*ga" -> "Seongsu-dong1ga")
                    for k_try in keys_to_try:
                        tc, tg, td = k_try
                        td_str = str(td)
                        if '*' in td_str:
                            clean_td = td_str.split('*')[0]
                            if len(clean_td) >= 2: # At least 2 chars for safety
                                for (mc, mg, md), info in mapping_dict.items():
                                    if mc == tc and mg == tg and str(md).startswith(clean_td):
                                        matched_info = info
                                        break
                        if matched_info: break
                    if matched_info: break

                # Case 3: Double check (G, D) if unique in dictionary for this City
                # Helpful for skipping intermediary "Si" or "Gu" segments.
                if not matched_info and len(addr_parts) >= start + 2:
                    g2 = normalize_str(addr_parts[start+1])
                    d2 = normalize_str(addr_parts[start+2]) if len(addr_parts) >= start + 3 else ""
                    # If we find a Gu/Dong pair that uniquely maps in this city
                    possible_matches = [info for (mc, mg, md), info in mapping_dict.items() if mc == c and (mg == g2 or md == g2)]
                    if len(possible_matches) == 1:
                        matched_info = possible_matches[0]
                        break
        # [FEATURE] Case 5: Road Name Address Fallback (도로명주소 활용)
        # If still unassigned, try extracting Dong from parentheses in '도로명전체주소'
        if not matched_info:
            road_addr = str(target_df.iloc[i].get('도로명전체주소', '')).strip()
            if road_addr and road_addr != 'nan':
                # Extract content in brackets: "성수동1가" from "... (성수동1가)"
                # Handle cases like (성수동, 래미안) by splitting at comma
                match = re.search(r'\(([^)]+)\)$', road_addr)
                if match:
                    bracket_content = match.group(1)
                    dong_candidates = [d.strip() for d in bracket_content.split(',')]
                    
                    # Try matching with extracted dong names
                    for d_cand in dong_candidates:
                        # Extract City/Gu from road address start
                        road_parts = road_addr.split()
                        if len(road_parts) >= 2:
                            c_road = normalize_str(road_parts[0])
                            g_road = normalize_str(road_parts[1])
                            d_road = normalize_str(d_cand)
                            
                            key_road = (c_road, g_road, d_road)
                            if key_road in mapping_dict:
                                matched_info = mapping_dict[key_road]
                                break
                                
                            # Try base-dong match for wildcard support in road names
                            d_road_base = re.sub(r'\d+동$', '동', d_road) if d_road.endswith('동') else d_road
                            for (mc, mg, md), info in mapping_dict.items():
                                if mc == c_road and mg == g_road:
                                    md_base = re.sub(r'\d+동$', '동', str(md)) if str(md).endswith('동') else str(md)
                                    if md_base == d_road_base:
                                        matched_info = info
                                        break
                            if matched_info: break

        # [FEATURE] City-level Fallback Match (e.g., Paju -> Goyang Branch)
        # This triggers if strict (City, Gu, Dong) match failed.
        if not matched_info and len(addr_parts) >= 2:
            city_name = normalize_str(addr_parts[0])
            # Skip Metropolitan/Province name and check the secondary city name
            if city_name in ['서울', '경기', '인천', '강원', '충청', '전라', '경상', '제주']:
                city_name = normalize_str(addr_parts[1])
            
            if city_name in CITY_FALLBACK_MAP:
                fallback_info = CITY_FALLBACK_MAP[city_name]
                if isinstance(fallback_info, dict):
                    matched_info = {
                        '관리지사': fallback_info.get('branch', '미지정'),
                        'SP담당': fallback_info.get('mgr', '미지정')
                    }
                else:
                    matched_info = {
                        '관리지사': fallback_info,
                        'SP담당': '미지정'
                    }
                    
        # [FEATURE] Default non-matching records to '미지정'
        if matched_info:
            results.append(matched_info)
        else:
            results.append({'관리지사': '미지정', 'SP담당': '미지정'})

    results_df = pd.DataFrame(results, index=target_df.index)
    
    # Clean up existing mapping columns if present before merging
    for col in ['관리지사', 'SP담당']:
        if col in target_df.columns:
            target_df = target_df.drop(columns=[col])
            
    target_df = pd.concat([target_df, results_df], axis=1)
    
            
    # [FIX] Robust User Request: Reassign all Chuncheon Branch records to Wonju (Representative: Kim Sang-tae)
    # Using strict NFC normalization and stripping to handle potential Unicode/whitespace inconsistencies.
    import unicodedata
    def _robust_norm(val):
        if pd.isna(val): return ""
        return unicodedata.normalize('NFC', str(val)).strip()
        
    c_mask = target_df['관리지사'].apply(_robust_norm) == '춘천지사'
    if c_mask.any():
        target_df.loc[c_mask, '관리지사'] = '원주지사'
        target_df.loc[c_mask, 'SP담당'] = '김상태'
            
    # 4. Generate Manager Info for statistics (Recalculated after override)
    mgr_info = []
    if '관리지사' in target_df.columns and 'SP담당' in target_df.columns:
        for branch in target_df['관리지사'].unique():
            if branch == '미지정': continue
            branch_df = target_df[target_df['관리지사'] == branch]
            for mgr in branch_df['SP담당'].unique():
                if mgr == '미지정': continue
                mgr_info.append({
                    'branch': branch, 
                    'name': mgr, 
                    'count': len(branch_df[branch_df['SP담당'] == mgr])
                })
            
    return target_df, mgr_info, None

@st.cache_data(show_spinner=False)
def load_and_process_data(zip_file_path: str, district_file_path_or_obj: Any, salt: str = ""):
    temp_dir = "temp_extracted"
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)

    try:
        zip_tasks = zip_file_path if isinstance(zip_file_path, list) else [zip_file_path]
        for zip_obj in zip_tasks:
            with zipfile.ZipFile(zip_obj, 'r') as zip_ref:
                for member in zip_ref.infolist():
                    if member.is_dir(): continue
                    filename = os.path.basename(member.filename)
                    if not filename.lower().endswith('.csv'): continue
                    base_name, ext = os.path.splitext(filename)
                    if len(base_name) > 60:
                        import hashlib
                        h = hashlib.md5(base_name.encode()).hexdigest()[:8]
                        base_name = base_name[:50] + "_" + h
                    target_path = os.path.join(temp_dir, base_name + ext)
                    with zip_ref.open(member) as source, open(target_path, "wb") as target:
                        shutil.copyfileobj(source, target)
    except Exception as e:
        return None, [], f"Error extracting ZIP: {e}", {}

    all_files = glob.glob(os.path.join(temp_dir, "**/*.csv"), recursive=True)
    dfs = []
    
    def generate_vectorized_record_key(df_in):
        if df_in is None or df_in.empty: return df_in
        t_ser = df_in.get('사업장명', pd.Series(['']*len(df_in), index=df_in.index)).fillna('').astype(str)
        a_ser = (df_in.get('소재지전체주소', pd.Series(['']*len(df_in), index=df_in.index)).fillna('')
                 .combine_first(df_in.get('도로명전체주소', pd.Series(['']*len(df_in), index=df_in.index)).fillna(''))
                 .combine_first(df_in.get('주소', pd.Series(['']*len(df_in), index=df_in.index)).fillna(''))
                 .astype(str))
        def v_clean(ser):
            import re
            repls = {"서울특별시": "서울", "서울시": "서울", "경기도": "경기", "기도": "경기"}
            for k, v in repls.items(): ser = ser.str.replace(k, v, regex=False)
            return ser.str.replace('"', '', regex=False).str.replace("'", "", regex=False).str.replace(r'\s+', ' ', regex=True).str.strip()
        df_in['record_key'] = v_clean(t_ser) + "_" + v_clean(a_ser)
        return df_in

    def extract_coordinates(df_in):
        if df_in is None or df_in.empty: return df_in
        
        # 1. Identify X, Y columns
        x_col = next((c for c in df_in.columns if '좌표정보x' in c.lower() or '좌표정보(x)' in c.lower()), None)
        y_col = next((c for c in df_in.columns if '좌표정보y' in c.lower() or '좌표정보(y)' in c.lower()), None)
        
        if not x_col or not y_col:
            # Try more generic names
            x_col = next((c for c in df_in.columns if c.lower() in ['x', 'lon', 'longitude', 'x좌표']), x_col)
            y_col = next((c for c in df_in.columns if c.lower() in ['y', 'lat', 'latitude', 'y좌표']), y_col)
        
        if x_col and y_col:
            # Apply parsing to all rows
            def _parse_row(row):
                return parse_coordinates_row(row, x_col, y_col)
            
            coords = df_in.apply(_parse_row, axis=1)
            df_in['lat'] = coords.apply(lambda x: x[0] if x else None)
            df_in['lon'] = coords.apply(lambda x: x[1] if x else None)
        else:
            # Ensure columns exist even if empty to prevent KeyError
            if 'lat' not in df_in.columns: df_in['lat'] = np.nan
            if 'lon' not in df_in.columns: df_in['lon'] = np.nan
            
        return df_in

    for file in all_files:
        try:
            df = None
            for enc in ['utf-8-sig', 'cp949']:
                try:
                    df = pd.read_csv(file, encoding=enc, on_bad_lines='skip', dtype=str, low_memory=False)
                    if any('주소' in str(c) for c in df.columns): break
                except: continue
            if df is None or df.empty: continue
            df_filtered = df.copy()
            if '인허가일자' in df.columns:
                # [FIX] Broaden search to '상태' to catch '영업상태', '상태명' etc.
                status_cols = [c for c in df.columns if '상태' in c and '코드' not in c]
                if not status_cols: # Fallback if nothing found
                    status_cols = [c for c in df.columns if '상태' in c]
                
                if status_cols:
                    s_col = status_cols[0]
                    # [FIX] Standardize year parsing for both license and closure
                    df['parsed_open_year'] = pd.to_numeric(df['인허가일자'].fillna('').astype(str).str.replace(r'[^0-9]', '', regex=True).str[:4], errors='coerce').fillna(0).astype(int)
                    
                    p_col = next((c for c in df.columns if '폐업일자' in c), None)
                    df['parsed_close_year'] = pd.to_numeric(df[p_col].fillna('').astype(str).str.replace(r'[^0-9]', '', regex=True).str[:4], errors='coerce').fillna(0).astype(int) if p_col else 0

                    is_active = df[s_col].str.contains('영업|정상', na=False)
                    is_closed = df[s_col].str.contains('폐업|정지', na=False)
                    
                    # [CRITICAL FIX] Allow recently opened ACTIVE businesses OR any CLOSED businesses with recent activity
                    # Active: Must be opened 2024+
                    # Closed: Can be old (opened before 2024) but MUST have closed/opened recently (2024+)
                    is_recent_open = (df['parsed_open_year'] >= 2024)
                    is_recent_close = (df['parsed_close_year'] >= 2024)
                    
                    is_valid = (is_active & is_recent_open) | (is_closed & (is_recent_open | is_recent_close))
                    
                    # [FALLBACK] If no closure date is available but it's marked as CLOSED, 
                    # and it's in a recent dataset, we might still want it. 
                    # But for now, strict recentness (2024+) is better to prevent data bloat.
                    
                    df_filtered = df[is_valid].copy()
                    # [FIX] Standardize status column name for UI/Reporting compatibility
                    df_filtered['영업상태명'] = df_filtered[s_col]

            if not df_filtered.empty:
                df_filtered = generate_vectorized_record_key(df_filtered)
                df_filtered = extract_coordinates(df_filtered)
                dfs.append(df_filtered)
        except: continue
            
    if not dfs: return None, [], "No valid CSV files found.", {}
    final_df = pd.concat(dfs, ignore_index=True)
    final_df, mgr_info, err = _process_and_merge_district_data(final_df, district_file_path_or_obj)
    return final_df, mgr_info, err, {'before': len(final_df), 'after': len(final_df)}

def fetch_openapi_data(auth_key: str, local_code: str, start_date: str, end_date: str) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    return None, "Not implemented in repair mode"

def process_api_data(target_df, district_file_path_or_obj):
    results = _process_and_merge_district_data(target_df, district_file_path_or_obj)
    return results[0], results[1], results[2], {'before': 0, 'after': 0}

def load_fixed_coordinates_data(file_path: str):
    try:
        df = pd.read_excel(file_path)
        return df, {}, "", {}
    except Exception as e: return None, {}, str(e), {}

def merge_activity_status(df: pd.DataFrame) -> pd.DataFrame:
    return df
