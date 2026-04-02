import pandas as pd
import os

# Possible data files
target_files = [
    'data/MASTER_2026_MERGED_FINAL.csv',
    'data/LOCALDATA_2026_ONLY.csv'
]

results = []

for file_path in target_files:
    if os.path.exists(file_path):
        print(f"Analyzing {file_path}...")
        try:
            # Use low_memory=False to avoid DtypeWarning for large files
            df = pd.read_csv(file_path, low_memory=False)
            total_rows = len(df)
            
            # Address columns
            addr_cols = ['소재지전체주소', '도로명전체주소']
            
            file_results = {"file": file_path, "total": total_rows}
            
            for col in addr_cols:
                if col in df.columns:
                    # Count rows with '*'
                    masked_count = df[col].astype(str).str.contains('\*', na=False).sum()
                    file_results[f"{col}_masked"] = masked_count
                    
            results.append(file_results)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")

if not results:
    print("No data files found to analyze.")
else:
    for res in results:
        print(f"\n--- Results for {res['file']} ---")
        print(f"Total Records: {res['total']:,}")
        for k, v in res.items():
            if k.endswith('_masked'):
                pct = (v / res['total']) * 100
                print(f"Masked {k.replace('_masked', '')}: {v:,} ({pct:.2f}%)")
