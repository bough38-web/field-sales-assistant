# Version: 2026-03-11_v13 (Admin Sync Notify)
import json
import os
from datetime import datetime
from pathlib import Path
import pandas as pd
try:
    import streamlit as st
    from streamlit_gsheets import GSheetsConnection
    HAS_GSHEETS = True
except ImportError:
    HAS_GSHEETS = False

# [NEW] Drive Media Persistence Helper
def get_gdrive_service_and_creds():
    """Returns (drive_service, credentials) authorized from streamlit secrets"""
    if not HAS_GSHEETS or "connections" not in st.secrets or "gsheets" not in st.secrets.connections:
        return None
        
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.oauth2 import service_account
        
        # Use existing secrets
        creds_info = dict(st.secrets.connections.gsheets)
        valid_keys = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email', 
                      'client_id', 'auth_uri', 'token_uri', 'auth_provider_x509_cert_url', 
                      'client_x509_cert_url']
        creds_clean = {k: creds_info[k] for k in valid_keys if k in creds_info}
        
        # [FIX] Handle literal \n and potential whitespace in private_key from Streamlit Secrets
        if 'private_key' in creds_clean:
            pk = creds_clean['private_key']
            if isinstance(pk, str):
                # Replace escaped \n with actual newlines
                pk = pk.replace("\\n", "\n")
                # Remove extra quotes if present
                pk = pk.strip("'").strip('"')
                creds_clean['private_key'] = pk
        
        credentials = service_account.Credentials.from_service_account_info(creds_clean)
        drive_service = build('drive', 'v3', credentials=credentials)
        return drive_service, credentials, creds_clean # [NEW] Return creds_clean too
    except Exception as e:
        print(f"DEBUG: GDrive Auth Error: {e}")
        return None, None, None

def upload_to_gdrive(file_path, filename):
    """Uploads a file to Google Drive and returns a public view link."""
    drive_service, _, creds_clean = get_gdrive_service_and_creds()
    if not drive_service: return None
        
    try:
        # [DEBUG] Identify which Folder ID is being used
        drive_folder_id = st.secrets.get("drive_folder_id") or creds_info.get("drive_folder_id")
        print(f"DEBUG: GDrive - Detected Folder ID: {drive_folder_id}")
        
        # Upload
        file_metadata = {'name': filename}
        
        # [NEW] Use Shared Folder ID to bypass Service Account 0GB quota
        if drive_folder_id:
            file_metadata['parents'] = [drive_folder_id]
        else:
            print("DEBUG: GDrive - No Folder ID provided. Using default service account root.")
            
        media = MediaFileUpload(str(file_path), resumable=True)
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        file_id = file.get('id')
        
        # Make public
        drive_service.permissions().create(fileId=file_id, body={'type': 'anyone', 'role': 'reader'}).execute()
        
        # Return public link
        return f"https://drive.google.com/uc?export=view&id={file_id}"
        
    except Exception as e:
        err_msg = str(e)
        print(f"DEBUG: GDrive Upload Error: {err_msg}")
        if "HttpError 403" in err_msg:
            if "storageQuotaExceeded" in err_msg or "storage quota" in err_msg.lower():
                sa_email = creds_clean.get("client_email", "알 수 없음")
                st.error(f"⚠️ **구글 드라이브 용량 부족 (Quota Exceeded)**\n\n현재 폴더 ID: `{drive_folder_id or '미지정'}`")
                st.markdown(f"""
                서비스 계정은 기본 용량이 0GB이므로, 본인의 드라이브 폴더를 공유해 주셔야 합니다:

                
                1. **폴더 생성**: 본인 구글 드라이브에 사진 저장용 폴더를 만드세요.
                2. **공유 설정**: 폴더 우클릭 -> '공유' -> 아래 이메일을 **편집자**로 추가:
                   `{sa_email}`
                3. **ID 설정**: 폴더 주소창의 마지막 부분(ID)을 복사하여 Streamlit Secrets에 등록하세요.
                   * 예: `https://drive.google.com/drive/folders/1abc...xyz` -> **`1abc...xyz`** 부분만 복사
                   * Secrets 설정: `drive_folder_id = "복사한_ID"`
                """)
            else:
                st.error(f"⚠️ 구글 드라이브 권한 오류: Drive API 활성화 여부나 폴더 권한을 확인해 주세요.\n\n상세내용: {err_msg}")

                st.info("💡 위 상세내용에 링크가 있다면 클릭하여 'Enable'을 눌러주세요.")
        elif "ImportError" in err_msg or "ModuleNotFoundError" in err_msg:
            st.error("⚠️ 라이브러리 누락: google-api-python-client 등을 설치 중입니다. 잠시 후 상단 'Re-run'을 눌러주세요.")
        else:
            st.error(f"⚠️ 업로드 실패 (기타): {err_msg}")
            with st.expander("🛠 개발자용 상세 에러 (Traceback)"):
                st.exception(e)
        return None

# [NEW] Image Resizing Helper
def resize_image(image_file, max_size=(800, 800)):
    """Resizes an image while maintaining aspect ratio using PIL."""
    try:
        from PIL import Image
        import io
        
        img = Image.open(image_file)
        # Convert to RGB if necessary (for PNGs with transparency)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=85)
        return output.getvalue()
    except Exception as e:
        print(f"DEBUG: Image Resize Error: {e}")
        return image_file.getvalue() if hasattr(image_file, 'getvalue') else None

# Storage directory
# Use absolute path resolution to avoid issues with Streamlit execution context
# Storage directory - [FIX] Move outside project to prevent Streamlit reload loops
# BASE_DIR = Path(os.path.abspath(__file__)).parent.parent
# Storage directory - [FIX] Move outside project to prevent Streamlit reload loops
# [CLOUD_COMPAT] Handle read-only home directory by falling back to /tmp
STORAGE_DIR = Path(os.path.expanduser("~")) / ".sales_assistant_data"
try:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    import tempfile
    STORAGE_DIR = Path(tempfile.gettempdir()) / ".sales_assistant_data"
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

