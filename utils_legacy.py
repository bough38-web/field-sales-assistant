import pandas as pd
import os
import zipfile
import glob
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from difflib import SequenceMatcher
import streamlit as st

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
    # Note: 5174 is common for these datasets but sometimes needs 5174->5174 legacy tweaking.
    # We will try standard first.
    transformer = Transformer.from_crs("epsg:5174", "epsg:4326", always_xy=True)
    HAS_PYPROJ = True
except ImportError:
    HAS_PYPROJ = False

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
    address = address.replace('강원특별자치도', '강원도')
    address = address.replace('세종특별자치시', '세종시')
    address = address.replace('서울특별시', '서울시')
    address = address.replace('  ', ' ') # Double spaces
    address = address.replace('-', '')
    
    if '*' in address or len(address) < 8:  # Too short or masked
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
        tfidf_vec = vectorizer.transform([address])
        cosine_sim = cosine_similarity(tfidf_vec, tfidf_matrix).flatten()
        # Get top candidate
        best_idx = cosine_sim.argmax()
        best_cosine_score = cosine_sim[best_idx]
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
            score = fuzz.ratio(address, choice) / 100.0
        else:
            # Difflib: 0-1 scale
            score = SequenceMatcher(None, address, choice).ratio()
            
        if score > best_score:
            best_score = score
            best_match = choice
            
    # Combine signals: Max of cosine and edit distance logic
    # Actually, edit distance is usually better for small typos.
    final_score = max(best_score, best_cosine_score)
    
    if final_score >= threshold:
        return best_match
    
    return None

def get_local_data_paths(data_dir="data"):
    """
    Scans the data directory for ZIP and Excel files.
    Returns (zip_path, excel_path) or None.
    """
    if not os.path.exists(data_dir):
        return None, None
        
    zips = glob.glob(os.path.join(data_dir, "*.zip"))
    excels = glob.glob(os.path.join(data_dir, "*.xlsx"))
    
    if not zips or not excels:
        return None, None
        
    # Return the first found (or most recent could be added)
    return zips[0], excels[0]

