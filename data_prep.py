
import pandas as pd
import os
import zipfile
import unicodedata
import numpy as np
from typing import Optional, Tuple, Any
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re

# Reuse normalization logic or define here for standalone
def normalize_address(addr: str) -> str:
    if not isinstance(addr, str): return ""
    # Remove common patterns
    addr = re.sub(r'\([^)]*\)', '', addr)
    addr = re.sub(r'\[[^]]*\]', '', addr)
    addr = re.sub(r'\s+', ' ', addr).strip()
    return unicodedata.normalize('NFC', addr)

def normalize_str(s: Any) -> str:
    if pd.isna(s): return ""
    return unicodedata.normalize('NFC', str(s)).strip()

def run_pre_calculation():
    zip_path = 'data/LOCALDATA_APRIL_TOTAL_CONSOLIDATED.zip'
    dist_path = 'data/영업구역별_주소현행화_최종_20260304.xlsx'
    output_path = 'data/processed_results.parquet'

    if not os.path.exists(zip_path):
        print(f"Error: {zip_path} not found.")
        return
    if not os.path.exists(dist_path):
        print(f"Error: {dist_path} not found.")
        return

    print("🚀 Loading District Data...")
    df_district = pd.read_excel(dist_path)
    # Standardize columns
    df_district.columns = [unicodedata.normalize('NFC', str(c)).strip() for c in df_district.columns]
    
    # Setup full_address
    addr_parts = [c for c in ['주소시', '주소군구', '주소동'] if c in df_district.columns]
    if addr_parts:
        df_district['full_address'] = df_district[addr_parts].astype(str).agg(' '.join, axis=1)
    else:
        addr_col = next((c for c in df_district.columns if any(p in c for p in ['설치주소', '도로명주소', '소재지주소', '주소'])), None)
        df_district['full_address'] = df_district[addr_col] if addr_col else ""

    df_district['full_address_norm'] = df_district['full_address'].apply(normalize_address)
    df_district = df_district.dropna(subset=['full_address_norm']).drop_duplicates(subset=['full_address_norm'])

    print("🚀 Loading ZIP Data...")
    all_dfs = []
    with zipfile.ZipFile(zip_path, 'r') as z:
        for f in z.namelist():
            if f.endswith('.csv'):
                try:
                    # Try cp949 first (common for localdata)
                    tmp = pd.read_csv(z.open(f), encoding='cp949', low_memory=False)
                    all_dfs.append(tmp)
                except:
                    try:
                        tmp = pd.read_csv(z.open(f), encoding='utf-8', low_memory=False)
                        all_dfs.append(tmp)
                    except: pass
    
    if not all_dfs:
        print("Error: No CSVs found in zip.")
        return
    
    target_df = pd.concat(all_dfs, ignore_index=True)
    print(f"✅ Total Rows to Match: {len(target_df):,}")

    # Standardize column for address
    target_addr_col = next((c for c in target_df.columns if '소재지전체주소' in c or '도로명전체주소' in c), None)
    if not target_addr_col:
        print("Error: No address column found in CSVs.")
        return
    
    target_df['소재지전체주소'] = target_df[target_addr_col].fillna('')
    target_df['address_norm'] = target_df['소재지전체주소'].apply(normalize_address)
    
    unique_targets = [a for a in target_df['address_norm'].unique() if a.strip()]
    print(f"⚡ Unique Addresses to Match: {len(unique_targets):,}")

    # 4. TF-IDF Matching
    vectorizer = TfidfVectorizer(analyzer='char', ngram_range=(2, 3)).fit(df_district['full_address_norm'])
    dist_matrix = vectorizer.transform(df_district['full_address_norm'])
    target_matrix = vectorizer.transform(unique_targets)
    
    print("⚡ Calculating Similarity Matrix...")
    cosine_sim = cosine_similarity(target_matrix, dist_matrix)
    
    match_map = {}
    for i, addr in enumerate(unique_targets):
        best_idx = cosine_sim[i].argmax()
        score = cosine_sim[i][best_idx]
        if score >= 0.7:
            match_map[addr] = {
                '관리지사': df_district.iloc[best_idx]['관리지사'],
                'SP담당': df_district.iloc[best_idx]['SP담당'],
                '영업구역 수정': df_district.iloc[best_idx].get('영업구역 수정', '')
            }
        else:
            match_map[addr] = {'관리지사': '미지정', 'SP담당': '미지정', '영업구역 수정': ''}

    # 5. Map results back to the entire target_df using vectorized mapping
    target_df['관리지사'] = target_df['address_norm'].map(lambda x: match_map.get(x, {}).get('관리지사', '미지정'))
    target_df['SP담당'] = target_df['address_norm'].map(lambda x: match_map.get(x, {}).get('SP담당', '미지정'))
    target_df['영업구역 수정'] = target_df['address_norm'].map(lambda x: match_map.get(x, {}).get('영업구역 수정', ''))

    # [OPTIMIZATION] Keep only essential columns to save memory and disk space
    essential_cols = [
        '사업장명', '관리지사', 'SP담당', '영업구역 수정', '소재지전체주소', '도로명전체주소', 
        'lat', 'lon', '인허가일자', '영업상태명', '상세영업상태명', '업태구분명', '개방서비스명'
    ]
    # Check which ones exist
    keep_cols = [c for c in essential_cols if c in target_df.columns]
    target_df = target_df[keep_cols].copy()

    # Force all kept columns to string before saving to avoid pyarrow type inference errors
    for col in target_df.columns:
        if col not in ['lat', 'lon']: # Keep coordinates as numbers if possible, but for Parquet string is safer if mixed
            target_df[col] = target_df[col].astype(str)

    print(f"💾 Saving results to {output_path}...")
    target_df.to_parquet(output_path, index=False)
    print("✨ Pre-calculation Complete!")

if __name__ == "__main__":
    run_pre_calculation()
