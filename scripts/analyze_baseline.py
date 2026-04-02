import os, glob, zipfile, pandas as pd
from collections import Counter

TARGET_REGIONS = ["서울특별시", "경기도", "강원도", "강원특별자치도"]
EXCLUDED_REGIONS = ["수원시", "용인시", "화성시", "평택시", "안성시", "오산시", "광주시", "이천시", "여주시", "양평군"]
BASE_DIR = 'data'
zips = [f for f in glob.glob(f'{BASE_DIR}/LOCALDATA*.zip')]

print("Scanning ZIP files to analyze Year distribution after filtering...")
for zip_path in zips:
    year_counter = Counter()
    total_retained = 0
    total_original = 0
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            csv_files = [m for m in zf.namelist() if m.endswith('.csv')]
            for csv_f in csv_files:
                with zf.open(csv_f) as cf:
                    try:
                        df = pd.read_csv(cf, encoding='cp949', on_bad_lines='skip', low_memory=False)
                    except:
                        try:
                            cf.seek(0)
                            df = pd.read_csv(cf, encoding='utf-8-sig', on_bad_lines='skip', low_memory=False)
                        except:
                            continue
                    
                    addr_cols = [c for c in df.columns if '주소' in c]
                    date_cols = [c for c in df.columns if '인허가일자' in c or '데이터갱신일자' in c]
                    
                    if not addr_cols: continue
                    a_col = addr_cols[0]
                    d_col = date_cols[0] if date_cols else None
                    
                    total_original += len(df)
                    
                    df_filtered = df.copy()
                    df_filtered[a_col] = df_filtered[a_col].astype(str)
                    
                    # Target Region match
                    mask_target = df_filtered[a_col].apply(lambda x: any(tr in x for tr in TARGET_REGIONS))
                    df_filtered = df_filtered[mask_target]
                    
                    # Exclusion match
                    def is_excluded(x):
                        return ('경기도' in x or '경기 ' in x) and any(ex in x for ex in EXCLUDED_REGIONS)
                    
                    mask_excl = df_filtered[a_col].apply(is_excluded)
                    df_filtered = df_filtered[~mask_excl]
                    
                    total_retained += len(df_filtered)
                    
                    if d_col:
                        dates = df_filtered[d_col].dropna().astype(str)
                        for d in dates:
                            # Extract year
                            parts = d.split('-')
                            if len(parts) >= 1 and len(parts[0]) == 4 and parts[0].isdigit():
                                year_counter[parts[0]] += 1
                            else:
                                if len(d) >= 4 and d[:4].isdigit():
                                    year_counter[d[:4]] += 1
    except Exception as e:
        print(f"Error reading {zip_path}: {e}")
        continue
        
    print(f"\n--- {os.path.basename(zip_path)} ---")
    print(f"Original records: {total_original} -> Retained records: {total_retained}")
    if total_retained > 0:
        print("Yearly distribution (Top 10):")
        for y, c in year_counter.most_common(10):
            print(f"  {y}년: {c}건")
