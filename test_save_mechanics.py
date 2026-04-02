
import os
import sys
import json
from pathlib import Path

# Setup paths
BASE_DIR = Path(os.path.abspath("."))
sys.path.append(str(BASE_DIR))

from src import activity_logger
from src import utils

def test_save():
    print(f"Testing Save Mechanism...")
    print(f"BASE_DIR: {BASE_DIR}")
    print(f"Logger Storage Dir: {activity_logger.STORAGE_DIR}")
    
    # 1. Generate Key
    title = "Test_Save_Mechanic_Corp"
    addr = "Seoul Gangnam Test 123"
    key = utils.generate_record_key(title, addr)
    print(f"Generated Key: {key}")
    
    # 2. Save Status
    print("Saving status...")
    result = activity_logger.save_activity_status(key, "🔵 상담완료", "Mechanics Test Note", "Tester")
    if result:
        print("Save function returned True.")
    else:
        print("Save function returned False!")
        return
        
    # 3. Verify File
    status_file = activity_logger.ACTIVITY_STATUS_FILE
    print(f"Checking file: {status_file}")
    
    if not status_file.exists():
        print("ERROR: File does not exist after save!")
        return
        
    with open(status_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    if key in data:
        print("SUCCESS: Key found in storage.")
        print(f"Value: {data[key]}")
    else:
        print(f"FAILURE: Key '{key}' NOT found in storage.")
        print(f"Keys present: {list(data.keys())}")

if __name__ == "__main__":
    test_save()
