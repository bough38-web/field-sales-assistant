
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
import hashlib
from typing import Optional, Tuple, List, Dict, Any, Union
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Import from local utils
from src.utils import normalize_address, parse_coordinates_row, get_best_match, calculate_area, transformer, HAS_PYPROJ

def normalize_str(s: Any) -> Optional[str]:
    if pd.isna(s): return s
    # [STRICT] Enforce NFC and '지사' suffix at the lowest level
    b_norm = unicodedata.normalize('NFC', str(s)).strip()
    known_branches = ['중앙', '강북', '서대문', '고양', '의정부', '남양주', '강릉', '원주']
    if b_norm in known_branches:
        return b_norm + '지사'
    return b_norm

def _process_and_merge_district_data(target_df: pd.DataFrame, district_file_path_or_obj: Any) -> Tuple[pd.DataFrame, List[Dict], Optional[str]]:
    """
    Common logic to process district file, match addresses, and merge with target_df.
    """
    # 1. Load District File
    try:
        if isinstance(district_file_path_or_obj, str) and district_file_path_or_obj.startswith("http"):
            import requests
            import io
            response = requests.get(district_file_path_or_obj, timeout=15)
            response.raise_for_status()
            df_district = pd.read_excel(io.BytesIO(response.content))
        else:
            df_district = pd.read_excel(district_file_path_or_obj)
    except Exception as e:
        return target_df, [], f"Error reading District file: {e}"

    # 2. Normalize District Data
    if '주소시' in df_district.columns:
        df_district['full_address'] = df_district[['주소시', '주소군구', '주소동']].astype(str).agg(' '.join, axis=1)
    else:
        addr_col = next((c for c in df_district.columns if any(p in c for p in ['설치주소', '도로명주소', '소재지주소', '주소'])), None)
        if addr_col:
            df_district['full_address'] = df_district[addr_col]
        else:
            return target_df, [], "District file must contain an address column."

    branch_col = next((c for c in df_district.columns if any(p in c for p in ['관리지사', '지사'])), None)
    if branch_col:
        df_district['관리지사'] = df_district[branch_col].apply(normalize_str)
    else:
        df_district['관리지사'] = '미지정'

    mgr_col = next((c for c in df_district.columns if any(p in c for p in ['SP담당', '구역담당영업사원', '담당'])), None)
    if mgr_col:
        df_district['SP담당'] = df_district[mgr_col].apply(normalize_str)
    else:
        df_district['SP담당'] = '미지정'

    df_district['full_address'] = df_district['full_address'].apply(normalize_str)
    df_district['full_address_norm'] = df_district['full_address'].apply(normalize_address)
    df_district = df_district.dropna(subset=['full_address_norm'])
    df_district = df_district.drop_duplicates(subset=['full_address_norm'], keep='first')
    
    # 3. Prepare Target Data
    target_df['소재지전체주소_norm'] = target_df['소재지전체주소'].astype(str).apply(normalize_address)
    target_df = target_df.dropna(subset=['소재지전체주소_norm'])

    if df_district.empty or target_df.empty:
        return target_df, [], "District or Target data is empty after normalization."

    # 4. Batch Matching Logic
    vectorizer = TfidfVectorizer(analyzer='char', ngram_range=(2, 3)).fit(df_district['full_address_norm'])
    district_matrix = vectorizer.transform(df_district['full_address_norm'])
    target_addrs = target_df['소재지전체주소_norm'].tolist()
    target_matrix = vectorizer.transform(target_addrs)
    cosine_sim = cosine_similarity(target_matrix, district_matrix)
    
    results = []
    for i in range(len(target_df)):
        best_match_idx = cosine_sim[i].argmax()
        best_score = cosine_sim[i][best_match_idx]
        
        # [Hierarchical Region Guard]
        matched_branch = df_district.iloc[best_match_idx]['관리지사']
        row_addr = str(target_df.iloc[i].get('소재지전체주소', '')).lower()
        
        is_region_mismatch = False
        if '부산' in matched_branch and '부산' not in row_addr:
            is_region_mismatch = True
        elif '서울' in matched_branch and '서울' not in row_addr:
            is_region_mismatch = True
             
        if best_score >= 0.7 and not is_region_mismatch:
            results.append({
                '관리지사': matched_branch,
                'SP담당': df_district.iloc[best_match_idx]['SP담당']
            })
        else:
            results.append({'관리지사': '미지정', 'SP담당': '미지정'})
             
    results_df = pd.DataFrame(results, index=target_df.index)
    target_df = pd.concat([target_df, results_df], axis=1)
    
    # Manager stats
    mgr_info = []
    for branch in target_df['관리지사'].unique():
        if branch == '미지정': continue
        branch_df = target_df[target_df['관리지사'] == branch]
        for mgr in branch_df['SP담당'].unique():
            if mgr == '미지정': continue
            mgr_info.append({'branch': branch, 'name': mgr, 'count': len(branch_df[branch_df['SP담당'] == mgr])})
            
    return target_df, mgr_info, None

