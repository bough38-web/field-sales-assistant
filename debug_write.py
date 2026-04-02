
import sys
import os
import json
from pathlib import Path
from unittest.mock import MagicMock

# Mock streamlit
sys.modules['streamlit'] = MagicMock()
sys.modules['streamlit.components'] = MagicMock()
sys.modules['streamlit.components.v1'] = MagicMock()

try:
    from src import activity_logger
    
    target_file = activity_logger.ACTIVITY_STATUS_FILE
    print(f"Target: {target_file}")
    
    # 1. Read
    initial_data = activity_logger.load_json_file(target_file)
    print(f"Initial Count: {len(initial_data)}")
    
    # 2. Write
    test_key = "Debug_Write_Test_Key"
    print(f"Attempting to save key: {test_key}")
    
    # Mock user info
    success = activity_logger.save_activity_status(test_key, "테스트", "Write Test", "DebugScript")
    
    print(f"Save Function Returned: {success}")
    
    # 3. Verify
    new_data = activity_logger.load_json_file(target_file)
    if test_key in new_data:
        print("✅ SUCCESS: Key found in file after save.")
        print(f"Value: {new_data[test_key]}")
    else:
        print("❌ FAILURE: Key NOT found in file after save.")
        
except Exception as e:
    print(f"Error: {e}")
