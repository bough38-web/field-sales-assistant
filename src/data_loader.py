import pandas as pd
import os
import zipfile
import glob
import streamlit as st
import requests
import xml.etree.ElementTree as ET
import unicodedata
from sklearn.feature_extraction.text import TfidfVectorizer

# Import from local utils (assuming src is a package or in path)
# When running app.py from root, 'src.utils' is the way if src has __init__.py
# For now, we will assume this file is imported as 'src.data_loader'
from src.utils import normalize_address, parse_coordinates_row, get_best_match, calculate_area, transformer, HAS_PYPROJ

def normalize_str(s):
    if pd.isna(s): return s
    return unicodedata.normalize('NFC', str(s)).strip()

import shutil
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

@st.cache_data
def load_and_process_data(zip_file_path_or_obj, district_file_path_or_obj):
    """
    Loads data from the uploaded ZIP file/path and District Excel file/path, 
    performs processing and matching.
    """
    
    # 1. Process Zip File
    extract_folder = "temp_extracted_data"
    
    # [OPTIMIZATION] Cleanup Temp Folder
    if os.path.exists(extract_folder):
        try:
            shutil.rmtree(extract_folder)
        except:
            pass
    os.makedirs(extract_folder, exist_ok=True)
    
    try:
        with zipfile.ZipFile(zip_file_path_or_obj, 'r') as zip_ref:
            zip_ref.extractall(extract_folder)
    except Exception as e:
        return None, f"ZIP extraction failed: {e}"
        
    all_files = glob.glob(os.path.join(extract_folder, "**/*.csv"), recursive=True)
    
    dfs = []
    
    for file in all_files:
        try:
            # Read header first
            df_iter = pd.read_csv(file, encoding='cp949', on_bad_lines='skip', dtype=str, chunksize=1000)
            header = next(df_iter)
            
            # Check for address column
            cols = header.columns
            if not any('주소' in c for c in cols):
                continue
                
            # Read full file
            df = pd.read_csv(file, encoding='cp949', on_bad_lines='skip', dtype=str, low_memory=False)
            
            address_col = [c for c in df.columns if '주소' in c][0]
            
            # [FIX] Allow ALL regions (removed hardcoded filter for Seoul/Gyeonggi/Gangwon/Incheon)
            # df_filtered = df[df[address_col].str.contains('서울|경기|강원|인천', na=False)]
            df_filtered = df  # Keep all data
            dfs.append(df_filtered)
            
        except Exception as e:
            continue
            
    if not dfs:
        return None, "No valid/relevant CSV files found in ZIP."
        
    concatenated_df = pd.concat(dfs, ignore_index=True)
    
    # Deduplicate
    concatenated_df.drop_duplicates(subset=['사업장명', '소재지전체주소'], inplace=True)

    # Dynamic Column Selection
    all_cols = concatenated_df.columns
    x_col = next((c for c in all_cols if '좌표' in c and ('x' in c.lower() or 'X' in c)), None)
    y_col = next((c for c in all_cols if '좌표' in c and ('y' in c.lower() or 'Y' in c)), None)
    
    desired_patterns = ['소재지전체주소', '도로명전체주소', '사업장명', '업태구분명', '영업상태명', 
                        '소재지전화', '총면적', '소재지면적', '인허가일자', '폐업일자', 
                        '재개업일자', '최종수정시점', '데이터기준일자']
    
    # Map desired patterns to actual columns
    selected_cols = []
    rename_map = {}
    
    for pat in desired_patterns:
        match = next((c for c in all_cols if pat in c), None)
        if match:
            selected_cols.append(match)
            rename_map[match] = pat # Normalize name if slightly different
            
    # Include coords in selection
    if x_col: selected_cols.append(x_col)
    if y_col: selected_cols.append(y_col)
    
    target_df = concatenated_df[list(set(selected_cols))].copy()
    target_df.rename(columns=rename_map, inplace=True)
    
    # Date Parsing (After Renaming) - Robust Inference
    if '인허가일자' in target_df.columns:
        target_df['인허가일자'] = pd.to_datetime(target_df['인허가일자'], errors='coerce')
        
    if '폐업일자' in target_df.columns:
        target_df['폐업일자'] = pd.to_datetime(target_df['폐업일자'], errors='coerce')
        
    # Sort by Permit Date if available
    if '인허가일자' in target_df.columns:
        target_df.sort_values(by='인허가일자', ascending=False, inplace=True)
    
    # Coordinate Parsing
    # Coordinate Parsing (Vectorized)
    if x_col and y_col:
        x_c = x_col if x_col in target_df.columns else next((k for k,v in rename_map.items() if v == '좌표정보(X)'), x_col)
        y_c = y_col if y_col in target_df.columns else next((k for k,v in rename_map.items() if v == '좌표정보(Y)'), y_col)
        
        # Safe numeric conversion
        xs = pd.to_numeric(target_df[x_c], errors='coerce').values
        ys = pd.to_numeric(target_df[y_c], errors='coerce').values
        
        lats = np.full(xs.shape, np.nan)
        lons = np.full(ys.shape, np.nan)
        
        valid_mask = ~np.isnan(xs) & ~np.isnan(ys)
        
        if np.any(valid_mask):
             # Check if data is already Lat/Lon (Small numbers) or Projected (Large numbers)
             # Heuristic: Median of X. If > 200, it's likely projected (e.g. 190000)
             sample_x = xs[valid_mask]
             if np.median(sample_x) > 200 and HAS_PYPROJ:
                 # Transform
                 x_valid = xs[valid_mask]
                 y_valid = ys[valid_mask]
                 
                 try:
                     lon_v, lat_v = transformer.transform(x_valid, y_valid)
                     lats[valid_mask] = lat_v
                     lons[valid_mask] = lon_v
                 except Exception:
                     pass # Fallback or keep NaN
             else:
                 # Assume Lat/Lon (X=Lon, Y=Lat)
                 # Validate Range: Lat 30-45, Lon 120-140
                 # existing code heuristic: return y, x
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


    # 3. Process District File
    try:
        df_district = pd.read_excel(district_file_path_or_obj)
    except Exception as e:
        return None, f"Error reading District file: {e}"

    # Normalize Addresses
    if '주소시' in df_district.columns:
        df_district['full_address'] = df_district[['주소시', '주소군구', '주소동']].astype(str).agg(' '.join, axis=1)
    elif '주소' in df_district.columns:
        df_district['full_address'] = df_district['주소']
        
    # [FIX] Strict Cleaning with NFC Normalization
    df_district['full_address'] = df_district['full_address'].apply(normalize_str)
    df_district['관리지사'] = df_district['관리지사'].apply(normalize_str)
    df_district['SP담당'] = df_district['SP담당'].apply(normalize_str)
    
    df_district['full_address_norm'] = df_district['full_address'].apply(normalize_address)
    df_district = df_district.dropna(subset=['full_address_norm'])
    
    # [FIX] Deduplicate District Data to prevent 1-to-Many explosion
    # Keep the first occurrence.
    df_district = df_district.drop_duplicates(subset=['full_address_norm'], keep='first')
    
    target_df['소재지전체주소_norm'] = target_df['소재지전체주소'].astype(str).apply(normalize_address)
    target_df = target_df.dropna(subset=['소재지전체주소_norm'])

    # 4. Matching Logic (Batch Optimized)
    # [OPTIMIZATION] Batch Vectorization instead of row-by-row
    
    # A. Prepare Corpus (District)
    vectorizer = TfidfVectorizer(analyzer='char', ngram_range=(2, 3)).fit(df_district['full_address_norm'])
    district_matrix = vectorizer.transform(df_district['full_address_norm'])
    district_choices = df_district['full_address_norm'].tolist()
    district_originals = df_district['full_address'].tolist()
    
    # B. Prepare Query (Target)
    target_addrs = target_df['소재지전체주소_norm'].tolist()
    if not target_addrs:
        return target_df, None # Empty
        
    target_matrix = vectorizer.transform(target_addrs)
    
    # C. Compute Cosine Similarity (Query x Corpus) - CHUNKED to prevent Memory Overflow
    # If N=50k, M=50k, Matrix=2.5B floats => 20GB RAM. We must chunk.
    
    chunk_size = 1000
    num_rows = target_matrix.shape[0]
    
    matched_results = []
    
    # Threshold
    THRESHOLD = 0.5 
    
    # [FIX] Geographic Validation Helper
    def extract_geo_tokens(addr):
        if not addr: return set()
        tokens = addr.split()
        return set(tokens[:2]) if len(tokens) >= 2 else set(tokens)

    for i in range(0, num_rows, chunk_size):
        end = min(i + chunk_size, num_rows)
        chunk_target = target_matrix[i:end]
        
        # Compute similarity for this chunk: (ChunkSize x M)
        # 1000 x 50000 = 50M floats = 400MB (Manageable)
        chunk_sim = cosine_similarity(chunk_target, district_matrix)
        
        # Find best for this chunk
        chunk_best_indices = chunk_sim.argmax(axis=1)
        chunk_best_scores = chunk_sim.max(axis=1)
        
        # Process results for this chunk
        for j, score in enumerate(chunk_best_scores):
            if score >= THRESHOLD:
                candidate = district_originals[chunk_best_indices[j]]
                # Original global index is i + j
                query = target_addrs[i + j]
                
                # Geo Validation
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
    
    # Area Calculation
    # Area Calculation (Vectorized)
    # final_df['평수'] = final_df.apply(calculate_area, axis=1) # Old Slow Way
    site_area = pd.to_numeric(final_df['소재지면적'], errors='coerce').fillna(0)
    tot_area = pd.to_numeric(final_df['총면적'], errors='coerce').fillna(0)
    # Use site_area if > 0 else tot_area. 
    # Vectorized 'where': np.where(condition, x, y)
    use_area = np.where(site_area > 0, site_area, tot_area)
    final_df['평수'] = (use_area / 3.3058).round(1)
    
    # Fill NA
    # [OPTIMIZATION] Drop Unassigned Data
    # User Request: Exclude 'Unassigned' completely to improve loading speed.
    final_df = final_df.dropna(subset=['관리지사'])
    
    # Optional: If you still need to ensure string type for safety
    # final_df['관리지사'] = final_df['관리지사'].astype(str)
    # final_df['SP담당'] = final_df['SP담당'].fillna('미지정') # Manager can still be NA even if Branch flows? Usually strictly coupled.
    # Let's clean perfectly:
    final_df = final_df[final_df['관리지사'] != '미지정'] # In case it was somehow '미지정' string already
    
    # Ensure SP담당 is clean (if branch exists but manager is empty in Excel)
    final_df['SP담당'] = final_df['SP담당'].fillna('미지정')
    if '영업구역 수정' in final_df.columns:
        final_df['영업구역 수정'] = final_df['영업구역 수정'].fillna('')
    
    return final_df, None