@st.cache_data(show_spinner=False)
def load_and_process_data(zip_file_path: str, district_file_path_or_obj: Any, salt: str = ""):
    """
    Main function to load LocalData (ZIP of CSVs) and merge with District file.
    Includes robust encoding, headerless support, and coordinate normalization.
    """
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
                        
                    # [FIX] Truncate extremely long filenames (Errno 36)
                    base_name, ext = os.path.splitext(filename)
                    if len(base_name) > 60:
                        h = hashlib.md5(base_name.encode()).hexdigest()[:8]
                        base_name = base_name[:50] + "_" + h
                    
                    target_name = base_name + ext
                    target_path = os.path.join(temp_dir, target_name)
                    
                    with zip_ref.open(member) as source, open(target_path, "wb") as target:
                        shutil.copyfileobj(source, target)
                        
    except Exception as e:
        return None, [], f"Error extracting ZIP: {e}", {}

    all_files = glob.glob(os.path.join(temp_dir, "**/*.csv"), recursive=True)
    dfs = []
    
    def generate_vectorized_record_key(df_in):
        """Vectorized version of utils.generate_record_key"""
        if df_in is None or df_in.empty: return df_in
        t_ser = df_in.get('사업장명', pd.Series(['']*len(df_in), index=df_in.index)).fillna('').astype(str)
        a_ser = (df_in.get('소재지전체주소', pd.Series(['']*len(df_in), index=df_in.index)).fillna('')
                 .combine_first(df_in.get('도로명전체주소', pd.Series(['']*len(df_in), index=df_in.index)).fillna(''))
                 .combine_first(df_in.get('주소', pd.Series(['']*len(df_in), index=df_in.index)).fillna(''))
                 .astype(str))
        
        replacements = {
            "서울특별시": "서울", "서울시": "서울", "경기도": "경기", "기도": "경기",
            "인천특별광역시": "인천", "인천광역시": "인천", "인천시": "인천",
            "부산광역시": "부산", "부산시": "부산", "대구광역시": "대구", "대구시": "대구",
            "광주광역시": "광주", "광주시": "광주", "대전광역시": "대전", "대전시": "대전",
            "울산광역시": "울산", "울산시": "울산", "세종특별자치시": "세종", "세종시": "세종",
            "제주특별자치도": "제주", "제주도": "제주", "제주시": "제주",
            "강원특별자치도": "강원", "강원도": "강원", "전북특별자치도": "전북", "전라북도": "전북",
            "충청북도": "충북", "충북도": "충북", "충청남도": "충남", "충남도": "충남",
            "전라남도": "전남", "전남도": "전남", "경상북도": "경북", "경북도": "경북",
            "경상남도": "경남", "경남도": "경남"
        }
        
        def v_clean(ser):
            res = ser.copy()
            for k, v in replacements.items():
                res = res.str.replace(k, v, regex=False)
            res = res.str.replace('"', '', regex=False).str.replace("'", "", regex=False).str.replace('\n', '', regex=False)
            res = res.str.replace(r'\s+', ' ', regex=True).str.strip()
            return res

        df_in['record_key'] = v_clean(t_ser) + "_" + v_clean(a_ser)
        return df_in

    for file in all_files:
        try:
            encodings_to_try = ['utf-8-sig', 'cp949']
            df = None
            for enc in encodings_to_try:
                try:
                    df_check = pd.read_csv(file, encoding=enc, on_bad_lines='skip', dtype=str, nrows=5)
                    if any('주소' in str(c) for c in df_check.columns):
                        df = pd.read_csv(file, encoding=enc, on_bad_lines='skip', dtype=str, low_memory=False)
                        break
                    elif len(df_check.columns) >= 20: 
                         first_val = str(df_check.columns[0])
                         if first_val.isdigit() or first_val.startswith('20'):
                             df = pd.read_csv(file, encoding=enc, on_bad_lines='skip', dtype=str, low_memory=False, header=None)
                             num_cols = len(df.columns)
                             x_idx, y_idx = None, None
                             for col_idx in range(min(num_cols, 30)):
                                 sample_vals = pd.to_numeric(df.iloc[:20, col_idx], errors='coerce').dropna()
                                 if not sample_vals.empty:
                                     med = sample_vals.median()
                                     if 150000 < med < 350000: x_idx = col_idx
                                     if 400000 < med < 650000: y_idx = col_idx
                                     if 124 < med < 132: x_idx = col_idx 
                                     if 33 < med < 43: y_idx = col_idx   
                             h_map = {}
                             if x_idx is not None: h_map[x_idx] = '좌표정보(X)'
                             if y_idx is not None: h_map[y_idx] = '좌표정보(Y)'
                             for a_idx in [15, 16, 17, 18, 14]:
                                 if a_idx < num_cols:
                                     sample_a = str(df.iloc[0, a_idx])
                                     if '시' in sample_a or '도' in sample_a:
                                         h_map[a_idx] = '소재지전체주소'
                                         break
                             if h_map: df.rename(columns=h_map, inplace=True)
                             break
                except Exception: continue
            
            if df is None or df.empty: continue
            
            df_filtered = df.copy()
            if '인허가일자' in df.columns:
                status_cols = [c for c in df.columns if '상태명' in c]
                if status_cols:
                    status_col = status_cols[0]
                    raw_dates = df['인허가일자'].fillna('').astype(str).str.replace(r'[^0-9]', '', regex=True)
                    df['parsed_temp_year'] = pd.to_numeric(raw_dates.str[:4], errors='coerce').fillna(0).astype(int)
                    is_active = df[status_col].str.contains('영업|정상', na=False)
                    is_valid_date = df['parsed_temp_year'] >= 2026
                    
                    if '폐업일자' in df.columns:
                        raw_close_dates = df['폐업일자'].fillna('').astype(str).str.replace(r'[^0-9]', '', regex=True)
                        close_years = pd.to_numeric(raw_close_dates.str[:4], errors='coerce').fillna(0).astype(int)
                        is_valid_close_date = close_years >= 2026
                    else: is_valid_close_date = False
                    
                    mask_active = is_active & is_valid_date
                    mask_closed = ~is_active & is_valid_close_date
                    df_filtered = df[mask_active | mask_closed].copy()
                    if 'parsed_temp_year' in df_filtered.columns: df_filtered.drop(columns=['parsed_temp_year'], inplace=True)
                else:
                    raw_dates = df['인허가일자'].fillna('').astype(str).str.replace(r'[^0-9]', '', regex=True)
                    temp_years = pd.to_numeric(raw_dates.str[:4], errors='coerce').fillna(0).astype(int)
                    df_filtered = df[temp_years >= 2026].copy()

            if not df_filtered.empty:
                # Per-file Coordinate Detection
                all_f_cols = df_filtered.columns
                x_c = next((c for c in all_f_cols if '좌표' in c and ('x' in c.lower() or 'X' in c)), None)
                y_c = next((c for c in all_f_cols if '좌표' in c and ('y' in c.lower() or 'Y' in c)), None)
                rename_f = {}
                if x_c: rename_f[x_c] = '좌표정보(X)'
                if y_c: rename_f[y_c] = '좌표정보(Y)'
                addr_c = next((c for c in all_f_cols if c in ['소재지전체주소', '도로명전체주소', '주소']), None)
                if addr_c: rename_f[addr_c] = '소재지전체주소'
                if rename_f: df_filtered.rename(columns=rename_f, inplace=True)

                df_filtered = generate_vectorized_record_key(df_filtered)
                if '인허가일자' in df_filtered.columns:
                    df_filtered['인허가일자_dt'] = pd.to_datetime(df_filtered['인허가일자'], errors='coerce')
                    df_filtered.sort_values(by='인허가일자_dt', ascending=False, inplace=True)
                    df_filtered.drop(columns=['인허가일자_dt'], inplace=True)
                
                df_filtered.drop_duplicates(subset=['record_key'], keep='first', inplace=True)
                dfs.append(df_filtered)
        except Exception: continue
            
    if not dfs: return None, [], "No valid CSV files found.", {}
        
    concatenated_df = pd.concat(dfs, ignore_index=True)
    count_before = len(concatenated_df)
    
    if '인허가일자' in concatenated_df.columns:
        concatenated_df['인허가일자_dt'] = pd.to_datetime(concatenated_df['인허가일자'], errors='coerce')
        concatenated_df.sort_values(by='인허가일자_dt', ascending=False, inplace=True, na_position='last')
        concatenated_df.drop(columns=['인허가일자_dt'], inplace=True)

    concatenated_df.drop_duplicates(subset=['record_key'], keep='first', inplace=True)
    count_after = len(concatenated_df)
    stats = {'before': count_before, 'after': count_after}

    all_cols = concatenated_df.columns
    desired_patterns = ['소재지전체주소', '지번주소', '사업장명', '업태구분명', '영업상태명', 
                        '소재지전화', '소재지전화번호', '총면적', '소재지면적', '인허가일자', '폐업일자', 
                        '재개업일자', '최종수정시점', '데이터기준일자']
    
    rename_map = {}
    selected_cols = []
    
    if '좌표정보(X)' in all_cols: selected_cols.append('좌표정보(X)')
    if '좌표정보(Y)' in all_cols: selected_cols.append('좌표정보(Y)')
    
    for cand in ['도로명전체주소', '도로명주소', '소재지도로명주소']:
        if cand in all_cols:
            selected_cols.append(cand)
            rename_map[cand] = '도로명전체주소'
            break
            
    for pat in desired_patterns:
        match = pat if pat in all_cols else next((c for c in all_cols if pat in c), None)
        if match:
            if match not in selected_cols: selected_cols.append(match)
            rename_map[match] = pat
            
    selected_cols.append('record_key')
    target_df = concatenated_df[list(set(selected_cols))].copy()
    target_df.rename(columns=rename_map, inplace=True)
    
    if '소재지전체주소' not in target_df.columns:
        if '지번주소' in target_df.columns: target_df.rename(columns={'지번주소': '소재지전체주소'}, inplace=True)
        elif '도로명전체주소' in target_df.columns: target_df['소재지전체주소'] = target_df['도로명전체주소']
    
    if '소재지전화' not in target_df.columns and '소재지전화번호' in target_df.columns:
        target_df.rename(columns={'소재지전화번호': '소재지전화'}, inplace=True)

    if '영업상태명' in target_df.columns:
        target_df['영업상태명'] = target_df['영업상태명'].fillna('').astype(str).str.strip()
        target_df['영업상태명'] = target_df['영업상태명'].apply(lambda x: unicodedata.normalize('NFC', x))
        active_p = [unicodedata.normalize('NFC', p) for p in ['영업/정상', '정상영업', '개업', '영업', '정상', '01']]
        closed_p = [unicodedata.normalize('NFC', p) for p in ['폐업', '폐업처리', '03']]
        target_df.loc[target_df['영업상태명'].isin(active_p), '영업상태명'] = '영업/정상'
        target_df.loc[target_df['영업상태명'].isin(closed_p), '영업상태명'] = '폐업'

    date_cols = ['인허가일자', '폐업일자', '재개업일자']
    for col in date_cols:
        if col in target_df.columns: target_df[col] = pd.to_datetime(target_df[col], errors='coerce')
            
    avail_dates = [c for c in date_cols if c in target_df.columns]
    if avail_dates: target_df['최종수정시점'] = target_df[avail_dates].max(axis=1)
    
    if '인허가일자' in target_df.columns: target_df.sort_values(by='인허가일자', ascending=False, inplace=True)
        
    if '좌표정보(X)' in target_df.columns and '좌표정보(Y)' in target_df.columns:
        xs = pd.to_numeric(target_df['좌표정보(X)'], errors='coerce').values
        ys = pd.to_numeric(target_df['좌표정보(Y)'], errors='coerce').values
        lats, lons = np.full(xs.shape, np.nan), np.full(xs.shape, np.nan)
        valid = ~np.isnan(xs) & ~np.isnan(ys)
        if np.any(valid):
             if np.median(xs[valid]) > 200 and HAS_PYPROJ:
                 try:
                     lon_v, lat_v = transformer.transform(xs[valid], ys[valid])
                     lats[valid], lons[valid] = lat_v, lon_v
                 except Exception: pass
             else:
                 lats[valid], lons[valid] = ys[valid], xs[valid]
        
        bad = (lats < 30) | (lats > 45) | (lons < 120) | (lons > 140)
        lats[bad], lons[bad] = np.nan, np.nan
        target_df['lat'], target_df['lon'] = lats, lons
    else:
        target_df['lat'], target_df['lon'] = None, None
        
    final_df, mgr_info, err = _process_and_merge_district_data(target_df, district_file_path_or_obj)
    return final_df, mgr_info, err, stats

