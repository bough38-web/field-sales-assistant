
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

# Import from local utils
from src.utils import normalize_address, parse_coordinates_row, get_best_match, calculate_area, transformer, HAS_PYPROJ

def normalize_str(s: Any) -> Optional[str]:
    if pd.isna(s): return s
    return unicodedata.normalize('NFC', str(s)).strip()

def _process_and_merge_district_data(target_df: pd.DataFrame, district_file_path_or_obj: Any) -> Tuple[pd.DataFrame, List[Dict], Optional[str]]:
    """
    Common logic to process district file, match addresses, and merge with target_df.
    """
    # 1. Load District File
    try:
        df_district = pd.read_excel(district_file_path_or_obj)
    except Exception as e:
        return target_df, [], f"Error reading District file: {e}"

    # 2. Normalize District Data
    if '주소시' in df_district.columns:
        df_district['full_address'] = df_district[['주소시', '주소군구', '주소동']].astype(str).agg(' '.join, axis=1)
    elif '주소' in df_district.columns:
        df_district['full_address'] = df_district['주소']
        
    df_district['full_address'] = df_district['full_address'].apply(normalize_str)
    df_district['관리지사'] = df_district['관리지사'].apply(normalize_str)
    df_district['SP담당'] = df_district['SP담당'].apply(normalize_str)
    
    df_district['full_address_norm'] = df_district['full_address'].apply(normalize_address)
    df_district = df_district.dropna(subset=['full_address_norm'])
    
    # Deduplicate District Data
    df_district = df_district.drop_duplicates(subset=['full_address_norm'], keep='first')
    
    # 3. Prepare Target Data for Matching
    # Ensure target_df has '소재지전체주소'
    if '소재지전체주소' not in target_df.columns:
        # If API data lacked it or named differently, ensure mapped before calling this
        pass

    target_df['소재지전체주소_norm'] = target_df['소재지전체주소'].astype(str).apply(normalize_address)
    # Don't dropNA on target immediately, or we lose rows? 
    # Logic in previous code: target_df = target_df.dropna(subset=['소재지전체주소_norm'])
    # Yes, we can drop because we can't match without address
    target_df = target_df.dropna(subset=['소재지전체주소_norm'])

    # 4. Batch Matching Logic
    # Prepare Corpus (District)
    vectorizer = TfidfVectorizer(analyzer='char', ngram_range=(2, 3)).fit(df_district['full_address_norm'])
    district_matrix = vectorizer.transform(df_district['full_address_norm'])
    district_originals = df_district['full_address'].tolist()
    
    # Prepare Query (Target)
    target_addrs = target_df['소재지전체주소_norm'].tolist()
    
    matched_results = []
    
    if target_addrs:
        target_matrix = vectorizer.transform(target_addrs)
        
        # Chunked Processing
        chunk_size = 1000
        num_rows = target_matrix.shape[0]
        THRESHOLD = 0.5
        
        def extract_geo_tokens(addr):
            if not addr: return set()
            tokens = addr.split()
            return set(tokens[:2]) if len(tokens) >= 2 else set(tokens)

        for i in range(0, num_rows, chunk_size):
            end = min(i + chunk_size, num_rows)
            chunk_target = target_matrix[i:end]
            chunk_sim = cosine_similarity(chunk_target, district_matrix)
            
            chunk_best_indices = chunk_sim.argmax(axis=1)
            chunk_best_scores = chunk_sim.max(axis=1)
            
            for j, score in enumerate(chunk_best_scores):
                if score >= THRESHOLD:
                    candidate = district_originals[chunk_best_indices[j]]
                    query = target_addrs[i + j]
                    
                    q_tok = extract_geo_tokens(query)
                    c_tok = extract_geo_tokens(candidate)
                    
                    if q_tok.intersection(c_tok):
                        matched_results.append(candidate)
                    else:
                        matched_results.append(None)
                else:
                    matched_results.append(None)
    
    target_df['matched_address'] = matched_results
    
    # 5. Merge
    merge_cols = ['full_address', '관리지사', 'SP담당']
    if '영업구역 수정' in df_district.columns:
        merge_cols.append('영업구역 수정')
        
    final_df = target_df.merge(df_district[merge_cols], left_on='matched_address', right_on='full_address', how='left')
    
    # 6. Area Calculation
    site_area = pd.to_numeric(final_df['소재지면적'], errors='coerce').fillna(0)
    tot_area = pd.to_numeric(final_df['총면적'], errors='coerce').fillna(0)
    use_area = np.where(site_area > 0, site_area, tot_area)
    final_df['평수'] = (use_area / 3.3058).round(1)
    
    # 7. Final Cleanup
    # [FIX] Do not drop unassigned branches (`관리지사` is null or `미지정`). Keep them for Admin review.
    final_df['관리지사'] = final_df['관리지사'].fillna('미지정')
    # final_df = final_df.dropna(subset=['관리지사']) # Removed to keep unassigned
    # final_df = final_df[final_df['관리지사'] != '미지정'] # Removed to keep unassigned
    
    final_df['SP담당'] = final_df['SP담당'].fillna('미지정')
    if '영업구역 수정' in final_df.columns:
        final_df['영업구역 수정'] = final_df['영업구역 수정'].fillna('')
        
    # Extract Manager Info
    if '영업구역 수정' in df_district.columns:
        mgr_info = df_district[['SP담당', '영업구역 수정', '관리지사']].drop_duplicates().to_dict(orient='records')
    else:
        mgr_info = df_district[['SP담당', '관리지사']].drop_duplicates().to_dict(orient='records')
        
    return final_df, mgr_info, None

