
import sys
import os
import json
import pandas as pd
from datetime import datetime

# Set up path to import src modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import activity_logger
from src import utils

def test_logic():
    print("Testing Visit/Interest Logic...")
    
    # Mock Data
    test_title = "테스트업체_ABC"
    test_addr = "서울시 강남구 테헤란로 123"
    test_user = "관리자"
    test_branch = "중앙지사"
    
    # 1. Generate Key
    key = utils.generate_record_key(test_title, test_addr)
    print(f"Generated Key: {key}")
    
    # 2. Simulate "Interest" Action (Map or Grid)
    print("\n--- Simulating Interest Action ---")
    # Log Status
    activity_logger.save_activity_status(key, "관심", "테스트 관심 등록", test_user)
    # Log Report (Draft)
    activity_logger.save_visit_report(key, test_user, test_branch, "[시스템] 관심 등록 테스트", None, None)
    
    # Verify Status
    status_data = activity_logger.load_json_file(activity_logger.ACTIVITY_STATUS_FILE)
    if key in status_data and status_data[key]['활동진행상태'] == "관심":
        print("✅ Status saved as '관심'")
    else:
        print("❌ Status save failed")
        
    # Verify Report
    reports = activity_logger.get_visit_reports(limit=10)
    found_report = False
    for r in reports:
        if r['record_key'] == key and "관심 등록 테스트" in r['content']:
            found_report = True
            print(f"✅ Report saved: {r['content']}")
            break
    if not found_report:
        print("❌ Report save failed")

    # 3. Simulate "Visit" Action (Map or Grid)
    print("\n--- Simulating Visit Action ---")
    u_info = {"name": test_user, "role": "admin", "branch": test_branch}
    activity_logger.register_visit(key, "[시스템] 방문 처리 테스트", None, None, u_info, forced_status="방문")
    
    # Verify Status
    status_data = activity_logger.load_json_file(activity_logger.ACTIVITY_STATUS_FILE)
    if key in status_data and status_data[key]['활동진행상태'] == "방문":
        print("✅ Status updated to '방문'")
    else:
        print("❌ Status update failed")

    # Verify Report (New one)
    reports = activity_logger.get_visit_reports(limit=10)
    found_visit = False
    for r in reports:
        if r['record_key'] == key and "방문 처리 테스트" in r['content']:
            found_visit = True
            print(f"✅ Visit Report saved: {r['content']}")
            break
    if not found_visit:
        print("❌ Visit Report save failed")
        
    print("\nTest Complete.")

if __name__ == "__main__":
    test_logic()
