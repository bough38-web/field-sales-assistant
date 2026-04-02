
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock

# Mock streamlit
sys.modules['streamlit'] = MagicMock()
sys.modules['streamlit.components'] = MagicMock()
sys.modules['streamlit.components.v1'] = MagicMock()

try:
    from src import activity_logger
    
    print(f"Current Working Directory: {os.getcwd()}")
    print(f"activity_logger file: {activity_logger.__file__}")
    print(f"Calculated BASE_DIR: {activity_logger.BASE_DIR}")
    print(f"Calculated STORAGE_DIR: {activity_logger.STORAGE_DIR}")
    print(f"ACTIVITY_STATUS_FILE: {activity_logger.ACTIVITY_STATUS_FILE}")
    
    file_exists = activity_logger.ACTIVITY_STATUS_FILE.exists()
    print(f"File Exists? {file_exists}")
    
    if file_exists:
        data = activity_logger.load_json_file(activity_logger.ACTIVITY_STATUS_FILE)
        print(f"Loaded Data Keys Count: {len(data) if data else 0}")
        print(f"Sample Keys: {list(data.keys())[:3] if data else 'None'}")
    else:
        print("File does not exist at that path.")

except Exception as e:
    print(f"Error: {e}")