def fetch_openapi_data(auth_key, local_code, start_date, end_date):
    """
    Fetches data from localdata.go.kr API.
    Returns (DataFrame, error_message).
    """
    # Base URL
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
        if body is None:
             items = root.findall("row")
        else:
             items = body.find("items")
             if items is not None:
                 items = items.findall("item")
             else:
                 items = root.findall("row")

        if not items:
             items = root.findall("row")
        
        if not items:
             return None, "No data found (XML parsing could not find 'row' or 'item' tags)."
             
        def get_val(item, tags):
            for tag in tags:
                node = item.find(tag)
                if node is not None and node.text:
                    return node.text
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
        
    if not all_rows:
        return None, "Parsed 0 rows."
        
    return pd.DataFrame(all_rows), None

@st.cache_data
def process_api_data(target_df, district_file_path_or_obj):
    """
    Processes the DataFrame fetched from API, merging it with district data.
    """
    if target_df is None or target_df.empty:
        return None, "API DataFrame is empty."
        
    x_col = '좌표정보(X)'
    y_col = '좌표정보(Y)'
    
    if x_col in target_df.columns and y_col in target_df.columns:
         target_df['lat'], target_df['lon'] = zip(*target_df.apply(lambda row: parse_coordinates_row(row, x_col, y_col), axis=1))
    else:
         target_df['lat'] = None
         target_df['lon'] = None
         
    for col in ['인허가일자', '폐업일자', '휴업시작일자', '휴업종료일자', '재개업일자']:
        if col in target_df.columns:
            target_df[col] = pd.to_datetime(target_df[col], format='%Y%m%d', errors='coerce')
            
    if '인허가일자' in target_df.columns:
        target_df.sort_values(by='인허가일자', ascending=False, inplace=True)

    # Process District File
    try:
        df_district = pd.read_excel(district_file_path_or_obj)
    except Exception as e:
        return None, f"Error reading District file: {e}"

    if '주소시' in df_district.columns:
        df_district['full_address'] = df_district[['주소시', '주소군구', '주소동']].astype(str).agg(' '.join, axis=1)
    elif '주소' in df_district.columns:
        df_district['full_address'] = df_district['주소']
        
    df_district['full_address_norm'] = df_district['full_address'].apply(normalize_address)
    df_district = df_district.dropna(subset=['full_address_norm'])
    
    target_df['소재지전체주소_norm'] = target_df['소재지전체주소'].astype(str).apply(normalize_address)
    
    # Matching Logic
    vectorizer = TfidfVectorizer(analyzer='char', ngram_range=(2, 3)).fit(df_district['full_address_norm'])
    tfidf_matrix = vectorizer.transform(df_district['full_address_norm'])
    choices = df_district['full_address_norm'].tolist()
    norm_to_original = dict(zip(df_district['full_address_norm'], df_district['full_address']))
    
    target_df = target_df.dropna(subset=['소재지전체주소_norm'])
    
    def match_row(row):
        addr = row['소재지전체주소_norm']
        matched = get_best_match(addr, choices, vectorizer, tfidf_matrix)
        return norm_to_original.get(matched) if matched else None

    target_df['matched_address'] = target_df.apply(match_row, axis=1)
    
    # Merge
    merge_cols = ['full_address', '관리지사', 'SP담당']
    final_df = target_df.merge(df_district[merge_cols], left_on='matched_address', right_on='full_address', how='left')
    
    # Area
    # Area Calculation (Vectorized)
    site_area = pd.to_numeric(final_df['소재지면적'], errors='coerce').fillna(0)
    tot_area = pd.to_numeric(final_df['총면적'], errors='coerce').fillna(0)
    use_area = np.where(site_area > 0, site_area, tot_area)
    final_df['평수'] = (use_area / 3.3058).round(1)
    
    # Fill NA
    final_df['관리지사'] = final_df['관리지사'].fillna('미지정')
    final_df['SP담당'] = final_df['SP담당'].fillna('미지정')
    
    return final_df, None
