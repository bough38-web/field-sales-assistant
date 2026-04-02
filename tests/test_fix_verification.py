import pandas as pd
import sys
import os

# Add src to path
sys.path.append(os.path.abspath('.'))

from src.data_loader import _process_and_merge_district_data

def test_mapping():
    # Mock district data
    district_data = pd.DataFrame([
        {'주소시': '서울', '주소군구': '강남구', '주소동': '역삼동', '관리지사': '강남지사', 'SP담당': '김철수'},
        {'주소시': '서울', '주소군구': '서초구', '주소동': '서초동', '관리지사': '서초지사', 'SP담당': '이영희'}
    ])
    
    # Mock target data
    # 1. Matching 서울 강남구 역삼동 -> 강남지사
    # 2. Not matching 서울 마포구 상암동 -> 미지정 (previously might have defaulted to first branch in Seoul)
    target_data = pd.DataFrame([
        {'소재지전체주소': '서울특별시 강남구 역삼동 123', '사업장명': 'A업체'},
        {'소재지전체주소': '서울특별시 마포구 상암동 456', '사업장명': 'B업체'}
    ])
    
    # Process
    result_df, mgr_info, err = _process_and_merge_district_data(target_data, district_data)
    
    print(f"Columns in result_df: {result_df.columns.tolist()}")
    print("Mapping Results:")
    if '관리지사' in result_df.columns:
        print(result_df[['사업장명', '관리지사', 'SP담당']])
    else:
        print("Columns '관리지사' or 'SP담당' NOT FOUND!")
        print(result_df)
    
    # Assertions
    assert result_df.iloc[0]['관리지사'] == '강남지사'
    assert result_df.iloc[1]['관리지사'] == '미지정'  # Crucial fix verification
    print("✅ Mapping bias fix verified: Unmatched addresses default to '미지정'.")

if __name__ == "__main__":
    try:
        test_mapping()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)