@st.cache_data
def load_and_process_data(zip_file_path_or_obj, district_file_path_or_obj):
    """
    Loads data from the uploaded ZIP file/path and District Excel file/path, 
    performs processing and matching.
    """
    
    # 1. Process Zip File
    extract_folder = "temp_extracted_data"
    os.makedirs(extract_folder, exist_ok=True)
    
    # Handle both file path (string) and uploaded file (BytesIO)
    is_path = isinstance(zip_file_path_or_obj, str)
    
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
            
            # Filter rows (Seoul/Gyeonggi/Gangwon)
            df_filtered = df[df[address_col].str.contains('서울|경기|강원', na=False)]
            dfs.append(df_filtered)
            
        except Exception as e:
            continue
            
    if not dfs:
        return None, "No valid/relevant CSV files found in ZIP."
        
    concatenated_df = pd.concat(dfs, ignore_index=True)
    
    # Deduplicate
    concatenated_df.drop_duplicates(subset=['사업장명', '소재지전체주소'], inplace=True)
    
    # (Date parsing moved to after column normalization)

    # Dynamic Column Selection
    # Find Coordinate Columns (X, Y)
    all_cols = concatenated_df.columns
    x_col = next((c for c in all_cols if '좌표' in c and ('x' in c.lower() or 'X' in c)), None)
    y_col = next((c for c in all_cols if '좌표' in c and ('y' in c.lower() or 'Y' in c)), None)
    
    desired_patterns = ['소재지전체주소', '도로명전체주소', '사업장명', '업태구분명', '영업상태명', 
                        '소재지전화', '총면적', '소재지면적', '인허가일자', '폐업일자']
    
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
    if x_col and y_col:
        # Use the original names for x_col/y_col as they might not be in rename_map yet or might be aliased
        # Just pass the actual column names in the sub-df
        x_c = x_col if x_col in target_df.columns else next((k for k,v in rename_map.items() if v == '좌표정보(X)'), x_col)
        y_c = y_col if y_col in target_df.columns else next((k for k,v in rename_map.items() if v == '좌표정보(Y)'), y_col)
        
        target_df['lat'], target_df['lon'] = zip(*target_df.apply(lambda row: parse_coordinates_row(row, x_col, y_col), axis=1))
    else:
        target_df['lat'] = None
        target_df['lon'] = None


    # 3. Process District File
    try:
        df_district = pd.read_excel(district_file_path_or_obj)
    except Exception as e:
        return None, f"Error reading District file: {e}"

    # Normalize Addresses
    # Construct full address from components if needed
    if '주소시' in df_district.columns:
        df_district['full_address'] = df_district[['주소시', '주소군구', '주소동']].astype(str).agg(' '.join, axis=1)
    elif '주소' in df_district.columns:
        df_district['full_address'] = df_district['주소']
        
    df_district['full_address_norm'] = df_district['full_address'].apply(normalize_address)
    df_district = df_district.dropna(subset=['full_address_norm'])
    
    target_df['소재지전체주소_norm'] = target_df['소재지전체주소'].astype(str).apply(normalize_address)
    
    # 4. Matching Logic
    # Prepare Vectorizer
    vectorizer = TfidfVectorizer(analyzer='char', ngram_range=(2, 3)).fit(df_district['full_address_norm'])
    tfidf_matrix = vectorizer.transform(df_district['full_address_norm'])
    choices = df_district['full_address_norm'].tolist()
    # Keep mapping-back dictionary
    norm_to_original = dict(zip(df_district['full_address_norm'], df_district['full_address']))
    
    # Match
    target_df = target_df.dropna(subset=['소재지전체주소_norm'])
    
    def match_row(row):
        addr = row['소재지전체주소_norm']
        matched = get_best_match(addr, choices, vectorizer, tfidf_matrix)
        # Return Original address for merge
        return norm_to_original.get(matched) if matched else None

    target_df['matched_address'] = target_df.apply(match_row, axis=1)
    
    # 5. Merge
    # We merge on the original full address since that's what we recovered
    # Check for '영업구역 수정' column, use if available
    merge_cols = ['full_address', '관리지사', 'SP담당']
    if '영업구역 수정' in df_district.columns:
        merge_cols.append('영업구역 수정')
        
    final_df = target_df.merge(df_district[merge_cols], left_on='matched_address', right_on='full_address', how='left')
    
    # Area Calculation
    def calculate_area(row):
        val = row.get('소재지면적', 0)
        if pd.isna(val) or val == 0: val = row.get('총면적', 0)
        try:
            return round(float(val) / 3.3058, 1)
        except:
            return 0
            
    final_df['평수'] = final_df.apply(calculate_area, axis=1)
    
    # Fill NA
    final_df['관리지사'] = final_df['관리지사'].fillna('미지정')
    final_df['SP담당'] = final_df['SP담당'].fillna('미지정')
    if '영업구역 수정' in final_df.columns:
        final_df['영업구역 수정'] = final_df['영업구역 수정'].fillna('')
    
    return final_df, None

