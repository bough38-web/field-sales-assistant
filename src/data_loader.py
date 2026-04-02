
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
from src.utils import normalize_address, parse_coordinates_row, get_best_match, calculate_area, transformer, HAS_PYPROJ, safe_normalize

# [SPEED OPTIMIZATION] Global cache for branch configuration to prevent redundant file I/O
_KNOWN_BRANCHES_CACHE = None

def get_known_branches() -> List[str]:
    global _KNOWN_BRANCHES_CACHE
    if _KNOWN_BRANCHES_CACHE is not None:
        return _KNOWN_BRANCHES_CACHE
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'branch_config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                _KNOWN_BRANCHES_CACHE = [b['name'].replace('지사', '') for b in config['branches']]
        else:
            _KNOWN_BRANCHES_CACHE = ['중앙', '강북', '서대문', '고양', '의정부', '남양주', '강릉', '원주', '춘천']
    except:
        _KNOWN_BRANCHES_CACHE = ['중앙', '강북', '서대문', '고양', '의정부', '남양주', '강릉', '원주', '춘천']
    return _KNOWN_BRANCHES_CACHE

def normalize_str(s: Any) -> Optional[str]:
    if pd.isna(s): return s
    # [STRICT] Enforce NFC and standardized naming using centralized util
    b_norm = safe_normalize(s)
    
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
        
    # Use cached branch list to avoid redundant file I/O
    if b_norm in get_known_branches():
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
    High-Performance Vectorized Matching Engine. 
    Reduces complexity from O(N*M) to O(N+M) using Pandas vectorized operations.
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

    # 2. Normalize District Data (Vectorized)
    region_cols = ['주소시', '주소군구', '주소동']
    has_regional_cols = all(c in df_district.columns for c in region_cols)
    
    if not has_regional_cols:
        return target_df, [], "District file missing required regional columns (주소시, 주소군구, 주소동)."

    # Standardize District Columns
    dist_map = df_district[region_cols + ['관리지사', 'SP담당']].copy()
    for col in region_cols + ['관리지사', 'SP담당']:
        dist_map[col] = dist_map[col].apply(normalize_str)
            
    # Drop duplicates to ensure unique mapping
    dist_map = dist_map.drop_duplicates(subset=region_cols)

    # 3. Vectorized Pre-processing of Target Data
    addr_ser = target_df['소재지전체주소'].fillna('').astype(str).str.strip()
    addr_split = addr_ser.str.split(n=3)
    
    target_df['_tmp_city'] = addr_split.str[0].apply(normalize_str)
    target_df['_tmp_gu'] = addr_split.str[1].apply(normalize_str)
    target_df['_tmp_dong'] = addr_split.str[2].apply(normalize_str)

    # 4. [PHASE 1] Strict Vectorized Merge (City, Gu, Dong)
    for col in ['관리지사', 'SP담당']:
        if col in target_df.columns:
            target_df = target_df.drop(columns=[col])
            
    target_df = target_df.merge(
        dist_map, 
        left_on=['_tmp_city', '_tmp_gu', '_tmp_dong'], 
        right_on=['주소시', '주소군구', '주소동'], 
        how='left'
    ).drop(columns=['주소시', '주소군구', '주소동'])

    # 5. [PHASE 2] Road Address Fallback (Vectorized)
    unmatched_mask = target_df['관리지사'].isna()
    if unmatched_mask.any():
        road_addr = target_df.loc[unmatched_mask, '도로명전체주소'].fillna('').astype(str)
        extracted_dong = road_addr.str.extract(r'\(([^,)]+)').iloc[:, 0].apply(normalize_str)
        road_split = road_addr.str.split(n=2)
        extracted_city = road_split.str[0].apply(normalize_str)
        extracted_gu = road_split.str[1].apply(normalize_str)
        
        fallback_df = pd.DataFrame({
            '__idx': target_df.index[unmatched_mask],
            'f_city': extracted_city,
            'f_gu': extracted_gu,
            'f_dong': extracted_dong
        })
        
        fallback_results = fallback_df.merge(
            dist_map,
            left_on=['f_city', 'f_gu', 'f_dong'],
            right_on=['주소시', '주소군구', '주소동'],
            how='inner'
        )
        
        if not fallback_results.empty:
            target_df.loc[fallback_results['__idx'], '관리지사'] = fallback_results['관리지사'].values
            target_df.loc[fallback_results['__idx'], 'SP담당'] = fallback_results['SP담당'].values

    # 6. [PHASE 3] Wildcard/Base Dong Merge
    unmatched_mask = target_df['관리지사'].isna()
    if unmatched_mask.any():
        def strip_dong_num(s):
            if not isinstance(s, str): return s
            return re.sub(r'\d+동$', '동', s) if s.endswith('동') else s
            
        target_df.loc[unmatched_mask, '_tmp_dong_base'] = target_df.loc[unmatched_mask, '_tmp_dong'].apply(strip_dong_num)
        dist_map['_tmp_dong_base'] = dist_map['주소동'].apply(strip_dong_num)
        
        base_map = dist_map.drop_duplicates(subset=['주소시', '주소군구', '_tmp_dong_base'])
        
        fallback_df = target_df.loc[unmatched_mask, ['_tmp_city', '_tmp_gu', '_tmp_dong_base']].copy()
        fallback_df['__idx'] = fallback_df.index
        
        base_results = fallback_df.merge(
            base_map,
            left_on=['_tmp_city', '_tmp_gu', '_tmp_dong_base'],
            right_on=['주소시', '주소군구', '_tmp_dong_base'],
            how='inner'
        )
        
        if not base_results.empty:
            target_df.loc[base_results['__idx'], '관리지사'] = base_results['관리지사'].values
            target_df.loc[base_results['__idx'], 'SP담당'] = base_results['SP담당'].values

    # 7. [PHASE 4] City-level Fallback (Vectorized)
    unmatched_mask = target_df['관리지사'].isna()
    if unmatched_mask.any():
        prov_mask = target_df['_tmp_city'].isin(['서울', '경기', '인천', '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주'])
        fallback_city_keys = target_df['_tmp_city'].copy()
        fallback_city_keys.loc[prov_mask] = target_df.loc[prov_mask, '_tmp_gu']
        
        # Apply the fallback mapping dictionary
        city_fallbacks = fallback_city_keys.loc[unmatched_mask].map(lambda x: CITY_FALLBACK_MAP.get(x, None))
        
        def process_fallback_val(val, field):
            if not val: return '미지정'
            if isinstance(val, dict): return val.get(field, '미지정')
            return val if field == '관리지사' else '미지정'

        target_df.loc[unmatched_mask, '관리지사'] = city_fallbacks.apply(lambda x: process_fallback_val(x, 'branch'))
        target_df.loc[unmatched_mask, 'SP담당'] = city_fallbacks.apply(lambda x: process_fallback_val(x, 'mgr'))

    # 8. [FINAL OVERRIDE] Chuncheon to Wonju
    c_mask = target_df['관리지사'].astype(str).str.strip() == '춘천지사'
    target_df.loc[c_mask, '관리지사'] = '원주지사'
    target_df.loc[c_mask, 'SP담당'] = '김상태'

    # Fill NaNs and Cleanup
    target_df['관리지사'] = target_df['관리지사'].fillna('미지정')
    target_df['SP담당'] = target_df['SP담당'].fillna('미지정')
    
    cols_to_drop = [c for c in target_df.columns if c.startswith('_tmp_')]
    target_df = target_df.drop(columns=cols_to_drop)

    # 9. Generate Stats
    valid_mgrs = target_df[target_df['관리지사'] != '미지정']
    if not valid_mgrs.empty:
        mgr_info_df = valid_mgrs.groupby(['관리지사', 'SP담당']).size().reset_index(name='count')
        mgr_info = mgr_info_df.rename(columns={'관리지사': 'branch', 'SP담당': 'name'}).to_dict('records')
    else:
        mgr_info = []
            
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
            
            # [ROBUSTNESS] Map column names to standard keys
            col_map = {
                '인허가일자': next((c for c in df.columns if '인허가일자' in c or 'LICENS_DATE' in c), '인허가일자'),
                '영업상태명': next((c for c in df.columns if '영업상태명' in c or 'TRD_STATE_NM' in c or ('상태' in c and '코드' not in c)), '영업상태명'),
                '폐업일자': next((c for c in df.columns if '폐업일자' in c or 'CLS_DATE' in c), '폐업일자'),
                '사업장명': next((c for c in df.columns if '사업장명' in c or 'BPLC_NM' in c), '사업장명'),
                '소재지전체주소': next((c for c in df.columns if '소재지전체주소' in c or 'SITE_WHL_ADDR' in c), '소재지전체주소'),
                '도로명전체주소': next((c for c in df.columns if '도로명전체주소' in c or 'RDN_WHL_ADDR' in c), '도로명전체주소')
            }
            
            df_filtered = df.copy()
            # Ensure standard column names for processing internal logic
            for std_col, orig_col in col_map.items():
                if orig_col in df.columns and std_col != orig_col:
                    df_filtered[std_col] = df[orig_col]

            if '인허가일자' in df_filtered.columns:
                s_col = '영업상태명'
                if s_col in df_filtered.columns:
                    # [FIX] Standardize year parsing
                    df_filtered['parsed_open_dt'] = pd.to_datetime(df_filtered['인허가일자'], errors='coerce')
                    df_filtered['parsed_open_year'] = df_filtered['parsed_open_dt'].dt.year.fillna(0).astype(int)
                    
                    p_col = '폐업일자'
                    if p_col in df_filtered.columns:
                        df_filtered['parsed_close_dt'] = pd.to_datetime(df_filtered[p_col], errors='coerce')
                        df_filtered['parsed_close_year'] = df_filtered['parsed_close_dt'].dt.year.fillna(0).astype(int)
                    else:
                        df_filtered['parsed_close_dt'] = pd.NaT
                        df_filtered['parsed_close_year'] = 0

                    is_active = df_filtered[s_col].str.contains('영업|정상', na=False)
                    is_closed = df_filtered[s_col].str.contains('폐업|정지', na=False)
                    
                    is_recent_open = (df_filtered['parsed_open_year'] >= 2024)
                    is_recent_close = (df_filtered['parsed_close_year'] >= 2024)
                    
                    is_valid = (is_active & is_recent_open) | (is_closed & (is_recent_open | is_recent_close))
                    df_filtered = df_filtered[is_valid].copy()

                    # [NEW] Calculate '최종수정시점' (Last Modified)
                    df_filtered['최종수정시점'] = df_filtered[['parsed_open_dt', 'parsed_close_dt']].max(axis=1)
                    
                    # Cleanup temp columns
                    df_filtered = df_filtered.drop(columns=['parsed_open_dt', 'parsed_close_dt', 'parsed_open_year', 'parsed_close_year'])

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