@st.cache_data
def load_and_process_data(zip_file_path_or_obj: Any, district_file_path_or_obj: Any, dist_mtime: Optional[float] = None) -> Tuple[Union[pd.DataFrame, None], List[Dict], Optional[str]]:
    """
    Loads data from uploads, extracts ZIP, processes CSVs, and merges with district data.
    """
    # 1. Process Zip File
    extract_folder = "temp_extracted_data"
    
    if os.path.exists(extract_folder):
        try: shutil.rmtree(extract_folder)
        except: pass
    os.makedirs(extract_folder, exist_ok=True)
    
    try:
        with zipfile.ZipFile(zip_file_path_or_obj, 'r') as zip_ref:
            zip_ref.extractall(extract_folder)
    except Exception as e:
        return None, [], f"ZIP extraction failed: {e}"
        
    all_files = glob.glob(os.path.join(extract_folder, "**/*.csv"), recursive=True)
    dfs = []
    
    for file in all_files:
        try:
            # Check header
            df_iter = pd.read_csv(file, encoding='cp949', on_bad_lines='skip', dtype=str, chunksize=1000)
            header = next(df_iter)
            if not any('주소' in c for c in header.columns): continue
                
            df = pd.read_csv(file, encoding='cp949', on_bad_lines='skip', dtype=str, low_memory=False)
            address_col = [c for c in df.columns if '주소' in c][0]
            
            # Filter standard headers
            df_filtered = df[df[address_col].str.contains('서울|경기|강원', na=False)]
            dfs.append(df_filtered)
        except Exception:
            continue
            
    if not dfs:
        return None, [], "No valid CSV files found in ZIP."
        
    concatenated_df = pd.concat(dfs, ignore_index=True)
    concatenated_df.drop_duplicates(subset=['사업장명', '소재지전체주소'], inplace=True)

    # Dynamic Column Mapping
    all_cols = concatenated_df.columns
    x_col = next((c for c in all_cols if '좌표' in c and ('x' in c.lower() or 'X' in c)), None)
    y_col = next((c for c in all_cols if '좌표' in c and ('y' in c.lower() or 'Y' in c)), None)
    
    desired_patterns = ['소재지전체주소', '도로명전체주소', '사업장명', '업태구분명', '영업상태명', 
                        '소재지전화', '총면적', '소재지면적', '인허가일자', '폐업일자', 
                        '재개업일자', '최종수정시점', '데이터기준일자']
    
    rename_map = {}
    selected_cols = []
    for pat in desired_patterns:
        match = next((c for c in all_cols if pat in c), None)
        if match:
            selected_cols.append(match)
            rename_map[match] = pat
            
    if x_col: selected_cols.append(x_col)
    if y_col: selected_cols.append(y_col)
    
    target_df = concatenated_df[list(set(selected_cols))].copy()
    target_df.rename(columns=rename_map, inplace=True)
    
    # Date Parsing
    for col in ['인허가일자', '폐업일자']:
        if col in target_df.columns:
            target_df[col] = pd.to_datetime(target_df[col], errors='coerce')
    
    if '인허가일자' in target_df.columns:
        target_df.sort_values(by='인허가일자', ascending=False, inplace=True)
        
    # Coordinate Parsing
    if x_col and y_col:
        x_c = x_col if x_col in target_df.columns else next((k for k,v in rename_map.items() if v == '좌표정보(X)'), x_col)
        y_c = y_col if y_col in target_df.columns else next((k for k,v in rename_map.items() if v == '좌표정보(Y)'), y_col)
        
        xs = pd.to_numeric(target_df[x_c], errors='coerce').values
        ys = pd.to_numeric(target_df[y_c], errors='coerce').values
        
        lats = np.full(xs.shape, np.nan)
        lons = np.full(ys.shape, np.nan)
        valid_mask = ~np.isnan(xs) & ~np.isnan(ys)
        
        if np.any(valid_mask):
             sample_x = xs[valid_mask]
             if np.median(sample_x) > 200 and HAS_PYPROJ:
                 try:
                     lon_v, lat_v = transformer.transform(xs[valid_mask], ys[valid_mask])
                     lats[valid_mask] = lat_v
                     lons[valid_mask] = lon_v
                 except: pass
             else:
                 lats = ys
                 lons = xs
        
        # Bound Check
        bad_mask = (lats < 30) | (lats > 45) | (lons < 120) | (lons > 140)
        lats[bad_mask] = np.nan
        lons[bad_mask] = np.nan
        
        target_df['lat'] = lats
        target_df['lon'] = lons
    else:
        target_df['lat'] = None
        target_df['lon'] = None
        
    # Delegate to common processor
    return _process_and_merge_district_data(target_df, district_file_path_or_obj)


