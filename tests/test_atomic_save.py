import sys
import os
import shutil
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.path.abspath("."))

from src import activity_logger
from src import utils

# Setup Mock Data
TEST_KEY = "TestBusiness_Seoul123"
TEST_USER = {"name": "TestUser", "role": "admin", "branch": "Seoul"}
TEST_CONTENT = "Atomic Save Test Content"

# Function to clear test data from JSONs
def clear_test_data():
    # Load Status
    statuses = activity_logger.load_json_file(activity_logger.ACTIVITY_STATUS_FILE)
    if TEST_KEY in statuses:
        del statuses[TEST_KEY]
        activity_logger.save_json_file(activity_logger.ACTIVITY_STATUS_FILE, statuses)
        print("Cleared test status.")

    # Load Reports (This is harder to delete specific one efficiently, but we can check existence)
    # For now, we just verify the append happened.
    pass

def run_test():
    print("=== STARTING ATOMIC SAVE TEST ===")
    
    # 0. Cleanup
    clear_test_data()
    
    # 1. Execute register_visit
    print("\n[Action] Calling register_visit...")
    success, msg = activity_logger.register_visit(
        TEST_KEY,
        TEST_CONTENT,
        None, # No audio
        None, # No photo
        TEST_USER
    )
    
    if not success:
        print(f"❌ Failed: {msg}")
        return
        
    print(f"✅ Success: {msg}")
    
    # 2. Verify Status File
    print("\n[Verification 1] Checking Activity Status JSON...")
    statuses = activity_logger.load_json_file(activity_logger.ACTIVITY_STATUS_FILE)
    status_data = statuses.get(TEST_KEY)
    
    if not status_data:
        print("❌ Test Key not found in status file!")
        return
        
    expected_status = activity_logger.ACTIVITY_STATUS_MAP["방문"]
    if status_data.get("활동진행상태") == expected_status:
        print(f"✅ Status updated correctly: {status_data.get('활동진행상태')}")
    else:
        print(f"❌ Status Validation Failed! Expected {expected_status}, Got {status_data.get('활동진행상태')}")
        
    if status_data.get("특이사항") == TEST_CONTENT:
        print(f"✅ Content updated correctly: {status_data.get('특이사항')}")
    else:
        print("❌ Content Validation Failed!")
        
    # 3. Verify Visit Report File
    print("\n[Verification 2] Checking Visit Report JSON...")
    reports = activity_logger.load_json_file(activity_logger.VISIT_REPORT_FILE)
    
    # Check last entry
    found = False
    for rep in reversed(reports):
        if rep.get("record_key") == TEST_KEY and rep.get("content") == TEST_CONTENT:
            print(f"✅ Report found! ID: {rep.get('id')}")
            found = True
            
            # Check Link
            if rep.get("resulting_status") == expected_status:
                print("✅ Report correctly linked to status.")
            else:
                 print(f"❌ Report status link mismatch! {rep.get('resulting_status')}")
            break
            
    if not found:
        print("❌ Report NOT found in JSON!")
        
    print("\n=== TEST COMPLETED ===")

if __name__ == "__main__":
    run_test()
