
import pandas as pd
import os
import unicodedata
import sys
from unittest.mock import MagicMock

# Mock streamlit to allow importing modules that use it
sys.modules['streamlit'] = MagicMock()
sys.modules['streamlit.components'] = MagicMock()
sys.modules['streamlit.components.v1'] = MagicMock()

# Now import utils
from src import utils
from src import activity_logger

def normalize(s):
    return unicodedata.normalize('NFC', str(s)) if pd.notna(s) else ""

def debug():
    # Load Data DIRECTLY (Avoid data_loader st dependency)
    print("Loading Data...")
    base_dir = "/Users/heebonpark/Downloads/내프로젝트모음/영업기회"
    data_dir = os.path.join(base_dir, "data")
    
    # Find Excel
    import glob
    excels = glob.glob(os.path.join(data_dir, "*.xlsx"))
    
    dist_file = [f for f in excels if '20260119' in f][0] if any('20260119' in f for f in excels) else excels[0]
    print(f"Dist: {dist_file}")
    
    # Load Excel
    try:
        raw_df = pd.read_excel(dist_file, engine='openpyxl')
        # Simple processing
        if '관리지사' in raw_df.columns:
             raw_df['관리지사'] = raw_df['관리지사'].fillna('미지정')
             raw_df.loc[raw_df['관리지사'].astype(str).str.strip() == '', '관리지사'] = '미지정'
    except Exception as e:
        print(f"Error reading Excel: {e}")
        return

    # 1. Find '팥티오'
    print("\n--- Searching for 팥티오 ---")
    
    # Normalize
    raw_df['사업장명_norm'] = raw_df['사업장명'].astype(str).apply(normalize)
    
    targets = raw_df[raw_df['사업장명_norm'].str.contains('팥티오')]
    
    if targets.empty:
        print("❌ '팥티오' not found in raw_df!")
        return
        
    print(f"Found {len(targets)} records:")
    # Get touched keys for comparison
    from src.activity_logger import ACTIVITY_STATUS_FILE, load_json_file
    status_data = load_json_file(ACTIVITY_STATUS_FILE)
    touched_keys = list(status_data.keys())
    
    for idx, row in targets.iterrows():
        b_name = row.get('관리지사', '미지정')
        addr = row['소재지전체주소']
        nm = row['사업장명']
        print(f"[{idx}] {nm} | 지사: {b_name} | 주소: {addr}")
        
        key = utils.generate_record_key(nm, addr)
        print(f"    Key: {key}")
        
        is_touched = key in touched_keys
        print(f"    Is in Activity Storage? {is_touched}")
        
        # 2. Simulate Filter Logic
        # Filter Line 1481: '미지정' check
        removed_by_unassigned = (b_name == '미지정')
        
        print(f"    Ref: '미지정' Filter removes it? {removed_by_unassigned}")
        
        # Filter Line 1515: Security check (Assigned vs Touched)
        # Assuming user is Manager and not assigned
        passed_security = is_touched # If not assigned, must be touched
        print(f"    Ref: Security Filter (Touched) passes? {passed_security}")
        
        if removed_by_unassigned:
            print("    RESULT: HIDDEN by '미지정' Filter (Line 1481) regardless of Security Check.")

if __name__ == "__main__":
    debug()