ACCESS_LOG_FILE = STORAGE_DIR / "access_logs.json"
USAGE_LOG_FILE = STORAGE_DIR / "usage_logs.json"
VIEW_LOG_FILE = STORAGE_DIR / "view_logs.json"
ACTIVITY_STATUS_FILE = STORAGE_DIR / "activity_status.json"
CHANGE_HISTORY_FILE = STORAGE_DIR / "change_history.json"
MAINTENANCE_FILE = STORAGE_DIR / "maintenance.json"

# [NEW] Diagnostic Helper
def get_storage_info():
    """Returns storage directory and file existence status"""
    files = {
        "access_logs": ACCESS_LOG_FILE.exists(),
        "usage_logs": USAGE_LOG_FILE.exists(),
        "view_logs": VIEW_LOG_FILE.exists(),
        "activity_status": ACTIVITY_STATUS_FILE.exists(),
        "maintenance": MAINTENANCE_FILE.exists()
    }
    return str(STORAGE_DIR), files

# [CONSTANTS] Activity Status Constants
# Centralized source of truth for all activity statuses
ACTIVITY_STATUS_MAP = {
    "방문": "✅ 방문",
    "상담중": "🟡 상담중",
    "상담완료": "🔵 상담완료",
    "상담불가": "🔴 상담불가",
    "계약완료": "🟢 계약완료"
}

# Helper to get normalized status
def normalize_status(status_str):
    if not status_str or status_str == "None" or status_str == "nan": return ""
    
    # Check if already has emoji (Value check)
    if status_str in ACTIVITY_STATUS_MAP.values():
        return status_str
        
    activity_key = str(status_str).replace("✅ ", "").replace("🟡 ", "").replace("🔵 ", "").replace("🔴 ", "").replace("🟢 ", "").strip()
    return ACTIVITY_STATUS_MAP.get(activity_key, status_str) # Default to original if no match


def load_json_file(filepath):
    """Load JSON file, return empty dict/list if not exists or corrupted"""
    filepath = Path(filepath) # Ensure Path object
    if filepath.exists():
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"CRITICAL: JSON Decode Error in {filepath}: {e}")
            # [SAFETY] Backup corrupted file
            try:
                from src import utils
                backup_path = filepath.with_suffix(f".bak_{utils.get_now_kst_str().replace(' ', '_').replace(':', '')}")
                os.rename(filepath, backup_path)
                print(f"Backing up corrupted file to {backup_path}")
            except: pass
            return [] if any(k in str(filepath.name) for k in ['logs', 'history', 'reports']) else {}
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
            return [] if any(k in str(filepath.name) for k in ['logs', 'history', 'reports']) else {}
    return [] if any(k in str(filepath.name) for k in ['logs', 'history', 'reports']) else {}

def get_maintenance_mode():
    """Get maintenance mode status"""
    data = load_json_file(MAINTENANCE_FILE)
    if not data or not isinstance(data, dict):
        return {"enabled": False, "message": "점검 및 업데이트 중이니 잠시만 기다려주세요."}
    return data

def set_maintenance_mode(enabled, message=None):
    """Set maintenance mode status"""
    data = get_maintenance_mode()
    data["enabled"] = enabled
    if message:
        data["message"] = message
    return save_json_file(MAINTENANCE_FILE, data)


def save_json_file(filepath, data, skip_sync=False):
    """Save data to JSON file atomically (Write to temp -> Rename)"""
    filepath = Path(filepath) # Ensure Path object
    try:
        # Ensure parent dir exists
        if hasattr(filepath, 'parent'):
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
        # Atomic Write Pattern
        temp_path = filepath.with_suffix('.tmp')
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno()) # Force write to disk
            
        # Rename temp to actual (Atomic on POSIX)
        os.replace(temp_path, filepath)
        
        # [REFINED] Sync to GSheet if it's one of the persistent files AND not skipped
        if not skip_sync and filepath.name in ["activity_status.json", "visit_reports.json", "change_history.json", "access_logs.json", "usage_logs.json", "view_logs.json"]:
            sync_to_gsheet(filepath.name, data)
            
        return True
    except Exception as e:
        # Fallback console log
        print(f"DEBUG: Error saving {filepath}: {e}")
        
        # [FIX] Critical logic: Only show error if it's NOT a background log
        is_background = any(log in str(filepath.name).lower() for log in ["usage_logs", "access_logs", "view_logs"])
        if not is_background:
            st.error(f"⚠️ 데이터 저장 오류 ({filepath.name}): {e}")
            
        # Try to clean up temp
        try:
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
        except: pass
def get_gspread_client():
    """Get authorized gspread client from secrets"""
    try:
        import gspread
        _, credentials, _ = get_gdrive_service_and_creds()
        if credentials:
            return gspread.authorize(credentials)
    except Exception as e:
        print(f"DEBUG: gspread Auth Error: {e}")
    return None

