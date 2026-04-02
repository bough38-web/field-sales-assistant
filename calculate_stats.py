
import pandas as pd
import zipfile
import os
import glob
import sys
import shutil

# Add current directory to path so we can import src
sys.path.append(os.getcwd())
try:
    from src import utils
except ImportError:
    # If running from root, src should be importable if __init__.py exists (checked earlier)
    pass

def load_stats():
    # 1. Identify Zip Files
    data_dir = "data"
    extract_folder = "temp_stats_extraction"
    
    # Clean up previous
    if os.path.exists(extract_folder):
        shutil.rmtree(extract_folder)
    os.makedirs(extract_folder, exist_ok=True)

    zip_files = [
        os.path.join(data_dir, "LOCALDATA_NOWMON_CSV.zip"),
        os.path.join(data_dir, "LOCALDATA_NOWMON_CSV_2월.zip")
    ]
    
    # Check if they exist
    valid_zips = [f for f in zip_files if os.path.exists(f)]
    print(f"Found zips: {valid_zips}")
    
    dfs = []
    
    # 2. Extract and Load
    for i, zip_path in enumerate(valid_zips):
        print(f"Processing {zip_path}...")
        sub_folder = os.path.join(extract_folder, f"zip_{i}")
        os.makedirs(sub_folder, exist_ok=True)
        
        zip_dfs = []
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(sub_folder)
                
            csv_files = glob.glob(os.path.join(sub_folder, "**/*.csv"), recursive=True)
            for file in csv_files:
                try:
                    # Quick check header first as per data_loader
                    temp_df = pd.read_csv(file, encoding='cp949', on_bad_lines='skip', nrows=1)
                    if not any('주소' in c for c in temp_df.columns): 
                        continue
                        
                    df = pd.read_csv(file, encoding='cp949', on_bad_lines='skip', dtype=str, low_memory=False)
                    zip_dfs.append(df)
                    dfs.append(df)
                except Exception as e:
                    print(f"Error reading {file}: {e}")
            
            if zip_dfs:
                zip_total = pd.concat(zip_dfs, ignore_index=True)
                print(f"  -> Found {len(zip_total):,} records in {os.path.basename(zip_path)}")
            else:
                print(f"  -> No valid records found in {os.path.basename(zip_path)}")

        except Exception as e:
            print(f"Error processing zip {zip_path}: {e}")

    if not dfs:
        print("No data found.")
        return

    # 3. Concatenate (Before Mix)
    concatenated_df = pd.concat(dfs, ignore_index=True)
    count_before = len(concatenated_df)
    
    # 4. Deduplicate (After Mix)
    # Using the logic from data_loader.py
    
    # Generate normalized key (mimicking data_loader logic)
    # Ensure columns exist to avoid key errors in lambda
    def safe_key(row):
        return utils.generate_record_key(
            row.get('사업장명', ''),
            row.get('소재지전체주소', '') or row.get('도로명전체주소', '') or row.get('주소', '')
        )

    concatenated_df['_temp_key'] = concatenated_df.apply(safe_key, axis=1)
    
    concatenated_df.drop_duplicates(subset=['_temp_key'], inplace=True)
    count_after = len(concatenated_df)
    
    print("-" * 30)
    print(f"Before Mix (Raw Sum): {count_before:,}")
    print(f"After Mix (Unique):   {count_after:,}")
    print(f"Removed Duplicates:   {count_before - count_after:,}")
    print("-" * 30)

    # Cleanup
    if os.path.exists(extract_folder):
        shutil.rmtree(extract_folder)

if __name__ == "__main__":
    load_stats()
