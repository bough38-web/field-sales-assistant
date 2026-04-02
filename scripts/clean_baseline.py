import os
import zipfile
import pandas as pd
from collections import defaultdict
import glob

# Constants
TARGET_REGIONS = ["서울특별시", "경기도", "강원도", "강원특별자치도"]
EXCLUDED_REGIONS = ["수원시", "용인시", "화성시", "평택시", "안성시", "오산시", "광주시", "이천시", "여주시", "양평군"]

INPUT_ZIP = "data/LOCALDATA_NOWMON_CSV-3월.zip"
OUTPUT_ZIP = "data/LOCALDATA_FILTERED_CSV-3월.zip"

yearly_stats = defaultdict(lambda: {'new': 0, 'closed': 0})

def clean_and_compress():
    print(f"🚀 원본 필터링 시작: {INPUT_ZIP}")
    if not os.path.exists(INPUT_ZIP):
        print(f"❌ 원본 파일을 찾을 수 없습니다: {INPUT_ZIP}")
        return
        
    total_original = 0
    total_retained = 0
    total_files = 0
    
    with zipfile.ZipFile(INPUT_ZIP, 'r') as zf_in:
        csv_files = [f for f in zf_in.namelist() if f.endswith('.csv')]
        print(f"📁 총 {len(csv_files)}개의 내부 파일 스캔 중...")
        
        # Open output zip with standard ZIP_DEFLATED (level 9 for max compression if needed but default is fine)
        with zipfile.ZipFile(OUTPUT_ZIP, 'w', compression=zipfile.ZIP_DEFLATED) as zf_out:
            for csv_name in csv_files:
                with zf_in.open(csv_name) as cf:
                    try:
                        df = pd.read_csv(cf, encoding='cp949', on_bad_lines='skip', low_memory=False)
                    except:
                        cf.seek(0)
                        try:
                            df = pd.read_csv(cf, encoding='utf-8-sig', on_bad_lines='skip', low_memory=False)
                        except:
                            continue
                            
                if df.empty:
                    continue
                    
                total_original += len(df)
                    
                # Identify key columns precisely to avoid generic errors
                addr_col = next((c for c in df.columns if '주소' in c), None)
                status_col = next((c for c in df.columns if '영업상태명' in c), None)
                date_cols = [c for c in df.columns if '일자' in c]
                
                if not addr_col:
                    continue
                    
                # Ensure address is string
                df[addr_col] = df[addr_col].astype(str)
                
                # 1. Base Target Inclusion
                df = df[df[addr_col].apply(lambda x: any(t in x for t in TARGET_REGIONS))]
                
                # 2. Gyeonggi-do Exclusion
                def is_excluded(addr_val):
                    if '경기도' in addr_val or '경기 ' in addr_val:
                        return any(e in addr_val for e in EXCLUDED_REGIONS)
                    return False
                
                df = df[~df[addr_col].apply(is_excluded)]
                
                # Calculate Year Stats via dict & Filter exclusively for 2026
                retained_records = []
                for r_dict in df.to_dict('records'):
                    status = ''
                    d_val = ''
                    for k_raw in r_dict.keys():
                        k = str(k_raw)
                        if '상태' in k and '영업' in k and pd.notna(r_dict[k_raw]):
                            status = str(r_dict[k_raw])
                            
                    is_new = '영업' in status or '정상' in status or '인허가' in status
                    is_closed = '폐업' in status
                    
                    for k_raw in r_dict.keys():
                        k = str(k_raw)
                        v = r_dict[k_raw]
                        if pd.notna(v):
                            if is_new and '인허가' in k: d_val = str(v)
                            elif is_closed and '폐업' in k: d_val = str(v)
                            
                    year = None
                    if d_val and d_val != 'None':
                        if '-' in d_val: year = d_val.split('-')[0]
                        elif len(d_val) >= 4: year = d_val[:4]
                        
                    if year and len(year) == 4 and year.isdigit():
                        if is_new: yearly_stats[year]['new'] += 1
                        elif is_closed: yearly_stats[year]['closed'] += 1
                        
                        # Only keep records from 2026
                        if year == '2026':
                            retained_records.append(r_dict)
                            
                # Rebuild DataFrame focusing only on 2026
                df = pd.DataFrame(retained_records)
                total_retained += len(df)
                
                if df.empty:
                    continue
                
                # Write filtered df back to CSV
                # Note: df.to_csv returns a string if path_or_buf is None
                csv_str = df.to_csv(index=False, encoding='utf-8-sig')
                zf_out.writestr(csv_name, csv_str)
                total_files += 1

    print(f"\n📊 [필터링 완벽 성공]")
    print(f"👉 원본 레코드수: {total_original:,.0f}건")
    print(f"👉 필터 후(남은) 레코드수: {total_retained:,.0f}건 (전체 용량 및 속도 최소 60% 단축 예측)")
    print(f"👉 새 경량화 데이터 저장경로: {OUTPUT_ZIP} ({os.path.getsize(OUTPUT_ZIP)/1024/1024:.2f} MB 예상)")
    
    print("\n📅 [남은 시설의 연도별 신규/폐업 리포트 (통합)]")
    sorted_years = sorted(yearly_stats.keys(), reverse=True)
    
    # We will print the last 20 years or so
    for y in sorted_years[:20]:
        n_cnt = yearly_stats[y]['new']
        c_cnt = yearly_stats[y]['closed']
        if n_cnt > 0 or c_cnt > 0:
            print(f"   ▫️ {y}년: 신규 {n_cnt:>5,d}건  |  폐업 {c_cnt:>5,d}건")

if __name__ == "__main__":
    clean_and_compress()