def sync_to_gsheet(filename, data, **kwargs):
    """Sync specific JSON data to Google Sheets for persistence"""
    if not HAS_GSHEETS: return
    
    # [NEW] Aggressive Silent Return for background logs immediately
    # Substring match to handle absolute paths, case-mismatches, etc.
    filename_lower = str(filename).lower()
    is_background = any(log in filename_lower for log in ["usage_logs", "access_logs", "view_logs"])
    
    # [NEW] Map to Korean Sheet names for user readability - Defined early to avoid NameError
    ws_name_map = {
        "access_logs": "로그인 이력",
        "usage_logs": "사용 이력",
        "view_logs": "조회 이력",
        "activity_status": "활동상태",
        "visit_reports": "방문보고서",
        "change_history": "변경내역"
    }
    internal_ws_name = filename.split('.')[0] if '.' in filename else filename
    ws_name = ws_name_map.get(internal_ws_name, internal_ws_name)

    if is_background:
        # If it's a background log, we proceed only IF we have service account secrets
        # But we do NOT want any error messages to reach the user.
        try:
            gs_secrets = st.secrets.connections.gsheets if "connections" in st.secrets and "gsheets" in st.secrets.connections else {}
            is_service_account = gs_secrets.get("type") == "service_account" and gs_secrets.get("private_key")
            if not is_service_account: return # SILENTLY return if not service account
        except: return # SILENTLY return on any secrets access error

    # We only sync in Streamlit context
    try:
        # Check if secrets/connection is configured
        gs_secrets = st.secrets.connections.gsheets if "connections" in st.secrets and "gsheets" in st.secrets.connections else {}
        if not gs_secrets:
            if is_background: return
            st.warning("⚠️ 구글 시트 연결 설정(Secrets)이 누락되었습니다. 데이터가 서버에만 저장됩니다.")
            return

        # [FIX] Determine Auth Mode (Service Account vs Public)
        is_service_account = gs_secrets.get("type") == "service_account" and gs_secrets.get("private_key")
        
        # [FIX] In Public mode, we cannot write. Skip writes for background logs to avoid clutter.
        if not is_service_account:
            if is_background:
                return
            else:
                # For critical data (activity_status), show a warning if triggered by Admin
                is_admin = st.session_state.get('user_role') == 'admin' or st.session_state.get('admin_auth')
                if is_admin:
                    st.info(f"💡 {ws_name}: '공개 URL' 방식에서는 시트 저장이 불가능합니다. (서비스 계정 설정 필요)")
                return

        conn = st.connection("gsheets", type=GSheetsConnection)
        
        # Convert to DataFrame
        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            # For dict-based statuses (activity_status), flatten to rows
            rows = []
            for k, v in data.items():
                row = {"record_key": k}
                row.update(v)
                rows.append(row)
            df = pd.DataFrame(rows)
        else:
            return
            
        # [NEW] Enforce Column Ordering and User-friendly Names for GSheet
        if internal_ws_name in ["activity_status", "visit_reports", "access_logs", "usage_logs", "view_logs"]:
            # 1. Ensure photo columns exist (even if all None) for relevant types
            if internal_ws_name in ["activity_status", "visit_reports"]:
                for c in ["photo_path1", "photo_path2", "photo_path3"]:
                    if c not in df.columns:
                        df[c] = None
                    
            # 2. Standard columns and ordering
            if internal_ws_name == "activity_status":
                # [REFINED] Google 이름 제외 (Exclude Changer Name)
                cols_order = ["record_key", "활동진행상태", "특이사항", "photo_path1", "photo_path2", "photo_path3", "변경일시"]
                # Filter to existing columns + photo columns we just ensured
                df = df[[c for c in cols_order if c in df.columns]]
                # Map names to Korean
                rename_map = {"photo_path1": "사진1", "photo_path2": "사진2", "photo_path3": "사진3"}
                df = df.rename(columns=rename_map)
            elif internal_ws_name == "visit_reports":
                # [REFINED] Google 이름 제외 (Exclude User Name)
                cols_order = ["timestamp", "record_key", "content", "resulting_status", "photo_path1", "photo_path2", "photo_path3", "user_branch"]
                df = df[[c for c in cols_order if c in df.columns]]
                rename_map = {"photo_path1": "사진1", "photo_path2": "사진2", "photo_path3": "사진3", "content": "방문내용", "resulting_status": "결과상태"}
                df = df.rename(columns=rename_map)
            elif internal_ws_name == "access_logs":
                # [NEW] Accessor Log Ordering
                cols_order = ["timestamp", "user_role", "user_name", "action"]
                df = df[[c for c in cols_order if c in df.columns]]
                # [FIX] Header Mismatch - Use "일시" to match Usage Logs
                rename_map = {"timestamp": "일시", "user_role": "권한", "user_name": "사용자", "action": "작업"}
                df = df.rename(columns=rename_map)
            elif internal_ws_name == "usage_logs":
                # [NEW] Usage Log Ordering
                cols_order = ["timestamp", "user_role", "user_name", "user_branch", "action", "details"]
                df = df[[c for c in cols_order if c in df.columns]]
                rename_map = {"timestamp": "일시", "user_role": "권한", "user_name": "사용자", "user_branch": "지사", "action": "작업", "details": "상세내용"}
                df = df.rename(columns=rename_map)
            
        # [REFINED] Robust Auto-create logic using direct gspread if provided
        gc = kwargs.get('gspread_client')
        spreadsheet = kwargs.get('spreadsheet_obj')
        existing_titles = kwargs.get('existing_titles')

        try:
            # 1. Try to get spreadsheet object if not provided
            if not spreadsheet and gc:
                ss_url = st.secrets.connections.gsheets.get("spreadsheet", "")
                if ss_url:
                    spreadsheet = gc.open_by_url(ss_url)
            
            # 2. Try falling back to streamlit-gsheets internal (for single calls)
            if not spreadsheet:
                if hasattr(conn, "_conn") and hasattr(conn._conn, "spreadsheet"):
                    spreadsheet = conn._conn.spreadsheet
                elif hasattr(conn, "_instance") and hasattr(conn._instance, "spreadsheet"):
                    spreadsheet = conn._instance.spreadsheet

            if spreadsheet:
                if existing_titles is None:
                    existing_titles = [ws.title for ws in spreadsheet.worksheets()]
                
                if ws_name not in existing_titles:
                    spreadsheet.add_worksheet(title=ws_name, rows=100, cols=20)
                    print(f"DEBUG: Created missing worksheet: {ws_name}")
            else:
                print(f"DEBUG: Skipping auto-creation as spreadsheet object could not be retrieved")
        except Exception as create_e:
            print(f"DEBUG: Failed to auto-create worksheet {ws_name}: {create_e}")

        # Update Spreadsheet
        conn.update(worksheet=ws_name, data=df)
        st.toast(f"✅ {ws_name} 동기화 완료")
        
    except Exception as e:
        # [FINAL AGGRESSIVE] Absolute Silent Return for background logs
        # Check both the calculated flag and the filename directly to be 100% sure
        filename_str = str(filename).lower()
        if is_background or any(x in filename_str for x in ["usage_logs", "access_logs", "view_logs"]):
            return

        # [REFINED] Log to console always, but only show Toast/Error to Admin
        err_msg = str(e)
        print(f"DEBUG: GSheet Sync Error ({filename}): {err_msg}")
        
        # [FIX] Detect "cannot be written to" error (Public Spreadsheet mode)
        if "cannot be written to" in err_msg.lower() or "not authorized" in err_msg.lower():
            is_admin = st.session_state.get('user_role') == 'admin' or st.session_state.get('admin_auth')
            if is_admin:
                st.info(f"💡 '{ws_name}' 업데이트 불가: 쓰기 권한이 없습니다. (시트를 개발자 서비스 계정에 '편집자'로 공유해 주세요)")
            return

        # If it's a WorksheetNotFound, we can try one more thing or just report it
        is_admin = st.session_state.get('user_role') == 'admin' or st.session_state.get('admin_auth')
        
        if is_admin:
            if "not found" in err_msg.lower() or "worksheetnotfound" in str(type(e)).lower():
                st.error(f"❌ '{ws_name}' 시트를 찾을 수 없습니다. 구글 시트에서 '편집자' 권한이 있는지 확인해 주세요.")
            else:
                # [DOUBLE CHECK] NEVER show this for background logs
                if not (is_background or any(x in filename_str for x in ["usage_logs", "access_logs", "view_logs"])):
                    st.error(f"❌ 구글 시트 동기화 실패 ({filename}): {e}")

