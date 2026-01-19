import streamlit as st
import pandas as pd
import altair as alt
import os
import glob
import unicodedata
import streamlit.components.v1 as components
from datetime import datetime

# Import modularized components
from src import utils
from src import data_loader
from src import map_visualizer

# --- Configuration & Theme ---
st.set_page_config(
    page_title="영업기회 관리 시스템",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# [FIX] Force Streamlit Native Theme for Altair (High Contrast)
try:
    alt.themes.enable('streamlit')
except:
    pass # fallback

# Custom CSS for Premium & Mobile Feel
st.markdown("""
<style>
    /* Global Font & Colors */
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Pretendard', sans-serif;
    }
    
    /* Main Container Padding */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 3rem;
    }

    /* Metrics Styling */
    .metric-card {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        text-align: center;
        border: 1px solid #e0e0e0;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #666;
        margin-bottom: 5px;
    }
    .metric-value {
        font-size: 1.6rem;
        font-weight: 700;
        color: #2c3e50;
    }
    .metric-sub {
        font-size: 0.8rem;
        color: #4CAF50;
    }

    /* Small Dashboard Card */
    .small-card {
        background-color: #f8f9fa;
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 10px;
        text-align: center;
        margin-bottom: 5px;
    }
    .small-card-title { font-size: 0.85rem; color: #555 !important; font-weight: 600; margin-bottom: 2px; }
    .small-card-value { font-size: 1.1rem; color: #333 !important; font-weight: 700; }
    .small-card-active { color: #2E7D32 !important; font-size: 0.8rem; }
    
    /* Ensure text visibility on forced white backgrounds */
    .metric-label { color: #555 !important; }
    .metric-value { color: #333 !important; }

    /* Mobile Card Styling */
    .card-container {
        background-color: white;
        padding: 16px;
        border-radius: 12px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        margin-bottom: 16px;
        border-left: 5px solid #2E7D32;
        transition: transform 0.2s;
    }
    .card-container:active {
        transform: scale(0.98);
    }
    .card-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #1a1a1a;
        margin-bottom: 4px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .card-badges {
        display: flex;
        gap: 5px;
    }
    .status-badge {
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .status-open { background-color: #e8f5e9; color: #2e7d32; }
    .status-closed { background-color: #ffebee; color: #c62828; }
    
    .card-meta {
        font-size: 0.85rem;
        color: #555;
        margin-bottom: 8px;
    }
    .card-address {
        font-size: 0.85rem;
        color: #777;
        margin-bottom: 12px;
        display: flex;
        align-items: start;
        gap: 5px;
    }
    
    /* Action Buttons Area */
    .card-actions {
        display: flex;
        gap: 10px;
        margin-top: 10px;
        border-top: 1px solid #eee;
        padding-top: 10px;
    }
    
    /* Tabs Customization */
    .stTabs [data-baseweb="tab-list"] {
        gap: 20px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 4px 4px 0 0;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: transparent;
        border-bottom: 2px solid #2E7D32;
        color: #2E7D32;
    }
</style>
""", unsafe_allow_html=True)

# State Update Callbacks
def update_branch_state(name):
    # [FIX] Force NFC to match selectbox options strictly
    normalized_name = unicodedata.normalize('NFC', name)
    st.session_state.sb_branch = normalized_name
    st.session_state.sb_manager = "전체"
    st.session_state.dash_branch = normalized_name
    
def update_manager_state(name):
    st.session_state.sb_manager = name

def update_branch_with_status(name, status):
    st.session_state.sb_branch = name
    st.session_state.sb_manager = "전체"
    st.session_state.dash_branch = name
    st.session_state.sb_status = status
    
def update_manager_with_status(name, status):
    st.session_state.sb_manager = name
    st.session_state.sb_status = status

# --- Sidebar Filters ---
with st.sidebar:
    st.header("⚙️ 설정 & 데이터")
    
    st.sidebar.markdown("---")
    with st.sidebar.expander("📂 데이터 소스 및 API 설정", expanded=False):
        st.subheader("데이터 소스 선택")
        
        data_source = st.radio(
            "데이터 출처", 
            ["파일 업로드 (File)", "OpenAPI 연동 (Auto)"],
            index=0
        )
        
        # [FIX] Enhanced File Selection with 20260119 Priority
        local_zips = sorted(glob.glob(os.path.join("data", "*.zip")), key=os.path.getmtime, reverse=True)
        local_excels = sorted(glob.glob(os.path.join("data", "*.xlsx")), key=os.path.getmtime, reverse=True)
        
        # Force Priority for 20260119
        priority_file_match = [f for f in local_excels if '20260119' in f]
        if priority_file_match:
            # Move to front
            for p in priority_file_match:
                if p in local_excels: local_excels.remove(p)
            local_excels = priority_file_match + local_excels
            
        uploaded_dist = None
        use_local_dist = False

        if local_excels:
            use_local_dist = st.toggle("영업구역(Excel) 자동 로드", value=True)
            if use_local_dist:
                # Let user choose if multiple
                file_opts = [os.path.basename(f) for f in local_excels]
                sel_file_idx = 0
                
                # Try to default to the 20260119 one if present in opts
                for i, fname in enumerate(file_opts):
                    if '20260119' in fname:
                        sel_file_idx = i
                        break
                        
                sel_file = st.selectbox("사용할 영업구역 파일", file_opts, index=sel_file_idx)
                uploaded_dist = os.path.join("data", sel_file)
                
                if '20260119' in sel_file:
                     st.success(f"✅ **[최신]** 로드된 파일: {sel_file}")
                else:
                     st.warning(f"⚠️ 로드된 파일: {sel_file} (20260119 파일 권장)")
        
        if not use_local_dist:
            uploaded_dist = st.file_uploader("영업구역 데이터 (Excel)", type="xlsx", key="dist_uploader")

        uploaded_zip = None
        
        if data_source == "파일 업로드 (File)":
             if local_zips:
                 use_local_zip = st.toggle("인허가(Zip) 자동 로드", value=True)
                 if use_local_zip:
                     # Let user choose zip if multiple
                     zip_opts = [os.path.basename(f) for f in local_zips]
                     sel_zip = st.selectbox("사용할 인허가 파일 (ZIP)", zip_opts, index=0)
                     uploaded_zip = os.path.join("data", sel_zip)
                     st.caption(f"ZIP: {sel_zip}")
                 else:
                     uploaded_zip = st.file_uploader("인허가 데이터 (ZIP)", type="zip")
             else:
                  uploaded_zip = st.file_uploader("인허가 데이터 (ZIP)", type="zip")
                 
        else: # OpenAPI
            st.info("🌐 지방행정 인허가 데이터 (LocalData)")
            
            default_auth_key = ""
            key_file_path = os.path.join(os.path.dirname(__file__), "오픈API", "api_key.txt")
            if os.path.exists(key_file_path):
                 try:
                     with open(key_file_path, "r", encoding="utf-8") as f:
                         default_auth_key = f.read().strip()
                 except: pass
                     
            api_auth_key = st.text_input("인증키 (AuthKey)", value=default_auth_key, type="password", help="공공데이터포털(data.go.kr)에서 발급받은 인증키")
            api_local_code = st.text_input("지역코드 (LocalCode)", value="3220000", help="예: 3220000 (강남구)")
            
            c_d1, c_d2 = st.columns(2)
            today = datetime.date.today()
            api_start_date = c_d1.date_input("시작일", value=today - datetime.timedelta(days=30))
            api_end_date = c_d2.date_input("종료일", value=today)
            
            fetch_btn = st.button("데이터 가져오기 (Fetch)")
            
            if fetch_btn and api_auth_key:
                with st.spinner("🌐 API 데이터 조회 중..."):
                    s_date = api_start_date.strftime("%Y%m%d")
                    e_date = api_end_date.strftime("%Y%m%d")
                    api_df, api_error = data_loader.fetch_openapi_data(api_auth_key, api_local_code, s_date, e_date)
                    
                    if api_error:
                        st.error(f"실패: {api_error}")
                    else:
                        st.success(f"성공! {len(api_df)}개 데이터 수신 완료")
                        st.session_state['api_fetched_df'] = api_df
            
            if 'api_fetched_df' in st.session_state:
                api_df = st.session_state['api_fetched_df']
                st.caption(f"✅ 수신된 데이터: {len(api_df)}건")




    with st.sidebar.expander("🎨 테마 설정", expanded=False):
        theme_mode = st.selectbox(
            "스타일 테마 선택", 
            ["기본 (Default)", "모던 다크 (Modern Dark)", "웜 페이퍼 (Warm Paper)", "고대비 (High Contrast)", "코퍼레이트 블루 (Corporate Blue)"],
            index=0,
            label_visibility="collapsed"
        )

    def apply_theme(theme):
        css = ""
        if theme == "모던 다크 (Modern Dark)":
            css = """
            <style>
                [data-testid="stAppViewContainer"] { background-color: #1E1E1E; color: #E0E0E0; }
                [data-testid="stSidebar"] { background-color: #252526; border-right: 1px solid #333; }
                [data-testid="stHeader"] { background-color: rgba(30,30,30,0.9); }
                .stMarkdown, .stText, h1, h2, h3, h4, h5, h6 { color: #E0E0E0 !important; }
                .stDataFrame { border: 1px solid #444; }
                div[data-testid="metric-container"] { background-color: #333333; border: 1px solid #444; color: #fff; padding: 10px; border-radius: 8px; }
            </style>
            """
        elif theme == "웜 페이퍼 (Warm Paper)":
            css = """
            <style>
                [data-testid="stAppViewContainer"] { background-color: #F5F5DC; color: #4A403A; }
                [data-testid="stSidebar"] { background-color: #E8E4D9; border-right: 1px solid #D8D4C9; }
                .stMarkdown, .stText, h1, h2, h3, h4, h5, h6 { color: #5C4033 !important; font-family: 'Georgia', serif; }
                div[data-testid="metric-container"] { background-color: #FFF8E7; border: 1px solid #D2B48C; color: #5C4033; padding: 10px; border-radius: 4px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
                .stButton button { background-color: #D2B48C !important; color: #fff !important; border-radius: 0px; }
            </style>
            """
        elif theme == "고대비 (High Contrast)":
            css = """
            <style>
                [data-testid="stAppViewContainer"] { background-color: #FFFFFF; color: #000000; }
                [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 2px solid #000000; }
                .stMarkdown, .stText, h1, h2, h3, h4, h5, h6 { color: #000000 !important; font-weight: 900 !important; }
                div[data-testid="metric-container"] { background-color: #FFFFFF; border: 2px solid #000000; color: #000000; padding: 15px; border-radius: 0px; }
                .stButton button { background-color: #000000 !important; color: #FFFFFF !important; border: 2px solid #000000; font-weight: bold; }
            </style>
            """
        elif theme == "코퍼레이트 블루 (Corporate Blue)":
            css = """
            <style>
                [data-testid="stAppViewContainer"] { background-color: #F0F4F8; color: #243B53; }
                [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #BCCCDC; }
                h1, h2, h3 { color: #102A43 !important; }
                div[data-testid="metric-container"] { background-color: #FFFFFF; border-left: 5px solid #334E68; box-shadow: 0 4px 6px rgba(0,0,0,0.1); padding: 15px; border-radius: 4px; }
                .stButton button { background-color: #334E68 !important; color: white !important; border-radius: 4px; }
            </style>
            """
        else: # Default
            css = """
            <style>
                /* Global Font & Background */
                @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@300;400;500;600;700&display=swap');
                
                html, body, [class*="css"] {
                    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif;
                }
                
                [data-testid="stAppViewContainer"] { 
                    background-color: #F8F9FA; 
                    color: #343A40; 
                }
                
                [data-testid="stSidebar"] { 
                    background-color: #FFFFFF; 
                    border-right: 1px solid #DEE2E6; 
                    box-shadow: 2px 0 12px rgba(0,0,0,0.03);
                }
                
                /* Headers */
                h1, h2, h3 { color: #212529 !important; font-weight: 700 !important; letter-spacing: -0.5px; }
                h4, h5, h6 { color: #495057 !important; font-weight: 600 !important; }
                
                /* Sidebar Headers & Text */
                [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
                     color: #212529 !important;
                }
                [data-testid="stSidebar"] .stMarkdown p {
                    color: #495057 !important;
                    font-size: 0.95rem;
                }
                
                /* Improved Visibility for Global Filters Section */
                /* We can't target specifically by ID easily in Streamlit, but we can style inputs */
                [data-testid="stSidebar"] .stSelectbox label, 
                [data-testid="stSidebar"] .stMultiSelect label,
                [data-testid="stSidebar"] .stTextInput label {
                    color: #343A40 !important;
                    font-weight: 600 !important;
                }
                
                /* Buttons */
                .stButton button { 
                    background-color: #228BE6 !important; 
                    color: #fff !important; 
                    border: none;
                    border-radius: 6px;
                    font-weight: 500;
                    transition: all 0.2s;
                }
                .stButton button:hover {
                    background-color: #1C7ED6 !important;
                    box-shadow: 0 4px 12px rgba(34, 139, 230, 0.3);
                    transform: translateY(-1px);
                }
                
                /* Metric Cards */
                div[data-testid="metric-container"] { 
                    background-color: #FFFFFF; 
                    border: 1px solid #E9ECEF; 
                    color: #495057; 
                    padding: 16px; 
                    border-radius: 12px; 
                    box-shadow: 0 4px 20px rgba(0,0,0,0.04); 
                    transition: transform 0.2s;
                }
                div[data-testid="metric-container"]:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 8px 24px rgba(0,0,0,0.08);
                }
                
                /* Expander */
                .streamlit-expanderHeader {
                    background-color: #FFFFFF;
                    border-radius: 8px;
                    border: 1px solid #E9ECEF;
                    color: #343A40;
                    font-weight: 600;
                }
                
                /* Dataframe */
                .stDataFrame {
                    border: 1px solid #DEE2E6;
                    border-radius: 8px;
                }
                
                /* Custom Highlight for Admin Section if it has a specific wrapper (Simulated) */
                hr { margin: 2rem 0; border-color: #DEE2E6; }
            </style>
            """
        st.markdown(css, unsafe_allow_html=True)

    apply_theme(theme_mode)
    
    st.sidebar.markdown("---")

    with st.sidebar.expander("🔑 카카오 지도 설정", expanded=False):
        st.warning("카카오 자바스크립트 키 필요")
        kakao_key = st.text_input("키 입력", type="password", key="kakao_api_key_v2")
        if kakao_key: kakao_key = kakao_key.strip()
        
        if kakao_key:
            st.success("✅ 활성화됨")
        else:
            st.caption("미입력 시: 기본 지도 사용")
        


# --- Main Logic ---

st.title("💼 영업기회 파이프라인")

raw_df = None
error = None

if uploaded_dist:
    if data_source == "파일 업로드 (File)" and uploaded_zip:
        with st.spinner("🚀 파일 분석 및 매칭중..."):
             raw_df, error = data_loader.load_and_process_data(uploaded_zip, uploaded_dist)
             
    elif data_source == "OpenAPI 연동 (Auto)" and api_df is not None:
        with st.spinner("🌐 API 데이터 매칭중..."):
             raw_df, error = data_loader.process_api_data(api_df, uploaded_dist)

if error:
    st.error(f"오류 발생: {error}")

if raw_df is not None:
    
    # [FIX] Global NFC Normalization to prevent Mac/Windows mismatch
    # This ensures all subsequent filters and buttons work with consistent strings.
    for col in ['관리지사', 'SP담당', '사업장명', '소재지전체주소', '영업상태명', '업태구분명']:
        if col in raw_df.columns:
            # [FIX] NFC + Strip to ensure exact matching
            raw_df[col] = raw_df[col].astype(str).apply(lambda x: unicodedata.normalize('NFC', x).strip() if x else x)
            
    # [REFACTOR] Centralized Branch List Calculation
    # Calculate ONCE, use EVERYWHERE
    custom_branch_order = ['중앙지사', '강북지사', '서대문지사', '고양지사', '의정부지사', '남양주지사', '강릉지사', '원주지사']
    custom_branch_order = [unicodedata.normalize('NFC', b) for b in custom_branch_order]
    
    current_branches_raw = [unicodedata.normalize('NFC', str(b)) for b in raw_df['관리지사'].unique() if pd.notna(b)]
    
    # Intersection while preserving order
    global_branch_opts = [b for b in custom_branch_order if b in current_branches_raw]
    others = [b for b in current_branches_raw if b not in custom_branch_order]
    global_branch_opts.extend(others)
    
    # --- Apply Global Filters (Sidebar) ---
    # --- Sidebar Filters ---
    with st.sidebar:
        st.header("⚙️ 설정")
        
        # [SECURITY] Session-based Admin Auth
        if 'admin_auth' not in st.session_state:
            st.session_state.admin_auth = False
            
        # [FIX] Initialize variables globally to prevent NameError
        edit_mode = False
        custom_view_mode = False
            
        c_mode1, c_mode2 = st.columns(2)
        
        
        # [UX] Admin Settings Toggle (Replaces simple login toggle)
        show_admin_settings = st.checkbox("⚙️ 관리자 설정 (필터 열기)", value=False)
        
        # Auth Logic Triggered by Checkbox
        if show_admin_settings:
            if not st.session_state.admin_auth:
                st.info("관리자 암호를 입력하세요.")
                admin_pw = st.text_input("암호", type="password", key="admin_pw_input", label_visibility="collapsed")
                if st.button("확인", key="admin_login_btn"):
                    if admin_pw == "admin1234":
                        st.session_state.admin_auth = True
                        st.rerun()
                    else:
                        st.error("암호 오류")
            else:
                # Logged In UI
                st.success("✅ 관리자 모드 활성")
                
                c_edit, c_view = st.columns(2)
                with c_edit:
                    edit_mode = st.toggle("🛠️ 수정 모드", value=False)
                with c_view:
                    custom_view_mode = st.toggle("👮 관리자 뷰", value=False)
                    
                if st.button("로그아웃 (잠금)", key="admin_logout_btn"):
                    st.session_state.admin_auth = False
                    st.rerun()
        else:
            # If checkbox is OFF, force auth off (or just hide controls)?
            # User expectation: "Button select -> Global Filter appear".
            # So if unchecked, filters are hidden. Auth state can persist or not, but visibility is off.
            pass

        # [FEATURE] Custom Dashboard View Controls (Only if auth)
        custom_view_managers = []
        if custom_view_mode and st.session_state.admin_auth:
            st.info("👮 대시보드 강제 지정 모드")
            all_mgrs_raw = sorted(raw_df['SP담당'].dropna().unique())
            custom_view_managers = st.multiselect(
                "노출할 담당자 지정 (복수)", 
                all_mgrs_raw,
                placeholder="담당자 선택..."
            )
            all_branches_raw = sorted(raw_df['관리지사'].dropna().unique())
            exclude_branches = st.multiselect(
                "제외할 지사 지정 (복수)",
                all_branches_raw,
                placeholder="제외할 지사 선택..."
            )
        
        st.divider()
        
        # [FIX] Initialize filter variables globally (Default: All)
        sel_branch = "전체"
        sel_manager = "전체"
        sel_manager_label = "전체"
        sel_types = []
        selected_area_code = None
        only_hospitals = False
        only_large_area = False
        type_col = '업태구분명' if '업태구분명' in raw_df.columns else raw_df.columns[0]
        
        # [FIX] Additional missing initializations
        sel_permit_ym = "전체"
        sel_close_ym = "전체"
        sel_status = "전체"
        only_with_phone = False
        
        filter_df = raw_df.copy()
        
        # [UI] Common Filters Logic
        # ONLY show if 'show_admin_settings' is Checked AND 'admin_auth' is True
        if show_admin_settings and st.session_state.admin_auth:
            st.markdown("---")
            st.markdown("### 🔍 공통 필터 설정")
            
            # 1. Branch
            custom_branch_order = ['중앙지사', '강북지사', '서대문지사', '고양지사', '의정부지사', '남양주지사', '강릉지사', '원주지사']
            custom_branch_order = [unicodedata.normalize('NFC', b) for b in custom_branch_order]
            current_branches_in_raw = [unicodedata.normalize('NFC', str(b)) for b in raw_df['관리지사'].unique() if pd.notna(b)]
            sorted_branches_for_filter = [b for b in custom_branch_order if b in current_branches_in_raw]
            others_for_filter = [b for b in current_branches_in_raw if b not in custom_branch_order]
            sorted_branches_for_filter.extend(others_for_filter)
            sorted_branches_for_filter = [unicodedata.normalize('NFC', b) for b in sorted_branches_for_filter]

            st.markdown("##### 🏢 지사 선택")
            branch_opts = ["전체"] + sorted_branches_for_filter
            if 'sb_branch' not in st.session_state: st.session_state.sb_branch = "전체"
            
            if st.session_state.sb_branch != "전체":
                 st.session_state.sb_branch = unicodedata.normalize('NFC', st.session_state.sb_branch)
            
            def reset_manager_filter():
                st.session_state.sb_manager = "전체"
                
            sel_branch = st.selectbox(
                "관리지사", 
                branch_opts, 
                key="sb_branch",
                on_change=reset_manager_filter
            )

            if sel_branch != "전체":
                filter_df = filter_df[filter_df['관리지사'] == sel_branch]
            
            # 2. Manager
            has_area_code = '영업구역 수정' in filter_df.columns
            
            if has_area_code:
                st.markdown("##### 🧑‍💻 영업구역 (담당자) 선택")
                temp_df = filter_df[['영업구역 수정', 'SP담당']].dropna(subset=['영업구역 수정']).copy()
                temp_df['label'] = temp_df['영업구역 수정'].astype(str) + " (" + temp_df['SP담당'].astype(str) + ")"
                temp_df = temp_df.sort_values('영업구역 수정')
                manager_opts = ["전체"] + list(temp_df['label'].unique())
                label_to_code = dict(zip(temp_df['label'], temp_df['영업구역 수정']))
            else:
                st.markdown("##### 🧑‍💻 담당자 선택")
                manager_opts = ["전체"] + sorted(list(filter_df['SP담당'].dropna().unique()))
                
            if 'sb_manager' not in st.session_state: st.session_state.sb_manager = "전체"
            
            sel_manager_label = st.selectbox(
                "영업구역/담당", 
                manager_opts, 
                index=manager_opts.index(st.session_state.get('sb_manager', "전체")) if st.session_state.get('sb_manager') in manager_opts else 0,
                key="sb_manager"
            )
            
            sel_manager = "전체" 
            selected_area_code = None 
            
            if sel_manager_label != "전체":
                if has_area_code:
                    selected_area_code = label_to_code.get(sel_manager_label)
                    if selected_area_code:
                        filter_df = filter_df[filter_df['영업구역 수정'] == selected_area_code]
                        sel_manager = filter_df['SP담당'].iloc[0] if not filter_df.empty else "전체"
                else:
                    filter_df = filter_df[filter_df['SP담당'] == sel_manager_label]
                    sel_manager = sel_manager_label

            if sel_manager != "전체":
                sel_manager = unicodedata.normalize('NFC', sel_manager)
                
            # 3. Type
            st.markdown("##### 🏥 병원/의원 필터")
            c_h1, c_h2 = st.columns(2)
            with c_h1:
                 only_hospitals = st.toggle("🏥 병원 관련만 보기", value=False)
            with c_h2:
                 only_large_area = st.toggle("🏗️ 100평 이상만 보기", value=False)
            
            try:
                available_types = sorted(list(filter_df[type_col].dropna().unique()))
            except:
                available_types = []
                
            if not available_types and not filter_df.empty:
                 available_types = sorted(list(raw_df[type_col].dropna().unique()))
                 
            with st.expander("📂 업태(업종) 필터 (펼치기/접기)", expanded=False):
                sel_types = st.multiselect(
                    "업태를 선택하세요 (복수 선택 가능)", 
                    available_types,
                    placeholder="전체 선택 (비어있으면 전체)",
                    label_visibility="collapsed"
                )
            
            # 4. Date
            st.markdown("##### 📅 날짜 필터 (연-월)")

            def get_ym_options(column):
                if column not in raw_df.columns: return []
                dates = raw_df[column].dropna()
                if dates.empty: return []
                return sorted(dates.dt.strftime('%Y-%m').unique(), reverse=True)

            permit_ym_opts = ["전체"] + get_ym_options('인허가일자')
            if 'sb_permit_ym' not in st.session_state: st.session_state.sb_permit_ym = "전체"
            sel_permit_ym = st.selectbox(
                "인허가일자 (월별)", 
                permit_ym_opts,
                index=permit_ym_opts.index(st.session_state.get('sb_permit_ym', "전체")) if st.session_state.get('sb_permit_ym') in permit_ym_opts else 0,
                key="sb_permit_ym"
            )
            
            close_ym_opts = ["전체"] + get_ym_options('폐업일자')
            if 'sb_close_ym' not in st.session_state: st.session_state.sb_close_ym = "전체"
            sel_close_ym = st.selectbox(
                "폐업일자 (월별)", 
                close_ym_opts,
                index=close_ym_opts.index(st.session_state.get('sb_close_ym', "전체")) if st.session_state.get('sb_close_ym') in close_ym_opts else 0,
                key="sb_close_ym"
            )
            
            # 5. Status
            st.markdown("##### 영업상태")
            status_opts = ["전체"] + sorted(list(raw_df['영업상태명'].unique()))
            
            if 'sb_status' not in st.session_state: st.session_state.sb_status = "전체"
            
            sel_status = st.selectbox(
                "영업상태", 
                status_opts, 
                index=status_opts.index(st.session_state.get('sb_status', "전체")) if st.session_state.get('sb_status') in status_opts else 0,
                key="sb_status"
            )
            
            st.markdown("##### 📞 전화번호 필터")
            only_with_phone = st.toggle("전화번호 있는 것만 보기", value=False)
            
            st.markdown("---")
        
    # Data Filtering
    base_df = raw_df.copy()
    base_df = base_df[base_df['관리지사'] != '미지정']
    
    # [FEATURE] Admin Custom Dashboard Override
    if custom_view_mode and admin_auth and (custom_view_managers or exclude_branches):
        if custom_view_managers:
            base_df = base_df[base_df['SP담당'].isin(custom_view_managers)]
            
        if exclude_branches:
            base_df = base_df[~base_df['관리지사'].isin(exclude_branches)]
            
        msg = "👮 관리자 지정 뷰: "
        if custom_view_managers: msg += f"담당자 {len(custom_view_managers)}명 포함"
        if custom_view_managers and exclude_branches: msg += " & "
        if exclude_branches: msg += f"지사 {len(exclude_branches)}곳 제외"
        st.toast(msg)
        
    else:
        # Standard Sidebar Filters
        # [FIX] Source of Truth is Session State (for Immediate Button Response)
        current_branch_filter = st.session_state.get('sb_branch', "전체")
        
        if current_branch_filter != "전체":
            # [FIX] Normalize comparison for Mac/Excel compatibility
            norm_sel_branch = unicodedata.normalize('NFC', current_branch_filter)
            base_df = base_df[base_df['관리지사'] == norm_sel_branch]
            
        if selected_area_code:
            base_df = base_df[base_df['영업구역 수정'] == selected_area_code]
        elif sel_manager != "전체": 
            norm_sel_manager = unicodedata.normalize('NFC', sel_manager)
            base_df = base_df[base_df['SP담당'] == norm_sel_manager]
            
    # Common Filters (Applied to both modes)
    if only_hospitals:
        mask = base_df[type_col].astype(str).str.contains('병원|의원', na=False)
        if '개방서비스명' in base_df.columns:
            mask = mask | base_df['개방서비스명'].astype(str).str.contains('병원|의원', na=False)
        base_df = base_df[mask]
        
    if only_large_area:
        if '소재지면적' in base_df.columns:
             base_df['temp_area'] = pd.to_numeric(base_df['소재지면적'], errors='coerce').fillna(0)
             base_df = base_df[base_df['temp_area'] >= 330.58]
    
    if sel_types:
        base_df = base_df[base_df[type_col].isin(sel_types)]
        
    if sel_permit_ym != "전체":
        base_df = base_df[base_df['인허가일자'].dt.strftime('%Y-%m') == sel_permit_ym]
        
    if sel_close_ym != "전체":
        base_df = base_df[base_df['폐업일자'].dt.strftime('%Y-%m') == sel_close_ym]
        
    if only_with_phone:
        base_df = base_df[base_df['소재지전화'].notna() & (base_df['소재지전화'] != "")]
        
    df = base_df.copy()
    if sel_status != "전체":
        df = df[df['영업상태명'] == sel_status]

    # Edit Mode
    # Edit Mode
    if edit_mode:
        if not admin_auth:
             st.warning("🔒 관리자 권한이 필요합니다. 사이드바 설정 메뉴에서 암호를 입력해주세요.")
             st.stop()
             
        # Authorized Logic
        st.title("🛠️ 영업구역 및 담당자 수정")
        st.info("💡 '관리지사'와 '영업구역(코드)'을 수정할 수 있습니다. 수정을 완료한 후 **[💾 수정본 다운로드]** 버튼을 눌러 저장하세요.")
        
        # [FEATURE] Enhanced Filters
        st.markdown("##### 🛠️ 편의 도구: 수정 대상 필터링")
        
        # 1. Scope Override
        ignore_global = st.checkbox("🔓 Sidebar 공통 필터 무시 (전체 데이터 불러오기)", value=False, help="체크 시 사이드바의 필터를 무시하고 전체 데이터를 대상으로 검색합니다.")
        
        if ignore_global:
            edit_target_df = raw_df.copy()
        else:
            edit_target_df = df.copy()
            
        c_e1, c_e2 = st.columns(2)
        
        # 2. Branch Filter
        with c_e1:
             all_branches_edit = sorted(edit_target_df['관리지사'].dropna().unique())
             sel_edit_branches = st.multiselect("1. 수정할 지사 선택 (복수 가능)", all_branches_edit, placeholder="전체 (미선택 시)")
             
        if sel_edit_branches:
            edit_target_df = edit_target_df[edit_target_df['관리지사'].isin(sel_edit_branches)]
            
        # 3. Manager Filter (Dynamic based on Branch)
        with c_e2:
             all_managers_edit = sorted(edit_target_df['SP담당'].dropna().unique())
             sel_edit_managers = st.multiselect("2. 수정할 담당자 선택 (복수 가능)", all_managers_edit, placeholder="전체 (미선택 시)")
             
        if sel_edit_managers:
            edit_target_df = edit_target_df[edit_target_df['SP담당'].isin(sel_edit_managers)]
            
        branche_opts = ['중앙지사', '강북지사', '서대문지사', '고양지사', '의정부지사', '남양주지사', '강릉지사', '원주지사']
        
        column_config = {
             "관리지사": st.column_config.SelectboxColumn("관리지사 (선택)", options=branche_opts, required=True, width="medium"),
             "영업구역 수정": st.column_config.TextColumn("영업구역 (Code)", width="medium", help="영업구역 코드 (예: G000407)"),
             "SP담당": st.column_config.TextColumn("SP실명 (담당자)", disabled=True, width="medium"),
             "사업장명": st.column_config.TextColumn("사업장명", disabled=True),
             "소재지전체주소": st.column_config.TextColumn("주소", disabled=True),
        }
        
        available_cols = edit_target_df.columns.tolist()
        base_cols = ['사업장명', '영업상태명', '관리지사']
        if '영업구역 수정' in available_cols:
            base_cols.append('영업구역 수정')
            
        base_cols.append('SP담당')
        base_cols.extend(['소재지전체주소', '업태구분명'])
        
        cols_to_show = [c for c in base_cols if c in available_cols]
        
        editable_cols = ['관리지사', '영업구역 수정']
        disabled_cols = [c for c in cols_to_show if c not in editable_cols]
        
        edited_df = st.data_editor(
            edit_target_df[cols_to_show],
            column_config=column_config,
            use_container_width=True,
            num_rows="fixed",
            hide_index=True,
            height=600,
            disabled=disabled_cols
        )
        
        st.success(f"총 {len(edited_df)}건의 데이터가 표시되었습니다.")
        
        csv_edit = edited_df.to_csv(index=False, encoding='cp949').encode('cp949')
        st.download_button(
            label="💾 수정된 데이터 다운로드 (CSV)",
            data=csv_edit,
            file_name="영업기회_수정본.csv",
            mime="text/csv",
            type="primary"
        )
        
        st.stop() 
        
    # Dashboard
    custom_branch_order = ['중앙지사', '강북지사', '서대문지사', '고양지사', '의정부지사', '남양주지사', '강릉지사', '원주지사']
    # [FIX] Normalize constants
    custom_branch_order = [unicodedata.normalize('NFC', b) for b in custom_branch_order]
    
    try:
        current_branches = list(base_df['관리지사'].unique())
        sorted_branches = [b for b in custom_branch_order if b in current_branches]
        others = [b for b in current_branches if b not in custom_branch_order]
        sorted_branches.extend(others)
    except:
        sorted_branches = []
    
    st.markdown("### 🏢 지사별 현황")
    
    if 'dash_branch' not in st.session_state:
        st.session_state.dash_branch = sorted_branches[0] if sorted_branches else None
        
    b_rows = [sorted_branches[i:i+8] for i in range(0, len(sorted_branches), 8)]
    for row in b_rows:
        cols = st.columns(len(row))
        for idx, btn_name in enumerate(row):
            with cols[idx]:
                # [FIX] Normalize comparison (use calculated source)
                # We defer calculation of raw_dashboard_branch to below (hack for layout order), 
                # OR we accept that buttons might flicker if we don't move the logic up.
                # Actually, best is to use sel_branch directly here as well:
                current_active_btn = sel_branch if sel_branch != "전체" else st.session_state.get('sb_branch', "전체")
                current_active_btn = unicodedata.normalize('NFC', current_active_btn)
                
                # [FIX] Shorten Branch Name for Display (e.g., "중앙지사" -> "중앙")
                # But keep full name for logic
                disp_name = btn_name.replace("지사", "")
                
                type_ = "primary" if current_active_btn == btn_name else "secondary"
                st.button(
                    disp_name, 
                    key=f"btn_{btn_name}", 
                    type=type_, 
                    use_container_width=True,
                    on_click=update_branch_state,
                    args=(btn_name,)
                )


    
    # [FIX] Source of Truth: Prioritize Widget (sel_branch) if active, else Session State
    if sel_branch != "전체":
        raw_dashboard_branch = sel_branch
    else:
        raw_dashboard_branch = st.session_state.get('sb_branch', "전체")
    sel_dashboard_branch = unicodedata.normalize('NFC', raw_dashboard_branch)

    cols = st.columns(len(sorted_branches) if sorted_branches else 1)
    for i, col in enumerate(cols):
        if i < len(sorted_branches):
            b_name = sorted_branches[i]
            # b_name is already normalized
            b_df = base_df[base_df['관리지사'] == b_name]
            b_total = len(b_df)
            count_active = len(b_df[b_df['영업상태명'] == '영업/정상'])
            count_closed = len(b_df[b_df['영업상태명'] == '폐업'])
            count_others = b_total - count_active - count_closed
            
            bg_color = "#e8f5e9" if b_name == sel_dashboard_branch else "#ffffff"
            border_color = "#2E7D32" if b_name == sel_dashboard_branch else "#e0e0e0"
            
            status_text = f"<span style='color:#2E7D32'>영업 {count_active}</span> / <span style='color:#d32f2f'>폐업 {count_closed}</span>"
            if count_others > 0: status_text += f" / <span style='color:#757575'>기타 {count_others}</span>"
            
            with col:
                branch_html = f'<div style="background-color: {bg_color}; border: 2px solid {border_color}; border-radius: 8px; padding: 10px; text-align: center;"><div style="font-weight:bold; font-size:0.9rem; margin-bottom:5px; color:#333;">{b_name}</div><div style="font-size:1.2rem; font-weight:bold; color:#000;">{b_total:,}</div><div style="font-size:0.8rem; margin-top:4px;">{status_text}</div></div>'
                st.markdown(branch_html, unsafe_allow_html=True)
                
                b_c1, b_c2 = st.columns(2)
                with b_c1:
                    st.button("영업", key=f"btn_br_active_{b_name}", on_click=update_branch_with_status, args=(b_name, '영업/정상'), use_container_width=True)
                with b_c2:
                    st.button("폐업", key=f"btn_br_closed_{b_name}", on_click=update_branch_with_status, args=(b_name, '폐업'), use_container_width=True)
    
    st.markdown("---")
    
    if not base_df.empty:

        # [FIX] Force Source of Truth for Header Text
        if sel_branch != "전체":
            current_br_name = sel_branch
        else:
            current_br_name = sel_dashboard_branch if sel_dashboard_branch and sel_dashboard_branch != "전체" else "전체"
        
        # [FIX] Strict Normalization for Manager Section
        current_br_name = unicodedata.normalize('NFC', current_br_name)
        
        st.markdown(f"### 👤 {current_br_name} 영업담당 현황")
        
        if current_br_name != "전체":
             # [FIX] Decouple from base_df to ensure Header-Content Match
             # We go back to raw_df and filter explicitly for the request branch.
             # This bypasses any Sidebar lag that might have filtered base_df to the wrong branch. (e.g. Gangbuk)
             
             # 1. Start with Raw
             mgr_df = raw_df[raw_df['관리지사'].astype(str).apply(lambda x: unicodedata.normalize('NFC', x)) == current_br_name].copy()
             
             # 2. Re-apply Common Filters (Date, Type, Status) if they exist
             # This ensures the manager view is still relevant, just correctly branched.
             if sel_permit_ym != "전체":
                 mgr_df = mgr_df[mgr_df['인허가일자'].dt.strftime('%Y-%m') == sel_permit_ym]
             if sel_close_ym != "전체":
                 mgr_df = mgr_df[mgr_df['폐업일자'].dt.strftime('%Y-%m') == sel_close_ym]
             if sel_status != "전체":
                 mgr_df = mgr_df[mgr_df['영업상태명'] == sel_status]
             if only_hospitals:
                 mask = mgr_df[type_col].astype(str).str.contains('병원|의원', na=False)
                 if '개방서비스명' in mgr_df.columns:
                     mask = mask | mgr_df['개방서비스명'].astype(str).str.contains('병원|의원', na=False)
                 mgr_df = mgr_df[mask]
        else:
             mgr_df = base_df.copy()
             
        manager_items = [] 
        
        if '영업구역 수정' in mgr_df.columns:
            # [FIX] Do NOT dropna. Keep managers even if they lack a code.
            # [FIX] Exclude 'Unassigned' or NaN names explicitly to prevent ghost cards
            temp_g = mgr_df[['영업구역 수정', 'SP담당']].drop_duplicates()
            temp_g = temp_g.dropna(subset=['SP담당'])
            temp_g = temp_g[temp_g['SP담당'] != '미지정']
            
            temp_g['영업구역 수정'] = temp_g['영업구역 수정'].fillna('')
            
            # [UX] Sort by Name first to match Sidebar order, then Code.
            # This makes it easier to find people.
            temp_g = temp_g.sort_values(by=['SP담당', '영업구역 수정'])
            
            for _, r in temp_g.iterrows():
                code = r['영업구역 수정']
                name = r['SP담당']
                # If code exists, show it. If not, just show Name.
                if code:
                    label = f"{code} ({name})"
                else:
                    label = name
                    
                manager_items.append({'label': label, 'code': code if code else None, 'name': name})
                
        else:
            unique_names = sorted(mgr_df['SP담당'].dropna().unique())
            for name in unique_names:
                manager_items.append({'label': name, 'code': None, 'name': name})
        
        m_cols = st.columns(8)
        for i, item in enumerate(manager_items):
            col_idx = i % 8
            
            if item['code']:
                m_sub_df = mgr_df[mgr_df['영업구역 수정'] == item['code']]
                target_val = item['code']
                use_code_filter = True
            else:
                m_sub_df = mgr_df[mgr_df['SP담당'] == item['name']]
                target_val = item['name']
                use_code_filter = False
                
            mgr_label = item['label']
            m_total = len(m_sub_df)
            
            m_active = len(m_sub_df[m_sub_df['영업상태명'] == '영업/정상'])
            m_closed = len(m_sub_df[m_sub_df['영업상태명'] == '폐업'])
            with m_cols[col_idx]:
                  current_sb_manager = st.session_state.get('sb_manager', "전체")
                  is_selected = (current_sb_manager == mgr_label)
                  
                  border_color_mgr = "#2E7D32" if is_selected else "#e0e0e0"
                  bg_color_mgr = "#e8f5e9" if is_selected else "#ffffff"
                  
                  unique_key_suffix = item['code'] if item['code'] else item['name']

                  manager_card_html = f'<div class="metric-card" style="margin-bottom:4px; padding: 10px 5px; text-align: center; border: 2px solid {border_color_mgr}; background-color: {bg_color_mgr};"><div class="metric-label" style="color:#555; font-size: 0.85rem; font-weight:bold; margin-bottom:4px;">{mgr_label}</div><div class="metric-value" style="color:#333; font-size: 1.1rem; font-weight:bold;">{m_total:,}</div><div class="metric-sub" style="font-size:0.75rem; margin-top:4px;"><span style="color:#2E7D32">영업 {m_active}</span> / <span style="color:#d32f2f">폐업 {m_closed}</span></div></div>'
                  st.markdown(manager_card_html, unsafe_allow_html=True)
                  
                  m_c1, m_c2 = st.columns(2)
                  with m_c1:
                      st.button("영업", key=f"btn_mgr_active_{unique_key_suffix}", on_click=update_manager_with_status, args=(mgr_label, '영업/정상'), use_container_width=True)
                  with m_c2:
                      st.button("폐업", key=f"btn_mgr_closed_{unique_key_suffix}", on_click=update_manager_with_status, args=(mgr_label, '폐업'), use_container_width=True)

    st.markdown("---")

    tab1, tab_stats, tab2, tab3 = st.tabs(["🗺️ 지도 & 분석", "📈 상세통계", "📱 모바일 리스트", "📋 데이터 그리드"])

    with tab1:
        st.subheader("🗺️ 지사/담당자 조회")
        
        # [FEATURE] Condition View Toolbar (Quick Filters)
        st.caption("조건별 빠른 조회 (지도 위에 표시됩니다)")
        c_q1, c_q2, c_q3, c_q4 = st.columns(4)
        with c_q1: q_new = st.checkbox("🆕 신규(15일)", value=False)
        with c_q2: q_closed = st.checkbox("🚫 폐업(15일)", value=False)
        with c_q3: q_hosp = st.checkbox("🏥 병원만", value=False)
        with c_q4: q_large = st.checkbox("🏗️ 100평↑", value=False)
        
        st.markdown("---")
        
        map_df_base = df.dropna(subset=['lat', 'lon']).copy()
        
        # [FEATURE] Apply Quick Filters (Pre-Filtering for Dynamic Dropdowns)
        # 1. Date Filters (OR Logic: New OR Closed)
        date_mask = pd.Series([False] * len(map_df_base), index=map_df_base.index)
        has_date_filter = False
        
        if q_new:
             has_date_filter = True
             if '인허가일자' in map_df_base.columns:
                 map_df_base['인허가일자'] = pd.to_datetime(map_df_base['인허가일자'], errors='coerce')
                 cutoff_new = pd.Timestamp.now() - pd.Timedelta(days=15)
                 date_mask = date_mask | (map_df_base['인허가일자'] >= cutoff_new)
                 
        if q_closed:
             has_date_filter = True
             if '폐업일자' in map_df_base.columns:
                 map_df_base['폐업일자'] = pd.to_datetime(map_df_base['폐업일자'], errors='coerce')
                 cutoff_closed = pd.Timestamp.now() - pd.Timedelta(days=15)
                 date_mask = date_mask | (map_df_base['폐업일자'] >= cutoff_closed)
        
        if has_date_filter:
            map_df_base = map_df_base[date_mask]
                 
        # 2. Property Filters (AND Logic)
        if q_hosp:
             if '업태구분명' in map_df_base.columns:
                 map_df_base = map_df_base[map_df_base['업태구분명'].astype(str).str.contains('병원|의원', na=False)]
                 
        if q_large:
             if '소재지면적' in map_df_base.columns:
                 map_df_base['소재지면적_ad'] = pd.to_numeric(map_df_base['소재지면적'], errors='coerce').fillna(0)
                 map_df_base = map_df_base[map_df_base['소재지면적_ad'] >= 330.0]
        
        st.markdown("---")
        
        c_f1, c_f2, c_f3 = st.columns(3)
        
        # [Dynamic Dropdowns]
        # Logic: Type Selection should filter Region/Manager lists.
        # We need to peek at the current 'map_biz_type' from session state if available
        current_map_type = st.session_state.get('map_biz_type', "전체")
        
        # Filter base for options based on Type (if selected)
        options_source_df = map_df_base.copy()
        if current_map_type != "전체" and '업태구분명' in options_source_df.columns:
            options_source_df = options_source_df[options_source_df['업태구분명'] == current_map_type]
            
        with c_f1:
            # Dropdowns use filtered data for options
            map_region_opts = ["전체"] + sorted(list(options_source_df['관리지사'].dropna().unique()))
            sel_map_region = st.selectbox("관리지사", map_region_opts, key="map_region")
        with c_f2:
            # Filter Sales options based on Region (if selected) + Type (already applied to options_source_df)
            temp_sales_source = options_source_df
            if sel_map_region != "전체": 
                temp_sales_source = temp_sales_source[temp_sales_source['관리지사'] == sel_map_region]
                
            map_sales_opts = ["전체"] + sorted(list(temp_sales_source['SP담당'].dropna().unique()))
            sel_map_sales = st.selectbox("담당자", map_sales_opts, key="map_sales")
            
        with c_f3:
            # Business Type Options - Should these be filtered by Region?
            # User asked for "Type selection -> Dynamic".
            # Usually, Type list comes from the Quick-filtered Base.
            map_type_col = '업태구분명' if '업태구분명' in map_df_base.columns else map_df_base.columns[0]
            try:
                # Type options come from the filters BEFORE Type selection (to allow changing type)
                # But should reflect Region selection? "Dynamic" implies full cross-filtering.
                # Let's try to filter Type options by Region if Region is selected.
                type_source_df = map_df_base
                if sel_map_region != "전체":
                    type_source_df = type_source_df[type_source_df['관리지사'] == sel_map_region]
                    
                map_type_opts = ["전체"] + sorted(list(type_source_df[map_type_col].dropna().unique()))
            except:
                map_type_opts = ["전체"]
            sel_map_type = st.selectbox("업종(업태)", map_type_opts, key="map_biz_type")
            
        # Final Filtering
        map_df = map_df_base.copy()
        if sel_map_region != "전체": map_df = map_df[map_df['관리지사'] == sel_map_region]
        if sel_map_sales != "전체": map_df = map_df[map_df['SP담당'] == sel_map_sales]
        if sel_map_type != "전체": map_df = map_df[map_df['업태구분명'] == sel_map_type]
            
        st.markdown(f"**📍 조회된 업체**: {len(map_df):,} 개")
        
        # [FEATURE] Visible Filter Summary for Verification
        filter_summary = []
        if sel_map_region != "전체": filter_summary.append(f"지사:{sel_map_region}")
        if sel_map_sales != "전체": filter_summary.append(f"담당:{sel_map_sales}")
        if sel_map_type != "전체": filter_summary.append(f"업종:{sel_map_type}")
        if sel_status != "전체": filter_summary.append(f"상태:{sel_status}")
        
        if filter_summary:
            st.caption(f"ℹ️ 적용된 필터: {', '.join(filter_summary)}")
            
        st.markdown("---")
        
        st.markdown("#### 🗺️ 지도")
        if not map_df.empty:
            if kakao_key:
                map_visualizer.render_kakao_map(map_df, kakao_key)
            else:
                map_visualizer.render_folium_map(map_df)
        else:
            st.warning("표시할 데이터가 없습니다.")
            
    with tab_stats:
        st.subheader("📈 다차원 상세 분석")
        
        now = datetime.now()
        if '인허가일자' in df.columns:
            valid_dates = df.dropna(subset=['인허가일자']).copy()
            if not valid_dates.empty:
                if not pd.api.types.is_datetime64_any_dtype(valid_dates['인허가일자']):
                     valid_dates['인허가일자'] = pd.to_datetime(valid_dates['인허가일자'], errors='coerce')
                
                valid_dates['business_years'] = (now - valid_dates['인허가일자']).dt.days / 365.25
                avg_age = valid_dates['business_years'].mean()
            else:
                avg_age = 0
        else:
            avg_age = 0
            
        if '평수' not in df.columns:
             if '소재지면적' in df.columns:
                 df['평수'] = pd.to_numeric(df['소재지면적'], errors='coerce').fillna(0) / 3.3058
             else:
                 df['평수'] = 0
        
        avg_area = df['평수'].mean()
        
        def extract_dong(addr):
             if pd.isna(addr): return "미상"
             tokens = addr.split()
             for t in tokens:
                 if t.endswith('동') or t.endswith('읍') or t.endswith('면'):
                     return t
             return "기타"
             
        df['dong'] = df['소재지전체주소'].astype(str).apply(extract_dong)
        top_dong = df['dong'].value_counts().idxmax() if not df.empty else "-"
        
        m1, m2, m3, m4 = st.columns(4)
        with m1: st.metric("평균 업력 (운영기간)", f"{avg_age:.1f}년")
        with m2: st.metric("평균 매장 규모", f"{avg_area:.1f}평")
        with m3: st.metric("최대 밀집 지역", top_dong)
        with m4: st.metric("현재 조회수", f"{len(df):,}개")
        
        st.divider()
        
        st.markdown("##### 🏢 지사별 업체 분포 (선택된 영업상태 기준)")
        
        if not df.empty:
            c3, c4 = st.columns([1,1])
            
            pie_base = alt.Chart(df).encode(
                theta=alt.Theta("count()", stack=True),
                color=alt.Color("관리지사", legend=alt.Legend(title="지사")),
                tooltip=["관리지사", "count()", alt.Tooltip("count()", format=".1%", title="비율")]
            )
            
            pie = pie_base.mark_arc(outerRadius=120).encode(
                order=alt.Order("count()", sort="descending")
            )
            
            pie_text = pie_base.mark_text(radius=140).encode(
                text=alt.Text("count()", format=",.0f"),
                order=alt.Order("count()", sort="descending"),
                color=alt.value("black") 
            )
            
            with c3:
                st.markdown("**지사별 점유율 (Pie)**")
                st.altair_chart((pie + pie_text), use_container_width=True)
                
            bar_base = alt.Chart(df).encode(
                x=alt.X("관리지사", sort=custom_branch_order, title=None),
                y=alt.Y("count()", title="업체 수"),
                color=alt.Color("영업상태명", scale=alt.Scale(domain=['영업/정상', '폐업'], range=['#2E7D32', '#d32f2f']), legend=alt.Legend(title="상태")),
                tooltip=["관리지사", "영업상태명", "count()"]
            )
            
            stacked_bar = bar_base.mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5)
            
            with c4:
                st.markdown("**지사별 영업상태 누적 (Stacked)**")
                st.altair_chart(stacked_bar.interactive(), use_container_width=True)
                
            st.divider()
            
            st.markdown("##### 👤 영업담당별 실적 Top 10")
            mgr_counts = df['SP담당'].value_counts().head(10).reset_index()
            mgr_counts.columns = ['SP담당', 'count']
            
            mgr_chart = alt.Chart(mgr_counts).mark_bar(color="#4DB6AC", cornerRadiusTopRight=5, cornerRadiusBottomRight=5).encode(
                x=alt.X("count", title="업체 수"),
                y=alt.Y("SP담당", sort='-x', title=None),
                tooltip=["SP담당", "count"]
            )
            
            mgr_text = mgr_chart.mark_text(dx=5, align='left', color='black').encode(
                text=alt.Text("count", format=",.0f")
            )
            
            st.altair_chart((mgr_chart + mgr_text), use_container_width=True)
            
        else:
            st.info("조건에 맞는 데이터가 없습니다.")

        st.divider()
        st.markdown("##### 🏘️ 행정동(읍/면/동)별 상위 TOP 20")
        dong_counts = df['dong'].value_counts().reset_index()
        dong_counts.columns = ['행정구역', '업체수']
        
        top20 = dong_counts.head(20)
        
        dong_chart = alt.Chart(top20).mark_bar(color="#7986CB").encode(
            x=alt.X('업체수', title="업체 수"),
            y=alt.Y('행정구역', sort='-x', title=None),
            tooltip=['행정구역', '업체수']
        )
        
        dong_text = dong_chart.mark_text(dx=5, align='left', color='black').encode(
             text=alt.Text("업체수", format=",.0f")
        )
        
        st.altair_chart((dong_chart + dong_text), use_container_width=True)

    with tab2:
        st.subheader("📱 영업 공략 리스트")
        
        keyword = st.text_input("검색", placeholder="업체명 또는 주소...")
            
        m_df = df.copy()
        
        if keyword: m_df = m_df[m_df['사업장명'].str.contains(keyword, na=False) | m_df['소재지전체주소'].str.contains(keyword, na=False)]
        
        st.caption(f"조회 결과: {len(m_df):,}건")
        
        ITEMS_PER_PAGE = 24 
        if 'page' not in st.session_state: st.session_state.page = 0
        total_pages = max(1, (len(m_df)-1)//ITEMS_PER_PAGE + 1)
        
        start = st.session_state.page * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        page_df = m_df.iloc[start:end]
        
        col_p, col_n = st.columns([1,1])
        with col_p:
            if st.button("Previous Pages") and st.session_state.page > 0:
                st.session_state.page -= 1
                st.rerun()
        with col_n:
            if st.button("Next Pages") and st.session_state.page < total_pages - 1:
                st.session_state.page += 1
                st.rerun()
                
        rows = [page_df.iloc[i:i+4] for i in range(0, len(page_df), 4)]
        
        for row_chunk in rows:
            cols = st.columns(4)
            for idx, (idx_df, row) in enumerate(row_chunk.iterrows()):
                status_cls = "status-open" if row['영업상태명'] == '영업/정상' else "status-closed"
                tel = row['소재지전화'] if pd.notna(row['소재지전화']) else ""
                
                def fmt_date(d):
                    if pd.isna(d): return ""
                    try:
                        return d.strftime('%Y-%m-%d')
                    except:
                        return ""

                permit_date = fmt_date(row.get('인허가일자'))
                close_date = fmt_date(row.get('폐업일자'))
                
                date_html = ""
                if permit_date:
                    date_html += f"<span style='color:#1565C0'>인허가: {permit_date}</span> "
                if close_date:
                    date_html += f"<span style='color:#d32f2f'>폐업: {close_date}</span>"
                
                with cols[idx]:
                    tel_html = ('<br>📞 ' + tel) if tel else ''
                    footer_html = f'<div class="card-container" style="min-height:120px; padding: 10px;"><div class="card-title" style="font-size:0.95rem; margin-bottom: 4px;">{row["사업장명"]}<div class="card-badges"><span class="status-badge {status_cls}" style="padding: 1px 4px; font-size: 0.65rem;">{row["영업상태명"]}</span></div></div><div class="card-meta" style="font-size:0.75rem; margin-bottom: 4px;">{row["업태구분명"]} | {row["평수"]}평<br>{row["관리지사"]} ({row["SP담당"]})</div><div class="card-meta" style="font-size:0.7rem; margin-bottom: 4px; font-weight:bold;">{date_html}</div><div class="card-address" style="font-size:0.7rem; color:#888;">{row["소재지전체주소"]}{tel_html}</div></div>'
                    st.markdown(footer_html, unsafe_allow_html=True)
                    
                    b1, b2, b3 = st.columns([1,1,2])
                    with b1:
                        if tel: st.link_button("📞", f"tel:{tel}", use_container_width=True)
                        else: st.button("📞", disabled=True, key=f"nc_{idx_df}", use_container_width=True)
                    with b2:
                         st.link_button("🗺️", f"https://map.naver.com/v5/search/{row['소재지전체주소']}", use_container_width=True)
                    with b3:
                         st.link_button("🔍 검색", f"https://search.naver.com/search.naver?query={row['사업장명']}", use_container_width=True)
    
    with tab3:
        st.markdown("### 📋 전체 데이터")
        
        custom_branch_order = [
            '중앙지사', '강북지사', '서대문지사', '고양지사', '의정부지사', 
            '남양주지사', '강릉지사', '원주지사', '미지정'
        ]
        
        df['관리지사'] = pd.Categorical(df['관리지사'], categories=custom_branch_order, ordered=True)
        
        grid_df = df.copy()
        
        if '인허가일자' in grid_df.columns:
            grid_df['인허가일자'] = grid_df['인허가일자'].apply(lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) else "")
            
        if '폐업일자' in grid_df.columns:
            grid_df['폐업일자'] = grid_df['폐업일자'].apply(lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) else "")

        grid_df = grid_df.sort_values(by=['관리지사', 'SP담당', '업태구분명'])
        
        display_cols = [
            '관리지사', 'SP담당', '업태구분명', '사업장명', 
            '소재지전체주소', '소재지전화', '평수', '인허가일자', '폐업일자'
        ]
        
        final_cols = [c for c in display_cols if c in grid_df.columns]
        df_display = grid_df[final_cols]
        
        st.dataframe(
            df_display, 
            use_container_width=True, 
            height=600,
            column_config={
                "평수": st.column_config.NumberColumn(format="%.1f평"),
            }
        )
        
        csv = df_display.to_csv(index=False, encoding='cp949').encode('cp949')
        st.download_button("📥 CSV 다운로드", csv, "영업기회_처리결과.csv", "text/csv")

else:
    st.info("👈 사이드바에서 데이터를 업로드하거나, '자동 감지' 기능을 확인하세요.")
    st.markdown("### 🚀 시작하기\n1. **자동 모드**: `data/` 폴더에 파일이 있으면 자동으로 불러옵니다.\n2. **수동 모드**: 언제든지 사이드바에서 파일을 직접 업로드할 수 있습니다.\n\n> **Tip**: 모바일 접속 시 '홈 화면에 추가'하여 앱처럼 사용하세요!", unsafe_allow_html=True)
