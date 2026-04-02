import pandas as pd
import sys
import os
import unicodedata

# Add src to path
sys.path.append(os.path.abspath('.'))

from src.data_loader import _process_and_merge_district_data

def test_mapping_with_city_fallback():
    # 1. Mock district data (Empty for Dong matches)
    district_data = pd.DataFrame(columns=['주소시', '주소군구', '주소동', '관리지사', 'SP담당'])
    
    # 2. Mock target data
    # - Case A: Paju (Should map to Goyang branch via fallback)
    # - Case B: Gangneung (Should map to Gangneung branch via fallback)
    # - Case C: Unknown City (Should stay unassigned)
    target_data = pd.DataFrame([
        {'소재지전체주소': '경기도 파주시 금촌동 123', '사업장명': '파주업체'},
        {'소재지전체주소': '강원도 강릉시 포남동 456', '사업장명': '강릉업체'},
        {'소재지전체주소': '충청남도 천안시 서북구 성정동', '사업장명': '천안업체'}
    ])
    
    # Process
    result_df, mgr_info, err = _process_and_merge_district_data(target_data, district_data)
    
    print("Mapping Results:")
    print(result_df[['사업장명', '소재지전체주소', '관리지사']])
    
    # Assertions
    paju_res = result_df.iloc[0]['관리지사']
    gangneung_res = result_df.iloc[1]['관리지사']
    cheonan_res = result_df.iloc[2]['관리지사']
    
    assert paju_res == '고양지사', f"Paju should be 고양지사 but got {paju_res}"
    assert gangneung_res == '강릉지사', f"Gangneung should be 강릉지사 but got {gangneung_res}"
    assert cheonan_res == '미지정', f"Cheonan should be 미지정 but got {cheonan_res}"
    
    print("✅ City-level fallback mapping verified successfully.")

if __name__ == "__main__":
    try:
        test_mapping_with_city_fallback()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