def fetch_openapi_data(auth_key: str, local_code: str, start_date: str, end_date: str) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """Fetches data from localdata.go.kr API."""
    base_url = "http://www.localdata.go.kr/platform/rest/TO0/openDataApi"
    params = {"authKey": auth_key, "localCode": local_code, "bgnYmd": start_date, "endYmd": end_date, "resultType": "xml", "numOfRows": 1000, "pageNo": 1}
    all_rows = []
    try:
        response = requests.get(base_url, params=params, timeout=20)
        if response.status_code != 200: return None, f"API Error: {response.status_code}"
        root = ET.fromstring(response.content)
        header = root.find("header")
        if header is not None:
             code = header.find("resultCode")
             msg = header.find("resultMsg")
             if code is not None and code.text != '00': return None, f"API Logic Error: {msg.text if msg is not None else 'Unknown'}"
        body = root.find("body")
        items = body.find("items") if body is not None else root.findall("row")
        if items is None: items = []

        def get_val(item, tags):
            for tag in tags:
                node = item.find(tag)
                if node is not None and node.text: return node.text
            return None

        for item in items:
            row_data = {}
            row_data['개방자치단체코드'] = get_val(item, ["opnSfTeamCode", "OPN_SF_TEAM_CODE"])
            row_data['관리번호'] = get_val(item, ["mgtNo", "MGT_NO"])
            row_data['사업장명'] = get_val(item, ["bplcNm", "BPLC_NM"])
            row_data['소재지전체주소'] = get_val(item, ["siteWhlAddr", "SITE_WHL_ADDR"])
            row_data['도로명전체주소'] = get_val(item, ["rdnWhlAddr", "RDN_WHL_ADDR"])
            row_data['소재지전화'] = get_val(item, ["siteTel", "SITE_TEL"])
            row_data['인허가일자'] = get_val(item, ["apvPermYmd", "APV_PERM_YMD"])
            row_data['폐업일자'] = get_val(item, ["dcbYmd", "DCB_YMD"])
            row_data['영업상태명'] = get_val(item, ["trdStateNm", "TRD_STATE_NM"])
            row_data['업태구분명'] = get_val(item, ["uptaeNm", "UPTAE_NM"])
            row_data['좌표정보(X)'] = get_val(item, ["x", "X"])
            row_data['좌표정보(Y)'] = get_val(item, ["y", "Y"])
            all_rows.append(row_data)
    except Exception as e: return None, f"Fetch Error: {e}"
    if not all_rows: return None, "Parsed 0 rows."
    return pd.DataFrame(all_rows), None