def check_gsheet_connection():
    """Verify if GSheet connection is correctly configured and accessible"""
    if not HAS_GSHEETS:
        return False, "streamlit-gsheets 라이브러리가 설치되지 않았습니다."
        
    try:
        if "connections" not in st.secrets or "gsheets" not in st.secrets.connections:
            return False, "Streamlit Secrets에 'connections.gsheets' 설정이 없습니다."
            
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        # [DEBUG] Check authentication mode
        is_service_account = False
        try:
            gs_secrets = st.secrets.connections.gsheets
            pk = gs_secrets.get("private_key", "")
            if gs_secrets.get("type") == "service_account" and pk:
                is_service_account = True
                if not pk.startswith("-----BEGIN"):
                    print("[GSheet Debug] Warning: private_key does not start with BEGIN header")
                if "\\n" in pk and "\n" not in pk:
                    print("[GSheet Debug] Tip: private_key uses literal '\\n' instead of newlines")
            
            ss_url = gs_secrets.get("spreadsheet", "N/A")
            print(f"[GSheet Debug] Mode: {'Service Account' if is_service_account else 'Public URL'}")
            print(f"[GSheet Debug] Targeting: {ss_url[:20]}...")
        except:
            pass

        # [REFINED] Internal Diagnostic Loop
        discovered_ws = []
        try:
            if hasattr(conn, "_conn") and hasattr(conn._conn, "spreadsheet"):
                discovered_ws = [ws.title for ws in conn._conn.spreadsheet.worksheets()]
                print(f"[GSheet Debug] Discovered Tabs: {discovered_ws}")
        except Exception as e:
            print(f"[GSheet Debug] Failed to list worksheets: {e}")

        try:
            # Attempt to read the specific worksheet
            df = conn.read(worksheet="activity_status", ttl="0s", nrows=1)
            mode_text = "서비스 계정 - Full Access" if is_service_account else "공개 URL - Read Only"
            
            # [NEW] Masked Spreadsheet ID for verification
            ss_id = "N/A"
            if ss_id == "N/A" and ss_url and "/d/" in ss_url:
                ss_id = ss_url.split("/d/")[1].split("/")[0]
            masked_id = ss_id[:5] + "..." + ss_id[-5:] if len(ss_id) > 10 else ss_id
            
            return True, f"연결 성공! ({mode_text}, ID: {masked_id}, 확인된 탭: {', '.join(discovered_ws) if discovered_ws else '알수없음'})"
        except Exception as read_e:
            error_msg = str(read_e)
            full_error = repr(read_e)
            mode_text = "서비스 계정 인증" if is_service_account else "공개 URL 방식"
            
            # If we found worksheets but failed to read the specific one
            if discovered_ws:
                if "activity_status" not in discovered_ws:
                    return False, f"연결 실패 (탭 누락): 'activity_status' 탭을 찾을 수 없습니다.\n\n현재 모드: `{mode_text}`\n\n탭 목록: `{discovered_ws}`"
                else:
                    return False, f"연결 실패 (구조 오류): 'activity_status' 탭이 존재하지만 읽을 수 없습니다.\n\n현재 모드: `{mode_text}`\n\n**상세 오류**: `{full_error}`"
            
            # General fallback
            if "400" in error_msg:
                return False, f"연결 실패 (HTTP 400): `{mode_text}`으로 시트 접근 실패.\n\n**상세 오류**: `{full_error}`\n\n**조치**: {'Secrets 설정을 다시 확인하세요.' if is_service_account else '서비스 계정 정보를 Secrets에 등록하세요.'}"
            
            if "Permission" in full_error:
                return False, f"연결 실패 (권한 오류): `{mode_text}` 인증은 성공했으나, 시트에 접근할 권한이 없습니다.\n\n**상세 오류**: `{full_error}`\n\n**해결법**:\n1. 구글 시트 [공유] 단추를 누르고 `{gs_secrets.get('client_email')}`를 **편집자**로 추가했는지 확인하세요.\n2. [Google Cloud Console](https://console.cloud.google.com/apis/library/sheets.googleapis.com)에서 **Google Sheets API**를 '사용'으로 설정했는지 확인하세요."

            return False, f"연결 실패: {error_msg}\n\n`{full_error}`"
            
    except Exception as e:
        return False, f"설정 오류: {str(e)}\n\n(참고: 서비스 계정 이메일이 시트에 '편집자'로 공유되었는지 확인하세요.)"


