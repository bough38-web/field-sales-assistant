import pandas as pd
import glob
import os

# Find the specific file
target_file = "data/1.영업구역별_주소현행화20260119.xlsx"

if not os.path.exists(target_file):
    print(f"File not found: {target_file}")
    # Try finding similarly named files
    files = glob.glob("data/*.xlsx")
    print(f"Available files: {files}")
    if files:
        target_file = files[0] # Fallback
else:
    print(f"Analyzing {target_file}...")

try:
    df = pd.read_excel(target_file)
    print(f"Columns: {list(df.columns)}")
    
    # Normalize column names if needed
    if '관리지사' in df.columns and 'SP담당' in df.columns:
        # Filter for Central Branch
        central_rows = df[df['관리지사'] == '중앙지사']
        print(f"\n[Central Branch] Total Rows: {len(central_rows)}")
        
        managers = central_rows['SP담당'].unique()
        print(f"Managers in Central Branch: {managers}")
        
        # Check specifically for Seong
        seong_in_central = central_rows[central_rows['SP담당'] == '성진수']
        if not seong_in_central.empty:
            print("\n!!! FOUND SEONG JIN-SU IN CENTRAL BRANCH !!!")
            print(seong_in_central.head())
        else:
            print("\nSeong Jin-su is NOT in Central Branch in this file.")
            
        # Check where Seong IS
        seong_rows = df[df['SP담당'] == '성진수']
        print(f"\n[Seong Jin-su] Branch assignments: {seong_rows['관리지사'].unique()}")
        
    else:
        print("Required columns '관리지사' or 'SP담당' not found.")

except Exception as e:
    print(f"Error: {e}")
