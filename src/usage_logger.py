# Version: 2026-03-11_v13 (Admin Sync Notify)
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

# Storage directory
STORAGE_DIR = Path(os.path.expanduser("~")) / ".sales_assistant_data"
try:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    import tempfile
    STORAGE_DIR = Path(tempfile.gettempdir()) / ".sales_assistant_data"
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

USAGE_LOG_FILE = STORAGE_DIR / "usage_logs.json"

def load_json_file(filepath):
    """Load JSON file, return empty list if not exists"""
    if filepath.exists():
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_json_file(filepath, data):
    """Save data to JSON file (Redirects to activity_logger for GSheet Sync)"""
    from . import activity_logger
    return activity_logger.save_json_file(filepath, data)

# ===== USAGE LOGGING =====

def log_usage(user_role, user_name, user_branch, action, details=None):
    """
    Log user usage activity
    """
    logs = load_json_file(USAGE_LOG_FILE)
    
    from . import utils
    log_entry = {
        "timestamp": utils.get_now_kst_str(),
        "user_role": user_role,
        "user_name": user_name,
        "user_branch": user_branch,
        "action": action,
        "details": details or {}
    }
    
    logs.append(log_entry)
    
    # Keep only last 10000 entries
    if len(logs) > 10000:
        logs = logs[-10000:]
    
    save_json_file(USAGE_LOG_FILE, logs)

def get_usage_logs(days=30, user_name=None, user_branch=None, action=None):
    """
    Get usage logs with filters
    """
    logs = load_json_file(USAGE_LOG_FILE)
    
    if not logs:
        return []
    
    # Convert to DataFrame for easier filtering
    df = pd.DataFrame(logs)
    
    # [FIX] Robust timestamp conversion (Naive for comparison)
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    if hasattr(df['timestamp'], 'dt'):
        df['timestamp'] = df['timestamp'].dt.tz_localize(None)
    df = df.dropna(subset=['timestamp'])
    
    # Filter by date
    from . import utils
    # [FIX] Force cutoff_date to be naive
    cutoff_date = (utils.get_now_kst() - timedelta(days=days)).replace(tzinfo=None)
    df = df[df['timestamp'] >= cutoff_date]
    
    # Apply filters
    if user_name:
        df = df[df['user_name'] == user_name]
    if user_branch:
        df = df[df['user_branch'] == user_branch]
    if action:
        df = df[df['action'] == action]
    
    return df.to_dict('records')

def get_usage_stats(days=30):
    """
    Get usage statistics for admin dashboard
    """
    logs = load_json_file(USAGE_LOG_FILE)
    
    if not logs:
        return {
            "total_actions": 0,
            "unique_users": 0,
            "actions_by_type": {},
            "actions_by_user": {},
            "actions_by_branch": {},
            "daily_activity": {},
            "hourly_activity": {}
        }
    
    df = pd.DataFrame(logs)
    
    # [FIX] Robust timestamp conversion (Naive for comparison)
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    if hasattr(df['timestamp'], 'dt'):
        df['timestamp'] = df['timestamp'].dt.tz_localize(None)
    df = df.dropna(subset=['timestamp'])
    
    if df.empty:
        return {
            "total_actions": 0,
            "unique_users": 0,
            "actions_by_type": {},
            "actions_by_user": {},
            "actions_by_branch": {},
            "daily_activity": {},
            "hourly_activity": {}
        }

    # Filter by date
    from . import utils
    # [FIX] Force cutoff_date to be naive
    cutoff_date = (utils.get_now_kst() - timedelta(days=days)).replace(tzinfo=None)
    df = df[df['timestamp'] >= cutoff_date]
    
    # Calculate statistics
    stats = {
        "total_actions": len(df),
        "unique_users": df['user_name'].nunique(),
        "unique_branches": df['user_branch'].nunique(),
        
        # Actions by type
        "actions_by_type": df['action'].value_counts().to_dict(),
        
        # Actions by user (top 20)
        "actions_by_user": df['user_name'].value_counts().head(20).to_dict(),
        
        # Actions by branch
        "actions_by_branch": df['user_branch'].value_counts().to_dict(),
        
        # Daily activity (last 30 days)
        "daily_activity": df.groupby(df['timestamp'].dt.date).size().to_dict(),
        
        # Hourly activity (0-23)
        "hourly_activity": df.groupby(df['timestamp'].dt.hour).size().to_dict(),
        
        # Most active users (with details)
        "top_users": df.groupby(['user_name', 'user_branch', 'user_role']).size().reset_index(name='count').sort_values('count', ascending=False).head(10).to_dict('records')
    }
    
    # Convert date keys to strings for JSON serialization
    stats['daily_activity'] = {str(k): v for k, v in stats['daily_activity'].items()}
    
    return stats