def pull_from_gsheet():
    """Download data from Google Sheets to local storage (Initial Sync)"""
    if not HAS_GSHEETS: return
    
    try:
        if "connections" not in st.secrets or "gsheets" not in st.secrets.connections:
            return
            
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        # [REFINED] Use Korean worksheet names for pulling too
        mapping = {
            "로그인 이력": ACCESS_LOG_FILE,
            "사용 이력": USAGE_LOG_FILE,
            "조회 이력": VIEW_LOG_FILE,
            "방문보고서": VISIT_REPORT_FILE,
            "활동상태": ACTIVITY_STATUS_FILE,
            "변경내역": CHANGE_HISTORY_FILE
        }
        
        for ws_name_kr, local_path in mapping.items():
            try:
                # Read from Korean worksheet name
                df = conn.read(worksheet=ws_name_kr, ttl="0s")
                if df is not None and not df.empty:
                    # Map Korean headers back to internal keys for JSON stability
                    if ws_name_kr == "로그인 이력":
                        # [FIX] Header Mismatch - Use "일시" instead of "상태일시"
                        rename_map = {"일시": "timestamp", "권한": "user_role", "사용자": "user_name", "작업": "action"}
                        df = df.rename(columns=rename_map)
                    elif ws_name_kr == "사용 이력":
                        rename_map = {"일시": "timestamp", "권한": "user_role", "사용자": "user_name", "지사": "user_branch", "작업": "action", "상세내용": "details"}
                        df = df.rename(columns=rename_map)
                        # JSON decode details column if it's a string
                        if "details" in df.columns:
                            def safe_json_load(val):
                                if isinstance(val, str) and (val.startswith('{') or val.startswith('[')):
                                    try: return json.loads(val)
                                    except: return val
                                return val
                            df["details"] = df["details"].apply(safe_json_load)
                    elif ws_name_kr == "조회 이력":
                        rename_map = {"일시": "timestamp", "권한": "user_role", "사용자": "user_name", "대상": "target", "상세내용": "details"}
                        df = df.rename(columns=rename_map)

                    # Convert back to JSON structure
                    if ws_name_kr == "활동상태":
                        # Dict by record_key
                        new_data = {}
                        for _, row in df.iterrows():
                            d = row.to_dict()
                            key = d.pop("record_key", d.pop("ID", None)) # Try both
                            if key: new_data[key] = d
                    else:
                        # List of dicts
                        new_data = df.to_dict(orient="records")
                    
                    # Save locally (Atomic) - skip_sync=True to avoid redundant write back to GSheet
                    save_json_file(local_path, new_data, skip_sync=True)
            except Exception as inner_e:
                print(f"DEBUG: Pulled error for {ws_name_kr}: {inner_e}")
                
    except Exception as e:
        print(f"DEBUG: GSheet Pull Error: {e}")
        return False, str(e)

def push_to_gsheet():
    """Manually push all local data to Google Sheets (Full Sync)"""
    if not HAS_GSHEETS: return False, "GSheet 라이브러리 미설치"
    
    try:
        if "connections" not in st.secrets or "gsheets" not in st.secrets.connections:
             return False, "연결 설정이 없습니다."

        # [NEW] Batch setup for efficiency
        gc = get_gspread_client()
        spreadsheet = None
        existing_titles = []
        
        if gc:
            try:
                ss_url = st.secrets.connections.gsheets.get("spreadsheet", "")
                if ss_url:
                    spreadsheet = gc.open_by_url(ss_url)
                    existing_titles = [ws.title for ws in spreadsheet.worksheets()]
            except Exception as ss_e:
                print(f"DEBUG: Batch Sync - Could not open spreadsheet: {ss_e}")

        files_to_sync = {
            "activity_status.json": load_json_file(ACTIVITY_STATUS_FILE),
            "visit_reports.json": load_json_file(VISIT_REPORT_FILE),
            "view_logs.json": load_json_file(VIEW_LOG_FILE),
            "change_history.json": load_json_file(CHANGE_HISTORY_FILE),
            "access_logs.json": load_json_file(ACCESS_LOG_FILE),
            "usage_logs.json": load_json_file(USAGE_LOG_FILE),
            "view_logs.json": load_json_file(VIEW_LOG_FILE)
        }
        
        success_count = 0
        status_text = st.empty() # For real-time updates
        
        for filename, data in files_to_sync.items():
            if data:
                status_text.info(f"📤 {filename} 동기화 중...")
                sync_to_gsheet(filename, data, gspread_client=gc, spreadsheet_obj=spreadsheet, existing_titles=existing_titles)
                success_count += 1
        
        status_text.empty()
        return True, f"{success_count}개 파일 동기화 완료"
    except Exception as e:
        return False, str(e)


# ===== ACCESS LOGGING =====

def log_access(user_role, user_name, action="login"):
    """Log user access"""
    logs = load_json_file(ACCESS_LOG_FILE)
    
    log_entry = {
        "timestamp": utils.get_now_kst_str(),
        "user_role": user_role,
        "user_name": user_name,
        "action": action
    }
    
    logs.append(log_entry)
    
    # Keep only last 1000 entries
    if len(logs) > 1000:
        logs = logs[-1000:]
    
    save_json_file(ACCESS_LOG_FILE, logs)


