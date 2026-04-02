import os
import pandas as pd
import glob
from tqdm import tqdm
import unicodedata

# Constants
DIR_PREV = "data/BACKUP_ALLMASTER_20260331/LOCALDATA_ALL_CSV-(2월말까지)"
DIR_NOW = "data/BACKUP_ALLMASTER_20260331/LOCALDATA_NOWMON_CSV(3월27일까지)"
OUTPUT_FILE = "data/MASTER_2026_MERGED_FINAL.csv"

# Target Regions
TARGET_REGIONS = ["서울특별시", "서울 ", "경기도", "경기 ", "강원도", "강원특별자치도", "충청북도", "인천"]

# Specific Filter Rules
EXCLUDED_GYEONGGI = ["수원시", "용인시", "화성시", "평택시", "안성시", "오산시", "광주시", "이천시", "여주시", "양평군"]
INCLUDED_INCHEON = ["부평구", "계양구"]
INCLUDED_CHUNGBUK = ["제천시"]
EXCLUDED_SEOUL = ["강남구", "송파구", "서초구"]

def normalize_nfc(s):
    if pd.isna(s): return ""
    return unicodedata.normalize('NFC', str(s))

def is_target_record(addr):
    if not addr or pd.isna(addr): return False
    addr = normalize_nfc(addr)
    
    # Seoul: Specific district filtering
    if any(t in addr for t in ["서울특별시", "서울 "]):
        if any(e in addr for e in EXCLUDED_SEOUL):
            return False
        return True
    
    # Gangwon: All
    if any(t in addr for t in ["강원도", "강원특별자치도"]):
        return True
    
    # Incheon: Bupyeong, Gyeyang only
    if "인천" in addr:
        return any(t in addr for t in INCLUDED_INCHEON)
    
    # Chungbuk: Jecheon only
    if "충청북도" in addr or "충북 " in addr:
        return any(t in addr for t in INCLUDED_CHUNGBUK)
    
    # Gyeonggi: Exclude specific cities, but include Gimpo/Bucheon (already handled by exclusions)
    if "경기도" in addr or "경기 " in addr:
        if any(e in addr for e in EXCLUDED_GYEONGGI):
            return False
        return True
    
    return False

def process_directories():
    all_csv_files = glob.glob(os.path.join(DIR_PREV, "*.csv")) + glob.glob(os.path.join(DIR_NOW, "*.csv"))
    print(f"🚀 총 {len(all_csv_files)}개의 CSV 파일 처리 시작...")
    
    total_retained_df = []
    processed_files_count = 0
    
    for file_path in tqdm(all_csv_files):
        try:
            # Read first line for headers
            df = pd.read_csv(file_path, encoding='cp949', on_bad_lines='skip', low_memory=False, dtype=str)
            
            if df.empty: continue
            
            # Identify columns
            addr_col = next((c for c in df.columns if '소재지전체주소' in c or '주소' in c), None)
            date_col = next((c for c in df.columns if '최종수정시점' in c), None)
            name_col = next((c for c in df.columns if '사업장명' in c), None)
            
            if not addr_col or not date_col:
                continue
            
            # 1. Year Filter (2026)
            mask_year = df[date_col].fillna('').str.contains('2026')
            df = df[mask_year]
            
            if df.empty: continue
            
            # 2. Regional Filter
            mask_region = df[addr_col].apply(is_target_record)
            df = df[mask_region]
            
            if not df.empty:
                # Add a record key for deduplication later
                if name_col:
                    df['record_key'] = df[name_col].fillna('') + "_" + df[addr_col].fillna('')
                else:
                    df['record_key'] = df[addr_col].fillna('')
                
                total_retained_df.append(df)
                processed_files_count += 1
                
        except Exception as e:
            print(f"❌ Error processing {file_path}: {e}")
            continue

    if not total_retained_df:
        print("⚠️ 선별된 데이터가 없습니다.")
        return

    # Merge all
    merged_df = pd.concat(total_retained_df, ignore_index=True)
    
    # Deduplicate: Keep the latest record based on 최종수정시점
    if '최종수정시점' in merged_df.columns:
        merged_df = merged_df.sort_values(by='최종수정시점', ascending=False)
    
    merged_df = merged_df.drop_duplicates(subset=['record_key'], keep='first')
    
    # Final cleanup: drop record_key if necessary, but might be useful
    
    # Save results
    merged_df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
    
    print("\n✅ [처리 완료 리포트]")
    print(f"👉 처리된 파일수: {processed_files_count} / {len(all_csv_files)}")
    print(f"👉 최종 병합 레코드수: {len(merged_df):,}건")
    print(f"👉 저장 위치: {OUTPUT_FILE}")
    
    # Display top 10 as a preview
    if len(merged_df) > 0:
        print("\n📝 [데이터 리스트 일부(샘플)]")
        sample_cols = [c for c in ['사업장명', '소재지전체주소', '최종수정시점', '영업상태명'] if c in merged_df.columns]
        print(merged_df[sample_cols].head(10).to_string(index=False))

if __name__ == "__main__":
    process_directories()