def fetch_openapi_data(auth_key, local_code, start_date, end_date):
    """
    Fetches data from localdata.go.kr API.
    Returns (DataFrame, error_message).
    """
    import requests
    import xml.etree.ElementTree as ET
    
    # Base URL (Adjusted based on common structure, assuming 'openDataApi' is correct)
    # Sample: http://www.localdata.go.kr/platform/rest/{TYPE}/openDataApi?authKey=...
    # We will try 'TO0' (Integrated) as per common usage.
    base_url = "http://www.localdata.go.kr/platform/rest/TO0/openDataApi"
    
    params = {
        "authKey": auth_key,
        "localCode": local_code,
        "bgnYmd": start_date,
        "endYmd": end_date,
        "resultType": "xml", 
        "numOfRows": 1000, # Request largely
        "pageNo": 1
    }
    
    # We might need to iterate pages, but start with one valid fetch
    all_rows = []
    
    try:
        response = requests.get(base_url, params=params, timeout=20)
        if response.status_code != 200:
            return None, f"API Error: Status {response.status_code}"
            
        root = ET.fromstring(response.content)
        
        # Check Result Code
        header = root.find("header")
        if header is not None:
             code = header.find("resultCode")
             msg = header.find("resultMsg")
             if code is not None and code.text != '00':
                 return None, f"API Logic Error: {msg.text if msg is not None else 'Unknown'}"
                 
        body = root.find("body")
        if body is None:
             # structure might be flat depending on API version
             items = root.findall("row")
        else:
             items = body.find("items")
             if items is not None:
                 items = items.findall("item") # standard portal structure
             else:
                 items = root.findall("row") # localdata structure often uses 'row' directly

        if not items:
             # Try finding 'row' directly under root (common in localdata)
             items = root.findall("row")
        
        if not items:
             return None, "No data found (XML parsing could not find 'row' or 'item' tags)."
             
        if not items:
             return None, "No data found (XML parsing could not find 'row' or 'item' tags)."
             
        def get_val(item, tags):
            # Helper to find text from multiple potential tag names
            for tag in tags:
                node = item.find(tag)
                if node is not None and node.text:
                    return node.text
            return None

        for item in items:
            row_data = {}
            # Map simplified names to standard names used in our app
            # Checking both CamelCase (Sample) and UPPER_SNAKE (Portal Spec)
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
    Similar logic to load_and_process_data but simplified for API dataframe.
    """
    if target_df is None or target_df.empty:
        return None, "API DataFrame is empty."
        
    # 1. Parse Coordinates (API often provides X/Y in GRS80 or similar)
    # The sample code implied X/Y exists. We'll try to parse/convert.
    # Note: localdata API typically uses GRS80 (EPSG:5174 compatible logic usually works or needs specific proj string)
    # We will try the same logic as CSV.
    
    x_col = '좌표정보(X)'
    y_col = '좌표정보(Y)'
    
    if x_col in target_df.columns and y_col in target_df.columns:
         target_df['lat'], target_df['lon'] = zip(*target_df.apply(lambda row: parse_coordinates_row(row, x_col, y_col), axis=1))
    else:
         target_df['lat'] = None
         target_df['lon'] = None
         
    # 2. Date Parsing
    # API data is yyyymmdd string from XML.
    for col in ['인허가일자', '폐업일자', '휴업시작일자', '휴업종료일자', '재개업일자']:
        if col in target_df.columns:
            target_df[col] = pd.to_datetime(target_df[col], format='%Y%m%d', errors='coerce')
            
    # Sort
    if '인허가일자' in target_df.columns:
        target_df.sort_values(by='인허가일자', ascending=False, inplace=True)

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
        
    df_district['full_address_norm'] = df_district['full_address'].apply(normalize_address)
    df_district = df_district.dropna(subset=['full_address_norm'])
    
    target_df['소재지전체주소_norm'] = target_df['소재지전체주소'].astype(str).apply(normalize_address)
    
    # 4. Matching Logic
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
    
    # 5. Merge
    merge_cols = ['full_address', '관리지사', 'SP담당']
    final_df = target_df.merge(df_district[merge_cols], left_on='matched_address', right_on='full_address', how='left')
    
    # Area Calculation
    def calculate_area(row):
        val = row.get('소재지면적', 0)
        if pd.isna(val) or val == 0: val = row.get('총면적', 0)
        try:
            return round(float(val) / 3.3058, 1)
        except:
            return 0
            
    final_df['평수'] = final_df.apply(calculate_area, axis=1)
    
    # Fill NA
    final_df['관리지사'] = final_df['관리지사'].fillna('미지정')
    final_df['SP담당'] = final_df['SP담당'].fillna('미지정')
    
    return final_df, None