def fetch_openapi_data(auth_key: str, local_code: str, start_date: str, end_date: str) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Fetches data from localdata.go.kr API.
    """
    base_url = "http://www.localdata.go.kr/platform/rest/TO0/openDataApi"
    params = {
        "authKey": auth_key,
        "localCode": local_code,
        "bgnYmd": start_date,
        "endYmd": end_date,
        "resultType": "xml", 
        "numOfRows": 1000, 
        "pageNo": 1
    }
    
    all_rows = []
    try:
        response = requests.get(base_url, params=params, timeout=20)
        if response.status_code != 200:
            return None, f"API Error: Status {response.status_code}"
            
        root = ET.fromstring(response.content)
        header = root.find("header")
        if header is not None:
             code = header.find("resultCode")
             msg = header.find("resultMsg")
             if code is not None and code.text != '00':
                 return None, f"API Logic Error: {msg.text if msg is not None else 'Unknown'}"
                 
        body = root.find("body")
        items = body.find("items") if body is not None else root.findall("row")
        if items is None or len(items) == 0:
            items = root.findall("row")
            
        if not items:
            # Try finding direct in root if xml structure is flat
            items = root.findall("row")
            
        if not items and hasattr(items, 'findall'):
             # If items is an Element (from body.find('items'))
             items = items.findall("item")

        if not items: return None, "No specific data found."

        def get_val(item, tags):
            for tag in tags:
                node = item.find(tag)
                if node is not None and node.text: return node.text
            return None

        for item in items:
            row_data = {}
            row_data['개방자치단체코드'] = get_val(item, ["opnSfTeamCode", "OPN_SF_TEAM_CODE"])
            row_data['관리번호'] = get_val(item, ["mgtNo", "MGT_NO"])
            row_data['개방서비스아이디'] = get_val(item, ["opnSvcId", "OPN_SVC_ID"])
            row_data['개방서비스명'] = get_val(item, ["opnSvcNm", "OPN_SVC_NM"])
            row_data['사업장명'] = get_val(item, ["bplcNm", "BPLC_NM"])
            row_data['소재지전체주소'] = get_val(item, ["siteWhlAddr", "SITE_WHL_ADDR"])
            row_data['도로명전체주소'] = get_val(item, ["rdnWhlAddr", "RDN_WHL_ADDR"])
            row_data['소재지전화'] = get_val(item, ["siteTel", "SITE_TEL"])
            row_data['인허가일자'] = get_val(item, ["apvPermYmd", "APV_PERM_YMD"])
            row_data['폐업일자'] = get_val(item, ["dcbYmd", "DCB_YMD"])
            row_data['휴업시작일자'] = get_val(item, ["clgStdt", "CLG_STDT"])
            row_data['휴업종료일자'] = get_val(item, ["clgEnddt", "CLG_ENDDT"])
            row_data['재개업일자'] = get_val(item, ["ropnYmd", "ROPN_YMD"])
            row_data['영업상태명'] = get_val(item, ["trdStateNm", "TRD_STATE_NM"])
            row_data['업태구분명'] = get_val(item, ["uptaeNm", "UPTAE_NM"])
            row_data['좌표정보(X)'] = get_val(item, ["x", "X"])
            row_data['좌표정보(Y)'] = get_val(item, ["y", "Y"])
            row_data['소재지면적'] = get_val(item, ["siteArea", "SITE_AREA"])
            row_data['총면적'] = get_val(item, ["totArea", "TOT_AREA"])
            all_rows.append(row_data)
            
    except Exception as e:
        return None, f"Fetch Exception: {e}"
        
    if not all_rows: return None, "Parsed 0 rows."
    return pd.DataFrame(all_rows), None

@st.cache_data
def process_api_data(target_df: pd.DataFrame, district_file_path_or_obj: Any) -> Tuple[Union[pd.DataFrame, None], List[Dict], Optional[str]]:
    """
    Processes API data and merges with district.
    """
    if target_df is None or target_df.empty:
        return None, [], "API DataFrame is empty."
        
    x_col = '좌표정보(X)'
    y_col = '좌표정보(Y)'
    
    # Coordinate parsing
    if x_col in target_df.columns and y_col in target_df.columns:
         # Check if we need to call parse_coordinates_row.
         # But in `load_and_process`, we did vectorized. Let's do vectorized here too if possible?
         # `parse_coordinates_row` handles the logic row-by-row safely.
         # For consistency with previous API logic, let's keep it or improve.
         # Improve: use vectorized if possible, but row-by-row is safer for mixed API data.
         target_df['lat'], target_df['lon'] = zip(*target_df.apply(lambda row: parse_coordinates_row(row, x_col, y_col), axis=1))
    else:
         target_df['lat'] = None
         target_df['lon'] = None
         
    for col in ['인허가일자', '폐업일자', '휴업시작일자', '휴업종료일자', '재개업일자']:
        if col in target_df.columns:
            target_df[col] = pd.to_datetime(target_df[col], format='%Y%m%d', errors='coerce')
            
    if '인허가일자' in target_df.columns:
        target_df.sort_values(by='인허가일자', ascending=False, inplace=True)

    # Delegate to common processor
    return _process_and_merge_district_data(target_df, district_file_path_or_obj)
