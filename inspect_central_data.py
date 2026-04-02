import pandas as pd
import unicodedata
import os

# Path to the specific Excel file
file_path = "data/1.영업구역별_주소현행화20260119.xlsx"

print(f"Loading {file_path}...")
try:
    df = pd.read_excel(file_path)
    
    # Normalize columns if needed
    if '관리지사' in df.columns:
        df['관리지사'] = df['관리지사'].astype(str).apply(lambda x: unicodedata.normalize('NFC', x).strip() if pd.notna(x) else x)
    if 'SP담당' in df.columns:
        df['SP담당'] = df['SP담당'].astype(str).apply(lambda x: unicodedata.normalize('NFC', x).strip() if pd.notna(x) else x)

    # 1. Check all managers in "Central Branch" (중앙지사)
    central_managers = sorted(df[df['관리지사'] == '중앙지사']['SP담당'].unique())
    print("\n[Managers in '중앙지사' (Central Branch)]")
    print(central_managers)
    
    # 2. Check where specific managers are
    targets = ['남기민', '권대호', '김병조']
    print("\n[Target Manager Locations]")
    for mgr in targets:
        result = df[df['SP담당'] == mgr][['관리지사', 'SP담당']].drop_duplicates()
        if not result.empty:
            print(f"{mgr}: Found in {result['관리지사'].tolist()}")
        else:
            print(f"{mgr}: NOT FOUND in file")

except Exception as e:
    print(f"Error: {e}")