def get_access_logs(limit=200, days=None):
    """Get recent access logs with optional date filtering"""
    logs = load_json_file(ACCESS_LOG_FILE)
    if not logs: return []
    
    if days:
        try:
            from datetime import timedelta
            df = pd.DataFrame(logs)
            
            # [REFINED] Robust Timestamp Conversion
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce', utc=True)
            
            # Use utils.get_now_kst() and convert to UTC for comparison
            from . import utils
            now_kst = utils.get_now_kst()
            cutoff_date = (now_kst - timedelta(days=days))
            
            # Ensure cutoff is also UTC-aware for safe comparison
            cutoff_utc = cutoff_date.astimezone(timedelta(0))
            
            # Filter
            df = df[df['timestamp'] >= cutoff_utc]
            
            # Convert back to KST string for display consistency if needed, 
            # or just keep as is for to_dict. 
            # [FIX] Localize back to KST for display strings in the dict
            # Use 'Asia/Seoul' explicitly instead of timedelta(hours=9) to avoid TypeError
            df['timestamp'] = df['timestamp'].dt.tz_convert('Asia/Seoul').dt.strftime('%Y-%m-%d %H:%M:%S')
            
            logs = df.to_dict('records')
        except Exception as e:
            print(f"DEBUG: get_access_logs filtering error: {e}")
            
    # If days is provided, we might want a larger default limit
    actual_limit = limit if days is None else max(limit, 500)
    return logs[-actual_limit:] if logs else []


# ===== ACTIVITY STATUS =====

from . import utils

def get_record_key(row):
    """Generate unique key for a record (Normalized)"""
    # Use centralized logic to prevent mismatch
    # Fallback to alternative address columns if primary is missing
    addr = row.get('소재지전체주소') or row.get('도로명전체주소') or row.get('주소') or ""
    return utils.generate_record_key(row.get('사업장명'), addr)


def get_activity_status(record_key):
    """Get activity status for a record"""
    statuses = load_json_file(ACTIVITY_STATUS_FILE)
    return statuses.get(record_key, {
        "활동진행상태": "",
        "특이사항": "",
        "변경일시": "",
        "변경자": ""
    })


def save_activity_status(record_key, status, notes, user_name, user_branch=None, user_role=None):
    """
    Save activity status for a record (Direct Update).
    Automatically creates a visit report entry if status changes for visibility.
    """
    from src import utils
    status = normalize_status(status)
    
    statuses = load_json_file(ACTIVITY_STATUS_FILE)
    old_data = statuses.get(record_key, {})
    
    ts_str = utils.get_now_kst_str()
    
    new_data = {
        "활동진행상태": status,
        "특이사항": notes,
        "변경일시": ts_str,
        "변경자": user_name,
        "photo_path1": old_data.get("photo_path1"),
        "photo_path2": old_data.get("photo_path2"),
        "photo_path3": old_data.get("photo_path3")
    }

    
    statuses[record_key] = new_data
    save_json_file(ACTIVITY_STATUS_FILE, statuses)
    
    # Log Change if different
    if old_data.get("활동진행상태") != status or old_data.get("특이사항") != notes:
        log_change_history(record_key, old_data, new_data, user_name)
        
        # [NEW] Integration: Create a visit report for visibility in "Activity History"
        # Only if it's not already a "Visit" which is handled by register_visit
        if status != ACTIVITY_STATUS_MAP.get("방문"):
            # Use string ID for consistency
            id_str = ts_str.replace("-", "").replace(" ", "_").replace(":", "").replace("+", "_")
            visit_entry = {
                "id": f"rep_sys_{id_str}_{record_key[:5]}",
                "timestamp": ts_str,
                "record_key": record_key,
                "content": f"[시스템 자동] 활동 상태가 '{status}'(으)로 변경되었습니다. (특이사항: {notes or '-'})",
                "audio_path": None,
                "photo_path": None,
                "photo_path1": None,
                "photo_path2": None,
                "photo_path3": None,
                "user_name": user_name,
                "user_role": user_role,
                "user_branch": user_branch,
                "resulting_status": status
            }
            
            reports = load_json_file(VISIT_REPORT_FILE)
            if not isinstance(reports, list): reports = []
            reports.append(visit_entry)
            save_json_file(VISIT_REPORT_FILE, reports)
            
    return True



