import os
import glob
import pandas as pd
import unicodedata
from src import data_loader

def normalize_str(s):
    return unicodedata.normalize('NFC', str(s)).strip()

def run_debug():
    print("--- Starting Deep Debug ---")
    
    # 1. correct file paths
    zip_files = sorted(glob.glob("data/*.zip"), key=os.path.getmtime, reverse=True)
    excel_files = sorted(glob.glob("data/*.xlsx"), key=os.path.getmtime, reverse=True)
    
    # Priority for 20260119
    excel_file = next((f for f in excel_files if '20260119' in f), excel_files[0] if excel_files else None)
    zip_file = zip_files[0] if zip_files else None
    
    if not excel_file or not zip_file:
        print("Missing files.")
        return

    print(f"Using ZIP: {zip_file}")
    print(f"Using Excel: {excel_file}")
    
    # 2. Run Loader
    print("Running load_and_process_data...")
    raw_df, error = data_loader.load_and_process_data(zip_file, excel_file)
    
    if error:
        print(f"Error: {error}")
        return
        
    print(f"Loaded {len(raw_df)} rows.")
    
    # 3. Normalize like App
    for col in ['관리지사', 'SP담당']:
        if col in raw_df.columns:
            raw_df[col] = raw_df[col].astype(str).apply(normalize_str)
            
    # 4. Check Central Branch
    target_branch = normalize_str("중앙지사")
    central_df = raw_df[raw_df['관리지사'] == target_branch]
    
    print(f"\n[Analysis: Central Branch ({target_branch})]")
    print(f"Total Rows: {len(central_df)}")
    
    if len(central_df) > 0:
        managers = sorted(central_df['SP담당'].unique())
        print(f"Unique Managers: {managers}")
        
        # Check for Gangbuk leak
        gangbuk_suspects = ['강북', '성진수'] # Example specific names
        for m in managers:
            print(f" - {m}")
    else:
        print("CRITICAL: No rows found for Central Branch.")
        
    # 5. Check Gangbuk Branch
    gangbuk_branch = normalize_str("강북지사")
    gb_df = raw_df[raw_df['관리지사'] == gangbuk_branch]
    print(f"\n[Analysis: Gangbuk Branch ({gangbuk_branch})]")
    print(f"Total Rows: {len(gb_df)}")
    print(f"Unique Managers: {sorted(gb_df['SP담당'].unique())}")

if __name__ == "__main__":
    run_debug()
