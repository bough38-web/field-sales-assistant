
import os
import json
from datetime import datetime
import streamlit as st

DATA_DIR = "data"
VOC_FILE = os.path.join(DATA_DIR, "voc_requests.json")

def load_voc_requests():
    """Load all VOC requests from JSON"""
    if not os.path.exists(VOC_FILE):
        return []
    try:
        with open(VOC_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading VOC: {e}")
        return []

def save_voc_requests(requests):
    """Save VOC requests list"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(VOC_FILE, 'w', encoding='utf-8') as f:
            json.dump(requests, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving VOC: {e}")
        return False

def add_voc_request(user_role, user_name, region, subject, content, priority="Normal"):
    """
    Add a new VOC request.
    Status defaults to 'New'.
    """
    requests = load_voc_requests()
    
    new_req = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S"),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_role": user_role,
        "user_name": user_name,
        "region": region,
        "subject": subject,
        "content": content,
        "priority": priority,
        "status": "New",  # New, In Progress, Done
        "admin_comment": ""
    }
    
    requests.insert(0, new_req) # Add to top
    return save_voc_requests(requests)

def update_voc_status(req_id, new_status, admin_comment=""):
    """Update status and comment of a request by ID"""
    requests = load_voc_requests()
    updated = False
    
    for req in requests:
        if req['id'] == req_id:
            req['status'] = new_status
            req['admin_comment'] = admin_comment
            updated = True
            break
            
    if updated:
        save_voc_requests(requests)
    return updated

def get_status_badge(status):
    """Return styling for status"""
    if status == 'New':
        return "🔴 접수"
    elif status == 'In Progress':
        return "🟡 진행중"
    elif status == 'Done':
        return "✅ 완료"
    return status

def delete_voc_request(req_id):
    """Delete a VOC request by ID"""
    requests = load_voc_requests()
    original_count = len(requests)
    requests = [req for req in requests if req['id'] != req_id]
    
    if len(requests) < original_count:
        save_voc_requests(requests)
        return True
    return False
