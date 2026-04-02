
import sys
import os
from pathlib import Path

# Add src to path
sys.path.append(os.path.abspath("."))
from src import activity_logger

print(f"Storage Dir: {activity_logger.STORAGE_DIR}")
print(f"Exists: {activity_logger.STORAGE_DIR.exists()}")

try:
    print("Attempting to save dummy status...")
    activity_logger.save_activity_status("test_key_123", "테스트", "테스트 노트", "DebugUser")
    print("Save Status Success")
except Exception as e:
    print(f"Save Status Failed: {e}")

try:
    print("Attempting to save dummy visit report...")
    u_info = {"name": "DebugUser", "role": "admin", "branch": "TestBranch"}
    activity_logger.save_visit_report("test_key_123", "Test Content", None, None, u_info)
    print("Save Report Success")
except Exception as e:
    print(f"Save Report Failed: {e}")