def get_user_activity_timeline(user_name, days=7):
    """
    Get detailed activity timeline for a specific user
    """
    logs = load_json_file(USAGE_LOG_FILE)
    
    if not logs:
        return []
    
    df = pd.DataFrame(logs)
    
    # [FIX] Robust timestamp conversion (Naive for comparison)
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    if hasattr(df['timestamp'], 'dt'):
        df['timestamp'] = df['timestamp'].dt.tz_localize(None)
    df = df.dropna(subset=['timestamp'])
    
    # Filter by user and date
    from . import utils
    # [FIX] Force cutoff_date to be naive
    cutoff_date = (utils.get_now_kst() - timedelta(days=days)).replace(tzinfo=None)
    df = df[(df['user_name'] == user_name) & (df['timestamp'] >= cutoff_date)]
    
    # Sort by timestamp descending
    df = df.sort_values('timestamp', ascending=False)
    
    return df.to_dict('records')

def log_navigation(user_role, user_name, user_branch, business_name, address, lat, lon):
    """
    Log navigation/route request to a specific business
    """
    log_usage(user_role, user_name, user_branch, 'navigation', {
        'business_name': business_name,
        'address': address,
        'lat': lat,
        'lon': lon
    })

def get_navigation_history(days=30, user_name=None, user_branch=None):
    """
    Get navigation history with business details
    """
    logs = load_json_file(USAGE_LOG_FILE)
    
    if not logs:
        return []
    
    # Filter for navigation actions only
    nav_logs = [log for log in logs if log.get('action') == 'navigation']
    
    if not nav_logs:
        return []
    
    df = pd.DataFrame(nav_logs)
    
    # [FIX] Robust timestamp conversion (Naive for comparison)
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    if hasattr(df['timestamp'], 'dt'):
        df['timestamp'] = df['timestamp'].dt.tz_localize(None)
    df = df.dropna(subset=['timestamp'])
    
    # Filter by date
    from . import utils
    # [FIX] Force cutoff_date to be naive
    cutoff_date = (utils.get_now_kst() - timedelta(days=days)).replace(tzinfo=None)
    df = df[df['timestamp'] >= cutoff_date]
    
    # Apply filters
    if user_name:
        df = df[df['user_name'] == user_name]
    if user_branch:
        df = df[df['user_branch'] == user_branch]
    
    # Extract business details from details column
    result = []
    for _, row in df.iterrows():
        # [FIX] Force details to be a dict v7
        details = row.get('details')
        if not isinstance(details, dict):
            details = {}
        result.append({
            'timestamp': row['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
            'user_name': row['user_name'],
            'user_branch': row['user_branch'],
            'business_name': details.get('business_name', ''),
            'address': details.get('address', ''),
            'lat': details.get('lat', 0),
            'lon': details.get('lon', 0)
        })
    
    return result

def get_navigation_stats(days=30):
    """
    Get navigation statistics for visualization
    """
    nav_history = get_navigation_history(days=days)
    
    if not nav_history:
        return {
            'total_navigations': 0,
            'unique_users': 0,
            'unique_businesses': 0,
            'navigations_by_user': {},
            'navigations_by_branch': {},
            'top_businesses': []
        }
    
    df = pd.DataFrame(nav_history)
    
    stats = {
        'total_navigations': len(df),
        'unique_users': df['user_name'].nunique(),
        'unique_businesses': df['business_name'].nunique(),
        
        # Navigations by user
        'navigations_by_user': df['user_name'].value_counts().to_dict(),
        
        # Navigations by branch
        'navigations_by_branch': df['user_branch'].value_counts().to_dict(),
        
        # Top visited businesses
        'top_businesses': df['business_name'].value_counts().head(20).to_dict(),
        
        # Daily navigation trend
        'daily_navigations': df.groupby(pd.to_datetime(df['timestamp'], errors='coerce').dt.date).size().to_dict()
    }
    
    # Convert date keys to strings
    stats['daily_navigations'] = {str(k): v for k, v in stats['daily_navigations'].items()}
    
    return stats

def log_interest(user_role, user_name, user_branch, business_name, address, road_address, lat, lon):
    """
    Log when a user marks a business as interesting
    """
    log_usage(user_role, user_name, user_branch, 'interest', {
        'business_name': business_name,
        'address': address,
        'road_address': road_address,
        'lat': lat,
        'lon': lon
    })

def get_interest_history(days=30, user_name=None, user_branch=None):
    """
    Get interest marking history with business details
    """
    logs = load_json_file(USAGE_LOG_FILE)
    
    if not logs:
        return []
    
    # Filter for interest actions only
    interest_logs = [log for log in logs if log.get('action') == 'interest']
    
    if not interest_logs:
        return []
    
    df = pd.DataFrame(interest_logs)
    
    # [FIX] Robust timestamp conversion (Naive for comparison)
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    if hasattr(df['timestamp'], 'dt'):
        df['timestamp'] = df['timestamp'].dt.tz_localize(None)
    df = df.dropna(subset=['timestamp'])
    
    # Filter by date
    from . import utils
    # [FIX] Force cutoff_date to be naive
    cutoff_date = (utils.get_now_kst() - timedelta(days=days)).replace(tzinfo=None)
    df = df[df['timestamp'] >= cutoff_date]
    
    # Apply filters
    if user_name:
        df = df[df['user_name'] == user_name]
    if user_branch:
        df = df[df['user_branch'] == user_branch]
    
    # Extract business details from details column
    result = []
    for _, row in df.iterrows():
        # [FIX] Force details to be a dict v7
        details = row.get('details')
        if not isinstance(details, dict):
            details = {}
        result.append({
            'timestamp': row['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
            'user_name': row['user_name'],
            'user_branch': row['user_branch'],
            'business_name': details.get('business_name', ''),
            'address': details.get('address', ''),
            'road_address': details.get('road_address', ''),
            'lat': details.get('lat', 0),
            'lon': details.get('lon', 0)
        })
    
    return result

def get_interest_stats(days=30):
    """
    Get interest statistics for visualization
    """
    interest_history = get_interest_history(days=days)
    
    if not interest_history:
        return {
            'total_interests': 0,
            'unique_users': 0,
            'unique_businesses': 0,
            'interests_by_user': {},
            'interests_by_branch': {},
            'top_businesses': [],
            'daily_interests': {}
        }
    
    df = pd.DataFrame(interest_history)
    
    stats = {
        'total_interests': len(df),
        'unique_users': df['user_name'].nunique(),
        'unique_businesses': df['business_name'].nunique(),
        
        # Interests by user
        'interests_by_user': df['user_name'].value_counts().to_dict(),
        
        # Interests by branch
        'interests_by_branch': df['user_branch'].value_counts().to_dict(),
        
        # Top interested businesses
        'top_businesses': df['business_name'].value_counts().head(20).to_dict(),
        
        # Daily interest trend
        'daily_interests': df.groupby(pd.to_datetime(df['timestamp'], errors='coerce').dt.date).size().to_dict()
    }
    
    # Convert date keys to strings
    stats['daily_interests'] = {str(k): v for k, v in stats['daily_interests'].items()}
    
    return stats
