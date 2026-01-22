
import streamlit as st
import os
import glob
import datetime
from src.config import ROLE_MAP
from src.utils import mask_name
from src import data_loader

def render_sidebar():
    """
    Renders the sidebar and returns the selected data configuration and theme.
    Returns: 
        dict: {
            'data_source': str,
            'uploaded_dist': str or None,
            'uploaded_zip': str or None,
            'api_df': df or None,
            'theme_mode': str
        }
    """
    with st.sidebar:
        st.header("⚙️ 설정 & 데이터")
        
        # [FEATURE] Logout / Role Info
        cur_role_txt = ROLE_MAP.get(st.session_state.user_role, 'Unknown')
        st.sidebar.info(f"접속: **{cur_role_txt}**")
        if st.session_state.user_role == 'branch':
            st.sidebar.caption(f"지사: {st.session_state.user_branch}")
        elif st.session_state.user_role == 'manager':
            st.sidebar.caption(f"담당: {mask_name(st.session_state.user_manager_name)}")

        if st.sidebar.button("로그아웃 (처음으로)", key="btn_logout", type="primary"):
            for key in ['user_role', 'user_branch', 'user_manager_name', 'user_manager_code', 'admin_auth']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

        st.sidebar.markdown("---")
        
        # --- Data Source Section ---
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
                for p in priority_file_match:
                    if p in local_excels: local_excels.remove(p)
                local_excels = priority_file_match + local_excels
                
            uploaded_dist = None
            uploaded_zip = None
            api_df = None
            
            use_local_dist = False

            if local_excels:
                use_local_dist = st.toggle("영업구역(Excel) 자동 로드", value=True)
                if use_local_dist:
                    file_opts = [os.path.basename(f) for f in local_excels]
                    sel_file_idx = 0
                    
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

            
            if data_source == "파일 업로드 (File)":
                 if local_zips:
                     use_local_zip = st.toggle("인허가(Zip) 자동 로드", value=True)
                     if use_local_zip:
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
                # Fixed path relative to utils/app location logic
                # Assuming this file is imported by app.py at root
                key_file_path = os.path.join("오픈API", "api_key.txt")
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
            
        st.sidebar.markdown("---")

        with st.sidebar.expander("🔑 카카오 지도 설정", expanded=False):
            st.warning("카카오 자바스크립트 키 필요")
            kakao_key = st.text_input("키 입력", type="password", key="kakao_api_key_v2")
            if kakao_key: kakao_key = kakao_key.strip()
            
            if kakao_key:
                st.success("✅ 활성화됨")
            else:
                st.caption("미입력 시: 기본 지도 사용")
    
    return {
        'data_source': data_source,
        'uploaded_dist': uploaded_dist,
        'uploaded_zip': uploaded_zip,
        'api_df': api_df,
        'theme_mode': theme_mode,
        'kakao_key': kakao_key
    }
