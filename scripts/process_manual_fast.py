import os
import glob
import csv
from datetime import datetime

# Configuration
MANUAL_DIR = "/Users/heebonpark/Downloads/LOCALDATA_YESTERDAY_CSV-0331(수동)"
TARGET_REGIONS = ["서울특별시", "경기도", "강원도", "강원특별자치도"]
EXCLUDED_REGIONS = ["수원시", "용인시", "화성시", "평택시", "안성시", "오산시", "광주시", "이천시", "여주시", "양평군"]
TARGET_DATES = [
    "2026-03-17", "2026-03-18", "2026-03-19", "2026-03-20", 
    "2026-03-21", "2026-03-22", "2026-03-23", "2026-03-24", 
    "2026-03-25", "2026-03-26", "2026-03-27", "2026-03-28",
    "2026-03-29", "2026-03-30", "2026-03-31"
]
DEST_DIR = "/Users/heebonpark/Downloads/field-sales-assistant-main-(배포-자동api)_0331/인허가자료db-API/기타자료/DAILY_CHANGE_RECOVERED"

def ensure_list(v):
    return v if isinstance(v, list) else [v]

def process_manual_fast():
    print(f"🚀 [고속 수동 추출] 시작 - 기준일: {TARGET_DATES}")
    print(f"   타겟 지역: {TARGET_REGIONS}")
    print(f"   제외 지역: {EXCLUDED_REGIONS}")
    print(f"   소스 폴더: {MANUAL_DIR}")
    
    os.makedirs(DEST_DIR, exist_ok=True)
    csv_files = glob.glob(os.path.join(MANUAL_DIR, "*.csv"))
    
    total_new = 0
    total_closed = 0
    files_processed = 0
    files_with_data = 0
    start_time = datetime.now()
    
    for in_file in csv_files:
        files_processed += 1
        out_file = os.path.join(DEST_DIR, os.path.basename(in_file))
        has_matched_rows = False
        
        # We will stream the read and write
        try:
            with open(in_file, 'r', encoding='cp949', errors='replace') as f_in:
                reader = csv.reader(f_in)
                try:
                    header = next(reader)
                except StopIteration:
                    continue  # empty file
                    
                # Find column indices
                addr_idx = None
                status_idx = None
                updt_idx = None
                
                # First find 최종수정시점 or DAT_UPDT_PNT if possible
                if '최종수정시점' in header:
                    updt_idx = header.index('최종수정시점')
                elif 'DAT_UPDT_PNT' in header:
                    updt_idx = header.index('DAT_UPDT_PNT')
                elif '데이터갱신일자' in header:
                    updt_idx = header.index('데이터갱신일자')
                    
                for idx, col_name in enumerate(header):
                    if col_name in ['도로명주소', '도로명전체주소', '지번주소', '소재지전체주소']:
                        addr_idx = idx
                    if col_name in ['영업상태명', '상세영업상태명']:
                        status_idx = idx
                        
                if addr_idx is None:
                    continue  # No address column, skip
                    
                # We need to buffer the rows for this file
                matched_rows = []
                
                for row in reader:
                    if len(row) <= addr_idx: continue
                    
                    # 1. Date Filter (if update column exists)
                    if updt_idx is not None and len(row) > updt_idx:
                        if not any(d in row[updt_idx] for d in TARGET_DATES):
                            continue
                            
                    # 2. Region Filter
                    addr_val = row[addr_idx]
                    if any(reg in addr_val for reg in TARGET_REGIONS):
                        # Gyeonggi-do exclusion logic
                        if '경기도' in addr_val and any(ex_reg in addr_val for ex_reg in EXCLUDED_REGIONS):
                            continue
                            
                        matched_rows.append(row)
                        
                        # 3. Status Count
                        if status_idx is not None and len(row) > status_idx:
                            status_val = row[status_idx]
                            if '영업' in status_val or '정상' in status_val or '인허가' in status_val:
                                total_new += 1
                            elif '폐업' in status_val:
                                total_closed += 1
                                
                if matched_rows:
                    has_matched_rows = True
                    # Write to out file
                    with open(out_file, 'w', encoding='cp949', newline='') as f_out:
                        writer = csv.writer(f_out)
                        writer.writerow(header)
                        writer.writerows(matched_rows)
                    files_with_data += 1
                    
        except Exception as e:
            print(f"⚠️ 읽기 실패: {os.path.basename(in_file)} - {e}")
            
    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\n✨ 추출 완료! 소요 시간: {elapsed:.2f}초")
    print(f"전체 검색 파일: {files_processed}개, 데이터 발견 파일: {files_with_data}개")
    print(f"📊 [결과 요약] 신규: {total_new}건, 폐업: {total_closed}건")
    print(f"📂 추출 파일 위치: {DEST_DIR}")

if __name__ == '__main__':
    process_manual_fast()