def log_change_history(record_key, old_data, new_data, user_name):
    """Log change to history"""
    history = load_json_file(CHANGE_HISTORY_FILE)
    
    change_entry = {
        "timestamp": utils.get_now_kst_str(),
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
    
    
def get_user_activity_keys(user_name):
    """Get list of record keys that have been modified by this user"""
    statuses = load_json_file(ACTIVITY_STATUS_FILE)
    if not statuses: return []
    
    keys = []
    for k, v in statuses.items():
        if v.get('변경자') == user_name:
            keys.append(k)
            
    return keys



# ===== VIEW LOGGING =====

# VIEW_LOG_FILE moved to top

def log_view(user_role, user_name, target, details):
    """Log view/search activity"""
    logs = load_json_file(VIEW_LOG_FILE)
    
    log_entry = {
        "timestamp": utils.get_now_kst_str(),
        "user_role": user_role,
        "user_name": user_name,
        "target": target,
        "details": details
    }
    
    logs.append(log_entry)
    
    # Keep only last 2000 entries (views happen more often)
    if len(logs) > 2000:
        logs = logs[-2000:]
        
    save_json_file(VIEW_LOG_FILE, logs)

def get_view_logs(limit=100):
    """Get recent view logs"""
    logs = load_json_file(VIEW_LOG_FILE)
    return logs[-limit:] if logs else []


# ===== VISIT REPORTS (Text, Voice, Photo) =====

VISIT_REPORT_FILE = STORAGE_DIR / "visit_reports.json"
VISIT_MEDIA_DIR = STORAGE_DIR / "visits"
VISIT_MEDIA_DIR.mkdir(exist_ok=True)

# ===== ATOMIC TRANSACTIONS (REDESIGN) =====

def register_visit(record_key, content, audio_file, photo_files, user_info, forced_status=None):
    """
    ATOMIC OPERATION: Register a visit.
    - photo_files: list of up to 3 photo files or a single file
    """
    try:
        from src import utils
        import io
        
        # 1. Save Media
        audio_path = None
        photo_paths = [None, None, None]
        
        # [FIX] Force KST Timezone
        ts_str = utils.get_now_kst_str()
        
        from dateutil import parser
        try:
            timestamp_kst = parser.parse(ts_str)
            file_prefix = f"{timestamp_kst.strftime('%Y%m%d_%H%M%S')}_{user_info.get('name', 'unknown')}"
        except Exception:
            file_prefix = f"visit_{user_info.get('name', 'unknown')}"
        
        if audio_file:
            ext = audio_file.name.split('.')[-1] if '.' in audio_file.name else "wav"
            fname = f"{file_prefix}_audio.{ext}"
            save_path = VISIT_MEDIA_DIR / fname
            with open(save_path, "wb") as f:
                f.write(audio_file.getvalue())
            
            drive_link = upload_to_gdrive(save_path, fname)
            audio_path = drive_link if drive_link else str(fname)
            
        if photo_files:
            # Handle both single file and list
            if not isinstance(photo_files, list):
                photo_files = [photo_files]
                
            for i, photo_file in enumerate(photo_files[:3]):
                if not photo_file: continue
                
                # Resize image (Small size as requested)
                resized_data = resize_image(photo_file)
                
                fname = f"{file_prefix}_photo_{i+1}.jpg"
                save_path = VISIT_MEDIA_DIR / fname
                
                with open(save_path, "wb") as f:
                    f.write(resized_data)
                
                drive_link = upload_to_gdrive(save_path, fname)
                photo_paths[i] = drive_link if drive_link else str(fname)

        # 2. Determine New Status
        new_status = forced_status if forced_status else ACTIVITY_STATUS_MAP["방문"]
        new_status = normalize_status(new_status)

        # 3. Create Visit Report Entry
        id_str = ts_str.replace("-", "").replace(" ", "_").replace(":", "").replace("+", "_")
        visit_entry = {
            "id": f"rep_{id_str}_{record_key[:5]}",
            "timestamp": ts_str,
            "record_key": record_key,
            "content": content,
            "audio_path": audio_path,
            "photo_path": photo_paths[0], # Legacy support
            "photo_path1": photo_paths[0],
            "photo_path2": photo_paths[1],
            "photo_path3": photo_paths[2],
            "user_name": user_info.get("name"),
            "user_role": user_info.get("role"),
            "user_branch": user_info.get("branch"),
            "resulting_status": new_status
        }
        
        # 4. Update Status Entry (Latest status overview)
        status_entry = {
            "활동진행상태": new_status,
            "특이사항": content[:150], # Summary
            "변경일시": ts_str,
            "변경자": user_info.get("name"),
            "photo_path1": photo_paths[0],
            "photo_path2": photo_paths[1],
            "photo_path3": photo_paths[2]
        }
        
        # 5. EXECUTE WRITES (Sequential)
        
        # A. Reports
        reports = load_json_file(VISIT_REPORT_FILE)
        reports.append(visit_entry)
        save_json_file(VISIT_REPORT_FILE, reports)
        
        # B. Status & History
        statuses = load_json_file(ACTIVITY_STATUS_FILE)
        old_data = statuses.get(record_key, {})
        statuses[record_key] = status_entry
        save_json_file(ACTIVITY_STATUS_FILE, statuses)
        
        # Log History if changed
        if old_data.get("활동진행상태") != new_status or old_data.get("특이사항") != content:
            log_change_history(record_key, old_data, status_entry, user_info.get("name"))

        
        return True, "저장 완료"
        
    except Exception as e:
        print(f"CRITICAL ERROR in register_visit: {e}")
        return False, str(e)

def register_visit_batch(batch_list):
    """
    BATCH OPERATION: Register multiple visits efficiently.
    - batch_list: list of dicts {record_key, content, user_info, forced_status}
    
    1. Load all files once
    2. Process updates in memory
    3. Save files once
    """
    if not batch_list:
        return True, "No changes"
        
    try:
        # 1. Load data
        reports = load_json_file(VISIT_REPORT_FILE)
        if not isinstance(reports, list): reports = []
        
        from src import utils
        from dateutil import parser
        statuses = load_json_file(ACTIVITY_STATUS_FILE)
        
        ts_str = utils.get_now_kst_str()
        try:
            timestamp_kst_dt = parser.parse(ts_str)
            timestamp_float = timestamp_kst_dt.timestamp()
        except Exception:
            timestamp_float = 0.0
        
        # 2. Process changes
        for item in batch_list:
            record_key = item['record_key']
            content = item['content']
            user_info = item['user_info']
            forced_status = item.get('forced_status')
            
            # Determine Status
            new_status = forced_status if forced_status else ACTIVITY_STATUS_MAP["방문"]
            new_status = normalize_status(new_status)
            
            # Create Report Entry
            visit_entry = {
                "id": f"rep_{timestamp_float}_{item.get('record_key', 'unk')[:5]}",
                "timestamp": ts_str,
                "record_key": record_key,
                "content": content,
                "audio_path": None,
                "photo_path": None,
                "photo_path1": None,
                "photo_path2": None,
                "photo_path3": None,
                "user_name": user_info.get("name"),
                "user_role": user_info.get("role"),
                "user_branch": user_info.get("branch"),
                "resulting_status": new_status
            }

            reports.append(visit_entry)
            
            # 3. Update activity status (Latest status)
            old_status_data = statuses.get(record_key, {})
            
            new_status_data = {
                "활동진행상태": new_status,
                "특이사항": content[:100] + "..." if len(content) > 100 else content,
                "변경일시": ts_str,
                "변경자": user_info.get("name"),
                "photo_path1": visit_entry.get("photo_path1"),
                "photo_path2": visit_entry.get("photo_path2"),
                "photo_path3": visit_entry.get("photo_path3")
            }
            
            statuses[record_key] = new_status_data
            
            # Log History if changed
            if old_status_data.get("활동진행상태") != new_status or \
               old_status_data.get("특이사항") != content:
                log_change_history(record_key, old_status_data, new_status_data, user_info.get("name"))
                
        # 3. Save files
        save_json_file(VISIT_REPORT_FILE, reports)
        save_json_file(ACTIVITY_STATUS_FILE, statuses)
        
        return True, f"{len(batch_list)}건 저장 완료"
        
    except Exception as e:
        print(f"CRITICAL ERROR in register_visit_batch: {e}")
        return False, str(e)

def update_visit_report(report_id, new_content=None, new_photo_files=None, deleted_photo_indices=None):
    """
    Update an existing visit report.
    - report_id: ID of the report to update
    - new_content: New text content (optional)
    - new_photo_files: List of Streamlit UploadedFiles (optional)
    - deleted_photo_indices: List of indices (0, 1, 2) to clear
    """
    try:
        reports = load_json_file(VISIT_REPORT_FILE)
        target_idx = next((i for i, r in enumerate(reports) if r.get("id") == report_id), -1)
        
        if target_idx == -1:
            return False, "리포트를 찾을 수 없습니다."
            
        report = reports[target_idx]
        
        # 1. Update Content
        if new_content is not None:
            report['content'] = new_content
            
        # 2. Handle Deletions
        if deleted_photo_indices:
            for idx in deleted_photo_indices:
                p_key = f"photo_path{idx+1}"
                report[p_key] = None
                if idx == 0:
                    report['photo_path'] = None
            
        # 3. Update/Add Photos
        if new_photo_files:
            # Handle single file or list
            if not isinstance(new_photo_files, list):
                new_photo_files = [new_photo_files]
                
            from src import utils
            from dateutil import parser
            ts_str = utils.get_now_kst_str()
            try:
                timestamp_kst = parser.parse(ts_str)
                file_prefix = f"{timestamp_kst.strftime('%Y%m%d_%H%M%S')}_upd"
            except Exception:
                file_prefix = "upd"
            
            # Find empty slots or overwrite starting from first empty
            photo_slots = ["photo_path1", "photo_path2", "photo_path3"]
            uploaded_count = 0
            
            for slot in photo_slots:
                if uploaded_count >= len(new_photo_files):
                    break
                    
                # If slot is empty, fill it. If not, only overwrite if we are forced?
                # For simplicity here: find first None slot or just append to end?
                # Realistically, if user provides new files, they usually want to ADD them to empty slots.
                if not report.get(slot):
                    photo_file = new_photo_files[uploaded_count]
                    if not photo_file: continue
                    
                    resized_data = resize_image(photo_file)
                    idx_num = slot[-1]
                    fname = f"{file_prefix}_{report_id[-5:]}_{idx_num}.jpg"
                    save_path = VISIT_MEDIA_DIR / fname
                    
                    with open(save_path, "wb") as f:
                        f.write(resized_data)
                    
                    drive_link = upload_to_gdrive(save_path, fname)
                    report[slot] = drive_link if drive_link else str(fname)
                    if slot == "photo_path1":
                        report["photo_path"] = report[slot]
                        
                    uploaded_count += 1

            # If all slots were full but we still have files, we could overwrite, 
            # but usually user deletes first then adds.
            
        # Ensure consistency for old single-path display
        if not report.get('photo_path') and report.get('photo_path1'):
            report['photo_path'] = report['photo_path1']
            
        # Prepare for save
        reports[target_idx] = report
        save_json_file(VISIT_REPORT_FILE, reports)
        
        return True, "수정 완료"
        
    except Exception as e:
        print(f"ERROR in update_visit_report: {e}")
        return False, str(e)


def delete_visit_report(report_id):
    """지정된 ID의 방문/활동 이력을 삭제합니다."""
    reports = load_json_file(VISIT_REPORT_FILE)
    if not isinstance(reports, list): return False, "No data found."
    
    new_reports = [r for r in reports if r.get("id") != report_id]
    
    if len(new_reports) == len(reports):
        return False, "Report not found."
        
    save_json_file(VISIT_REPORT_FILE, new_reports)
    return True, "Deleted successfully."

# Read Methods
def get_visit_reports(record_key=None, user_name=None, user_branch=None, limit=100):
    reports = load_json_file(VISIT_REPORT_FILE)
    if not isinstance(reports, list): reports = []
    
    # [FIX] Ensure all reports have an 'id' (KeyError protection)
    id_fixed = False
    for r in reports:
        if 'id' not in r:
            # Generate a stable-ish ID based on timestamp and record_key
            ts = r.get('timestamp', '00000000')
            rk = r.get('record_key', 'unk')
            r['id'] = f"rep_fix_{ts}_{rk[:5]}".replace(" ", "_").replace(":", "").replace("-", "")
            id_fixed = True
    
    # [NEW] Persist fixed IDs so deletion can find them
    if id_fixed:
        save_json_file(VISIT_REPORT_FILE, reports)

    if record_key:
        reports = [r for r in reports if r.get("record_key") == record_key]
    if user_name:
        reports = [r for r in reports if r.get("user_name") == user_name]
    if user_branch:
        reports = [r for r in reports if r.get("user_branch") == user_branch]
        
    reports.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return reports[:limit]

def get_media_path(filename):
    # Ensure filename is a valid non-empty string to prevent Path join errors (e.g. with NaN)
    if not isinstance(filename, str) or not filename.strip() or filename.lower() == "nan":
        return None
        
    # [NEW] If it's already a URL (e.g. GDrive link), return as is
    if filename.startswith("http"):
        return filename
        
    return str(VISIT_MEDIA_DIR / filename)
