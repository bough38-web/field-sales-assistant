import os
import zipfile
import pandas as pd
import argparse
from glob import glob

MASTER_ZIP = "data/LOCALDATA_2026_MASTER.zip"

TARGET_REGIONS = ["서울특별시", "경기도", "강원도", "강원특별자치도"]
EXCLUDED_REGIONS = ["수원시", "용인시", "화성시", "평택시", "안성시", "오산시", "광주시", "이천시", "여주시", "양평군"]

def filter_df_regions(df):
    if df.empty: return df
    addr_col = next((c for c in df.columns if '주소' in c), None)
    if not addr_col: return df
    
    df[addr_col] = df[addr_col].astype(str)
    # 1. Target Include
    mask_in = df[addr_col].apply(lambda x: any(tr in x for tr in TARGET_REGIONS))
    df = df[mask_in]
    
    # 2. Target Exclude
    def is_excluded(val):
        if '경기도' in val or '경기 ' in val:
            return any(ex in val for ex in EXCLUDED_REGIONS)
        return False
        
    mask_ex = df[addr_col].apply(is_excluded)
    return df[~mask_ex]

def merge_sources_to_master(source_files):
    print(f"🚀 [통합 마스터 파일 관리자] 실행")
    print(f"👉 타겟 마스터: {MASTER_ZIP}")
    
    # 1. Load existing master data if exists
    master_vfs = {}
    if os.path.exists(MASTER_ZIP):
        print("📂 기존 마스터 파일 로딩 중...")
        with zipfile.ZipFile(MASTER_ZIP, 'r') as zf:
            for csv_name in zf.namelist():
                if csv_name.endswith('.csv'):
                    with zf.open(csv_name) as cf:
                        try:
                            df = pd.read_csv(cf, encoding='utf-8-sig', on_bad_lines='skip', low_memory=False)
                            master_vfs[csv_name] = df
                        except Exception as e:
                            print(f"⚠️ {csv_name} 파싱 실패 (Master): {e}")

    # 2. Add source data
    total_added = 0
    for src in source_files:
        print(f"📥 추가 소스 병합 중: {src}")
        if not os.path.exists(src):
            print(f"❌ 소스를 찾을 수 없습니다: {src}")
            continue
            
        if src.endswith('.zip'):
            with zipfile.ZipFile(src, 'r') as zf:
                for csv_name in [f for f in zf.namelist() if f.endswith('.csv')]:
                    with zf.open(csv_name) as cf:
                        try:
                            df = pd.read_csv(cf, encoding='utf-8-sig', on_bad_lines='skip', low_memory=False)
                        except:
                            cf.seek(0)
                            try:
                                df = pd.read_csv(cf, encoding='cp949', on_bad_lines='skip', low_memory=False)
                            except:
                                continue
                                
                        if not df.empty:
                            df = filter_df_regions(df)
                            if not df.empty:
                                if csv_name in master_vfs:
                                    master_vfs[csv_name] = pd.concat([master_vfs[csv_name], df], ignore_index=True)
                                else:
                                    master_vfs[csv_name] = df
                                total_added += len(df)
        elif os.path.isdir(src):
            # If it's a directory containing CSVs
            csvs = glob(os.path.join(src, "*.csv"))
            for csv_path in csvs:
                csv_name = os.path.basename(csv_path)
                try:
                    df = pd.read_csv(csv_path, encoding='cp949', on_bad_lines='skip', low_memory=False)
                except:
                    try:
                        df = pd.read_csv(csv_path, encoding='utf-8-sig', on_bad_lines='skip', low_memory=False)
                    except:
                        continue
                        
                if not df.empty:
                    df = filter_df_regions(df)
                    if not df.empty:
                        if csv_name in master_vfs:
                            master_vfs[csv_name] = pd.concat([master_vfs[csv_name], df], ignore_index=True)
                        else:
                            master_vfs[csv_name] = df
                        total_added += len(df)
                    
    print(f"✅ 총 {total_added}건의 새 레코드가 병합 버퍼에 추가되었습니다.")

    # 3. Deduplicate and Save to new Master
    print("🧹 중복 데이터 무결성 검사 및 마스터 파일 압축 중...")
    total_final_records = 0
    with zipfile.ZipFile(MASTER_ZIP, 'w', compression=zipfile.ZIP_DEFLATED) as zf_out:
        for csv_name, df in master_vfs.items():
            if df.empty: continue
            
            # Final Safety Filter
            df = filter_df_regions(df)
            if df.empty: continue
            
            subset_cols = []
            for candidate in ['지번주소', '도로명전체주소', '사업장명', '인허가일자']:
                if candidate in df.columns:
                    subset_cols.append(candidate)
                    
            if subset_cols:
                original_len = len(df)
                df = df.drop_duplicates(subset=subset_cols, keep='last')
            
            total_final_records += len(df)
            csv_str = df.to_csv(index=False, encoding='utf-8-sig')
            zf_out.writestr(csv_name, csv_str)
            
    master_mb = os.path.getsize(MASTER_ZIP) / (1024 * 1024)
    print(f"🎉 마스터 병합 완료! [총합 {total_final_records:,.0f}건, 최적화 파일 크기: {master_mb:.2f} MB]")
    print(f"👉 사용법: 다음번에 수동으로 새 폴더(예: DAILY_CHANGE_0328)를 받으시면, 이 스크립트를 다음과 같이 실행하세요:")
    print(f"👉 python scripts/merge_to_master.py '인허가자료db-API/기타자료/DAILY_CHANGE_0328'")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="마스터 아카이브 병합 유틸리티")
    parser.add_argument('sources', nargs='*', help='마스터에 병합할 ZIP 파일 또는 폴더 경로들')
    args = parser.parse_args()
    
    if not args.sources:
        print("💡 초기화 모드 실행 (기존 베이스라인 + 21~27일 일일 분 병합)")
        if os.path.exists(MASTER_ZIP):
            os.remove(MASTER_ZIP)
        merge_sources_to_master([
            "data/LOCALDATA_FILTERED_CSV-3월.zip",
            "인허가자료db-API/기타자료/DAILY_CHANGE_RECOVERED"
        ])
    else:
        merge_sources_to_master(args.sources)
