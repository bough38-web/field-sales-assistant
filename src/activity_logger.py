import json
import os
from datetime import datetime
from pathlib import Path

# Storage directory
STORAGE_DIR = Path(__file__).parent.parent / "storage"
STORAGE_DIR.mkdir(exist_ok=True)

ACCESS_LOG_FILE = STORAGE_DIR / "access_logs.json"
ACTIVITY_STATUS_FILE = STORAGE_DIR / "activity_status.json"
CHANGE_HISTORY_FILE = STORAGE_DIR / "change_history.json"


def load_json_file(filepath):
    """Load JSON file, return empty dict/list if not exists"""
    if filepath.exists():
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return [] if 'logs' in filepath.name or 'history' in filepath.name else {}
    return [] if 'logs' in filepath.name or 'history' in filepath.name else {}


def save_json_file(filepath, data):
    """Save data to JSON file"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ===== ACCESS LOGGING =====

def log_access(user_role, user_name, action="login"):
    """Log user access"""
    logs = load_json_file(ACCESS_LOG_FILE)
    
    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_role": user_role,
        "user_name": user_name,
        "action": action
    }
    
    logs.append(log_entry)
    
    # Keep only last 1000 entries
    if len(logs) > 1000:
        logs = logs[-1000:]
    
    save_json_file(ACCESS_LOG_FILE, logs)


def get_access_logs(limit=100):
    """Get recent access logs"""
    logs = load_json_file(ACCESS_LOG_FILE)
    return logs[-limit:] if logs else []


# ===== ACTIVITY STATUS =====

def get_record_key(row):
    """Generate unique key for a record"""
    return f"{row.get('사업장명', '')}_{row.get('소재지전체주소', '')}"


def get_activity_status(record_key):
    """Get activity status for a record"""
    statuses = load_json_file(ACTIVITY_STATUS_FILE)
    return statuses.get(record_key, {
        "활동진행상태": "",
        "특이사항": "",
        "변경일시": "",
        "변경자": ""
    })


def save_activity_status(record_key, status, notes, user_name):
    """Save activity status for a record"""
    statuses = load_json_file(ACTIVITY_STATUS_FILE)
    
    old_data = statuses.get(record_key, {})
    
    new_data = {
        "활동진행상태": status,
        "특이사항": notes,
        "변경일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "변경자": user_name
    }
    
    statuses[record_key] = new_data
    save_json_file(ACTIVITY_STATUS_FILE, statuses)
    
    # Log change history
    if old_data.get("활동진행상태") != status or old_data.get("특이사항") != notes:
        log_change_history(record_key, old_data, new_data, user_name)


def log_change_history(record_key, old_data, new_data, user_name):
    """Log change to history"""
    history = load_json_file(CHANGE_HISTORY_FILE)
    
    change_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "record_key": record_key,
        "user": user_name,
        "old_status": old_data.get("활동진행상태", ""),
        "new_status": new_data.get("활동진행상태", ""),
        "old_notes": old_data.get("특이사항", ""),
        "new_notes": new_data.get("특이사항", "")
    }
    
    history.append(change_entry)
    
    # Keep only last 5000 entries
    if len(history) > 5000:
        history = history[-5000:]
    
    save_json_file(CHANGE_HISTORY_FILE, history)


def get_change_history(record_key=None, limit=100):
    """Get change history, optionally filtered by record_key"""
    history = load_json_file(CHANGE_HISTORY_FILE)
    
    if record_key:
        history = [h for h in history if h.get("record_key") == record_key]
    
    return history[-limit:] if history else []
