import pandas as pd
import os
import glob
from datetime import datetime
import json

# Configuration
DATA_ROOT = "인허가자료db-API/기타자료"
DAILY_FOLDERS_PATTERN = os.path.join(DATA_ROOT, "DAILY_CHANGE_*")
OUTPUT_REPORT = "data/daily_status_report.json"

def generate_report():
    print("🚀 Generating Daily Status Report (New/Closed)...")
    
    daily_folders = glob.glob(DAILY_FOLDERS_PATTERN)
    all_stats = []

    for folder in sorted(daily_folders):
        folder_name = os.path.basename(folder)
        # Extract date from folder name: DAILY_CHANGE_20260318 -> 2026-03-18
        date_str = folder_name.replace("DAILY_CHANGE_", "")
        if len(date_str) == 6: # e.g. 202603
             date_display = f"{date_str[:4]}-{date_str[4:]}"
        elif len(date_str) == 8: # e.g. 20260318
             date_display = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        else:
             date_display = date_str

        csv_files = glob.glob(os.path.join(folder, "*.csv"))
        
        new_count = 0
        closed_count = 0
        categories = {}

        for file in csv_files:
            try:
                # [FIX] Read with CP949 encoding (standard for portal data)
                df = pd.read_csv(file, encoding='cp949', on_bad_lines='skip', low_memory=False)
                
                # Identify 'Status' column (영업상태명 or similar)
                status_col = '영업상태명' if '영업상태명' in df.columns else None
                if not status_col:
                    # Fallback to '상세영업상태명'
                    status_col = '상세영업상태명' if '상세영업상태명' in df.columns else None
                
                if status_col:
                    # Convert to string to prevent '.str accessor errors' on numeric/NaN types
                    status_series = df[status_col].astype(str)
                    news = df[status_series.str.contains('영업|정상|인허가', na=False)]
                    closeds = df[status_series.str.contains('폐업', na=False)]
                    
                    new_count += len(news)
                    closed_count += len(closeds)

                    # Track by category (file name usually contains category)
                    cat_name = os.path.basename(file).split('_')[3] if len(os.path.basename(file).split('_')) > 3 else "기타"
                    categories[cat_name] = categories.get(cat_name, {'new': 0, 'closed': 0})
                    categories[cat_name]['new'] += len(news)
                    categories[cat_name]['closed'] += len(closeds)

            except Exception as e:
                print(f"  ⚠️ Error reading {file}: {e}")

        all_stats.append({
            "date": date_display,
            "new": new_count,
            "closed": closed_count,
            "details": categories
        })

    # Output to JSON for app consumption
    os.makedirs(os.path.dirname(OUTPUT_REPORT), exist_ok=True)
    with open(OUTPUT_REPORT, 'w', encoding='utf-8') as f:
        json.dump(all_stats, f, ensure_ascii=False, indent=2)
    
    print(f"✨ Report generated: {OUTPUT_REPORT}")
    
    # Also print a summary table
    print("\nSummary Report:")
    print(f"{'Date':<12} | {'New':<5} | {'Closed':<6}")
    print("-" * 30)
    for s in all_stats:
        print(f"{s['date']:<12} | {s['new']:<5} | {s['closed']:<6}")

if __name__ == "__main__":
    generate_report()