@st.cache_data
def process_api_data(target_df: pd.DataFrame, district_file_path_or_obj: Any) -> Tuple[Union[pd.DataFrame, None], List[Dict], Optional[str], Dict[str, int]]:
    """Processes API data and merges with district."""
    if target_df is None or target_df.empty: return None, [], "API DataFrame is empty.", {}
    x_col, y_col = '좌표정보(X)', '좌표정보(Y)'
    if x_col in target_df.columns and y_col in target_df.columns:
         target_df['lat'], target_df['lon'] = zip(*target_df.apply(lambda row: parse_coordinates_row(row, x_col, y_col), axis=1))
    else: target_df['lat'], target_df['lon'] = None, None
    for col in ['인허가일자', '폐업일자', '재개업일자']:
        if col in target_df.columns: target_df[col] = pd.to_datetime(target_df[col], format='%Y%m%d', errors='coerce')
    if 'record_key' not in target_df.columns:
        from . import utils
        target_df['record_key'] = target_df.apply(lambda row: utils.generate_record_key(row.get('사업장명', ''), row.get('소재지전체주소', '')), axis=1)
    final_df, mgr_info, err = _process_and_merge_district_data(target_df, district_file_path_or_obj)
    stats = {'before': len(target_df), 'after': len(final_df)}
    return final_df, mgr_info, err, stats

def merge_activity_status(df: pd.DataFrame) -> pd.DataFrame:
    """Merges persistent activity status from JSON."""
    from src.activity_logger import ACTIVITY_STATUS_FILE, load_json_file
    if df is None or df.empty: return df
    statuses = load_json_file(ACTIVITY_STATUS_FILE)
    if not statuses: return df
    rows = []
    for k, v in statuses.items():
        if not isinstance(v, dict): continue
        row = {"record_key": k}
        row.update(v)
        rows.append(row)
    status_df = pd.DataFrame(rows)
    if status_df.empty: return df
    if 'record_key' not in df.columns: return df
    cols_to_overwrite = ['활동진행상태', '특이사항', '변경일시', '변경자', 'photo_path1', 'photo_path2', 'photo_path3']
    df = df.drop(columns=[c for c in cols_to_overwrite if c in df.columns])
    merge_cols = ['record_key'] + [c for c in cols_to_overwrite if c in status_df.columns]
    return pd.merge(df, status_df[merge_cols], on='record_key', how='left')
