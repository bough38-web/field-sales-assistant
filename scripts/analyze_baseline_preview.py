import glob
import zipfile
import pandas as pd
from collections import defaultdict

TARGET_REGIONS = ["서울특별시", "경기도", "강원도", "강원특별자치도"]
EXCLUDED_REGIONS = ["수원시", "용인시", "화성시", "평택시", "안성시", "오산시", "광주시", "이천시", "여주시", "양평군"]

# We will scan the most relevant ZIPs
zip_files = ['data/LOCALDATA_NOWMON_CSV-3월.zip', 'data/LOCALDATA_2026_ONLY.zip']

print("🔍 원본 데이터 기반 필터링 시뮬레이션 및 연도별 현황 추출 시작...\n")

for zf_name in zip_files:
    print(f"[{zf_name}] 분석 중...")
    
    yearly_stats = defaultdict(lambda: {'new': 0, 'closed': 0})
    total_original = 0
    total_retained = 0
    
    try:
        with zipfile.ZipFile(zf_name, 'r') as zf:
            for csv_name in [x for x in zf.namelist() if x.endswith('.csv')]:
                with zf.open(csv_name) as cf:
                    try:
                        df = pd.read_csv(cf, encoding='cp949', on_bad_lines='skip', low_memory=False)
                    except:
                        cf.seek(0)
                        try:
                            df = pd.read_csv(cf, encoding='utf-8-sig', on_bad_lines='skip', low_memory=False)
                        except:
                            continue
                            
                    # Identify columns
                    addr_col = next((c for c in df.columns if '전체주소' in c or '주소' in c), None)
                    status_col = next((c for c in df.columns if '상태' in c and '영업' in c and '코드' not in c), None)
                    if not status_col: status_col = next((c for c in df.columns if '상태' in c and '영업' in c), None)
                    
                    open_date_col = next((c for c in df.columns if '인허가일자' in c or '시작' in c), None)
                    close_date_col = next((c for c in df.columns if '폐업일자' in c or '종료' in c), None)
                    
                    if not addr_col or not status_col:
                        continue
                        
                    total_original += len(df)
                    
                    # Filtering Engine
                    df[addr_col] = df[addr_col].astype(str)
                    
                    # 1. Target Include (Region Filter)
                    mask_in = df[addr_col].apply(lambda x: any(tr in x for tr in TARGET_REGIONS))
                    df = df[mask_in]
                    
                    # 2. Target Exclude
                    def is_excluded(val):
                        if '경기도' in val or '경기 ' in val:
                            return any(ex in val for ex in EXCLUDED_REGIONS)
                        return False
                        
                    mask_ex = df[addr_col].apply(is_excluded)
                    df = df[~mask_ex]
                    
                    # 3. Apply the NEW data_loader logic
                    df[status_col] = df[status_col].astype(str)
                    
                    # Year Parsing
                    df['parsed_open_year'] = pd.to_numeric(df[open_date_col].fillna('').astype(str).str.replace(r'[^0-9]', '', regex=True).str[:4], errors='coerce').fillna(0).astype(int) if open_date_col else 0
                    df['parsed_close_year'] = pd.to_numeric(df[close_date_col].fillna('').astype(str).str.replace(r'[^0-9]', '', regex=True).str[:4], errors='coerce').fillna(0).astype(int) if close_date_col else 0
                    
                    is_active = df[status_col].str.contains('영업|정상', na=False)
                    is_closed = df[status_col].str.contains('폐업|정지', na=False)
                    
                    is_recent_open = (df['parsed_open_year'] >= 2024)
                    is_recent_close = (df['parsed_close_year'] >= 2024)
                    
                    # The NEW logic
                    is_valid = (is_active & is_recent_open) | (is_closed & (is_recent_open | is_recent_close))
                    df = df[is_valid]
                    
                    total_retained += len(df)
                    
                    # Compute yearly stats for retained data
                    for idx, row in df.iterrows():
                        status = row[status_col]
                        # In the retained set:
                        if '영업' in status or '정상' in status:
                            year = str(row['parsed_open_year']) if row['parsed_open_year'] > 0 else "알림없음"
                            yearly_stats[year]['new'] += 1
                        elif '폐업' in status or '정지' in status:
                            # Use closure year if available, else open year
                            if row['parsed_close_year'] >= 2024:
                                year = str(row['parsed_close_year'])
                            else:
                                year = str(row['parsed_open_year'])
                            yearly_stats[year]['closed'] += 1

        print(f"  👉 원본 규모: {total_original}건 -> 필터 후(남길 규모): {total_retained}건")
        
        # Sort years
        sorted_years = sorted([y for y in yearly_stats.keys() if y != "알림없음"], reverse=True)
        print("  📊 필터링 후 연도별 데이터 현황 (기존 2024+ 필터 완화 적용):")
        for y in sorted_years[:10]:
            print(f"     ✅ {y}년: 신규 {yearly_stats[y]['new']:>6}건  |  폐업 {yearly_stats[y]['closed']:>6}건")


    except Exception as e:
        print(f"파일을 읽는 중 에러 발생: {e}")
        
    print("-" * 50)
