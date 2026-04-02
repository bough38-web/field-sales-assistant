import pandas as pd
import sys
import os
import io

# Add src to path
sys.path.append(os.path.abspath('.'))

from src.data_loader import load_and_process_data

def test_status_standardization():
    # Mock some CSV data with a status column NOT named '영업상태명'
    # Example: '영업상태(상태코드)'
    csv_content = """인허가일자,영업상태(상태코드),사업장명,소재지전체주소
20240101,영업,가게1,서울 강남구 역삼동 1
20240505,폐업,가게2,서울 강남구 역삼동 2
"""
    # Create a zip with this CSV
    import zipfile
    with zipfile.ZipFile('test_data.zip', 'w') as z:
        z.writestr('data.csv', csv_content)
    
    # Mock district data
    district_data = pd.DataFrame([
        {'주소시': '서울', '주소군구': '강남구', '주소동': '역삼동', '관리지사': '강남지사', 'SP담당': '김철수'}
    ])
    
    # Since load_and_process_data uses glob to find files in temp_extracted, 
    # we need to be careful. But it extracts from our zip.
    
    # Process
    df, mgr_info, err, stats = load_and_process_data('test_data.zip', district_data)
    
    if df is None:
        print(f"❌ Load failed: {err}")
        return

    print(f"Columns in final df: {df.columns.tolist()}")
    
    # Assertion: '영업상태명' should exist
    assert '영업상태명' in df.columns
    print(f"Status Mapping Results:")
    print(df[['사업장명', '영업상태명']])
    
    assert df.loc[df['사업장명']=='가게1', '영업상태명'].iloc[0] == '영업'
    assert df.loc[df['사업장명']=='가게2', '영업상태명'].iloc[0] == '폐업'
    print("✅ Status standardization fix verified: '영업상태명' created from aliased column.")

if __name__ == "__main__":
    try:
        test_status_standardization()
    finally:
        if os.path.exists('test_data.zip'):
            os.remove('test_data.zip')
