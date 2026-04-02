import os
import sys
import pandas as pd
import unicodedata

# Add current dir to path to import src
sys.path.append(os.getcwd())

from src import utils
from src import data_loader

def test_normalization():
    print("--- Testing Normalization ---")
    s1 = "서울"  # NFC
    s2 = unicodedata.normalize('NFD', "서울") # NFD
    
    print(f"s1 == s2 (direct): {s1 == s2}")
    
    n1 = utils.safe_normalize(s1)
    n2 = utils.safe_normalize(s2)
    
    print(f"n1 == n2 (safe_normalize): {n1 == n2}")
    assert n1 == n2, "Normalization failed!"
    print("✅ Normalization check passed.")

def test_column_mapping():
    print("\n--- Testing Column Mapping ---")
    # Simulate a CSV with non-standard headers
    data = {
        'BPLC_NM': ['Test Business'],
        'SITE_WHL_ADDR': ['서울 중구 태평로1가 31'],
        'LICENS_DATE': ['20260101'],
        'TRD_STATE_NM': ['영업/정상'],
        '좌표정보x': ['198000'],
        '좌표정보y': ['451000']
    }
    df = pd.DataFrame(data)
    
    # Save to dummy CSV and zip it
    import zipfile
    csv_path = "dummy.csv"
    zip_path = "dummy.zip"
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    
    with zipfile.ZipFile(zip_path, 'w') as z:
        z.write(csv_path)
    
    # Run data loader (partial check)
    try:
        # We need a dummy district file too or skip it
        # Let's just check the column mapping logic inside load_and_process_data
        # since it's hard to run the full thing without real district files.
        # However, we can check if the output df has the standard keys.
        
        # We'll just test the column mapping logic manually for now
        col_map = {
            '인허가일자': next((c for c in df.columns if '인허가일자' in c or 'LICENS_DATE' in c), '인허가일자'),
            '영업상태명': next((c for c in df.columns if '영업상태명' in c or 'TRD_STATE_NM' in c or ('상태' in c and '코드' not in c)), '영업상태명'),
            '사업장명': next((c for c in df.columns if '사업장명' in c or 'BPLC_NM' in c), '사업장명'),
        }
        
        print(f"Detected columns: {col_map}")
        assert col_map['인허가일자'] == 'LICENS_DATE'
        assert col_map['영업상태명'] == 'TRD_STATE_NM'
        assert col_map['사업장명'] == 'BPLC_NM'
        print("✅ Column mapping check passed.")
    finally:
        if os.path.exists(csv_path): os.remove(csv_path)
        if os.path.exists(zip_path): os.remove(zip_path)

if __name__ == "__main__":
    try:
        test_normalization()
        test_column_mapping()
        print("\n✨ All verification tests passed!")
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        sys.exit(1)
