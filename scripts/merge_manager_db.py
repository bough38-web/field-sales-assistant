import pandas as pd
import os
import unicodedata

def normalize_nfc(s):
    if pd.isna(s): return s
    return unicodedata.normalize('NFC', str(s))

def merge_manager_db():
    f1 = 'data/temp_bkp/1.영업구역별_주소현행화20260304.xlsx'
    f2 = 'data/temp_bkp/2.영업구역별_주소현행화_담당자추가_20260304.xlsx'
    output = 'data/영업구역별_주소현행화_최종_20260304.xlsx'

    print(f"Loading {f1}...")
    df1 = pd.read_excel(f1)
    print(f"Loading {f2}...")
    df2 = pd.read_excel(f2)

    # Standard columns to keep
    cols = ['관리지사', '영업구역 수정', 'SP사번', 'SP담당', '주소시', '주소군구', '주소동']
    
    # Check if columns exist and handle mismatches
    df1_clean = df1[[c for c in cols if c in df1.columns]].copy()
    df2_clean = df2[[c for c in cols if c in df2.columns]].copy()

    # Normalize names for comparison
    df1_clean['SP담당'] = df1_clean['SP담당'].apply(normalize_nfc)
    df2_clean['SP담당'] = df2_clean['SP담당'].apply(normalize_nfc)

    # Merge
    merged_df = pd.concat([df1_clean, df2_clean], ignore_index=True)

    # Deduplicate but keep all for specific managers if requested?
    # The user said "안수호 담당은 1번, 2번 파일의 주소 적용"
    # This implies we should keep both. Simple concat handles this.
    # To be safe, we deduplicate by ALL columns to avoid exact duplicates.
    before_count = len(merged_df)
    merged_df.drop_duplicates(inplace=True)
    after_count = len(merged_df)

    print(f"Merged {before_count} rows. After deduplication: {after_count} rows.")
    
    # Verify 안수호
    ansuho_rows = merged_df[merged_df['SP담당'] == normalize_nfc('안수호')]
    print(f"안수호 담당 데이터 수: {len(ansuho_rows)}건")

    merged_df.to_excel(output, index=False)
    print(f"Saved to {output}")

if __name__ == "__main__":
    merge_manager_db()
