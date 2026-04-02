
import streamlit as st
import pandas as pd
from typing import Optional, List, Dict, Any
from src.config import BRANCH_PASSWORDS
from src import utils
from src import activity_logger

def get_manager_password(manager_name: str) -> str:
    """
    Generate simple password for manager.
    Uses first 3 characters (in lowercase romanization approximation) + 1234
    """
    # Simple Korean to English first syllable mapping
    first_syllable_map = {
        '김': 'kim', '이': 'lee', '박': 'park', '최': 'choi', '정': 'jung',
        '강': 'kang', '조': 'jo', '윤': 'yoon', '장': 'jang', '임': 'lim',
        '한': 'han', '오': 'oh', '서': 'seo', '신': 'shin', '권': 'kwon',
        '황': 'hwang', '안': 'ahn', '송': 'song', '류': 'ryu', '홍': 'hong',
        '전': 'jeon', '고': 'go', '문': 'moon', '양': 'yang', '손': 'son',
        '배': 'bae', '백': 'baek', '허': 'heo', '남': 'nam', '심': 'shim'
    }
    
    if manager_name and len(manager_name) > 0:
        first_char = manager_name[0]
        prefix = first_syllable_map.get(first_char, 'user')
        return f"{prefix}1234"
    return "user1234"

def render_login_page(global_branch_opts: List[str], raw_df: Optional[pd.DataFrame]=None, mgr_info_list: Optional[List[Dict[str, Any]]]=None):
    """
    Renders the login page with tabs for Manager, Branch, and Admin.
    """
    
    # Custom CSS for the button
    st.markdown("""
        <style>
        .block-container {
            padding-top: 1rem !important;
        }
        .manual-btn-container {
            text-align: center; 
            margin-bottom: 25px;
        }
        .manual-btn {
            background-color: #03A9F4; 
            color: white; 
            border: none; 
            padding: 12px 28px; 
            text-align: center; 
            text-decoration: none; 
            display: inline-block; 
            font-size: 16px; 
            margin: 4px 2px; 
            cursor: pointer; 
            border-radius: 8px;
            font-family: "Pretendard", sans-serif;
            font-weight: 600;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: all 0.2s ease;
        }
        .manual-btn:hover {
            transform: translateY(-2px); 
            box-shadow: 0 6px 8px rgba(0,0,0,0.15);
        }
        </style>
        
        <script>
            // Ensure link works
            const link = document.getElementById('manual-link');
            if(link) link.href = 'user_manual';
        </script>
    """, unsafe_allow_html=True)

    _, main_col, _ = st.columns([1, 2, 1])
    
    with main_col:
        st.markdown("<h1 style='text-align: center; margin-bottom: 10px;'>영업기회 포착 대시보드</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #666; margin-bottom: 20px;'>공공DATA 기반 시장의 변화 신호(인허가 정보인 신규, 수정변경, 폐업 징후)를 조기에 감지하여<br>영업 기회로 활용</p>", unsafe_allow_html=True)
        
        # Check if 'pages/user_manual.py' likely exists or just link to it
        st.markdown("""
            <div class='manual-btn-container'>
                <a href='user_manual' target='_blank' id='manual-link'>
                    <button class='manual-btn'>
                        📖 사용설명서 보기 (새 창)
                    </button>
                </a>
                <p style='color: #888; font-size: 0.8rem; margin-top: 8px;'>
                    클릭하시면 새 탭에서 매뉴얼이 열립니다
                </p>
            </div>
        """, unsafe_allow_html=True)
        
        l_tab1, l_tab2, l_tab3 = st.tabs(["👤 담당자(Manager)", "🏢 지사(Branch)", "👮 관리자(Admin)"])
        
        with l_tab1:
            st.info("본인의 영업구역/담당 데이터만 조회합니다.")
            
            # Helper for Manager Selection
            sel_br_for_mgr = st.selectbox("소속 지사 (필터용)", ["전체"] + global_branch_opts)
            
            if raw_df is not None:
                # Use authoritative manager list if available
                if mgr_info_list:
                    mgr_candidates = pd.DataFrame(mgr_info_list)
                    # [FIX] Standardize keys if they came from mgr_info_list
                    if 'name' in mgr_candidates.columns:
                        mgr_candidates.rename(columns={'name': 'SP담당', 'code': '영업구역 수정', 'branch': '관리지사'}, inplace=True)
                else:
                    mgr_candidates = raw_df.copy()
                
                if sel_br_for_mgr != "전체":
                    if '관리지사' in mgr_candidates.columns:
                        mgr_candidates = mgr_candidates[mgr_candidates['관리지사'] == sel_br_for_mgr]
                
                # Generate Logic: Name + Code
                if 'SP담당' in mgr_candidates.columns:
                     # Check for '영업구역 수정'
                    if '영업구역 수정' in mgr_candidates.columns:
                        mgr_candidates['display'] = mgr_candidates.apply(
                            lambda x: f"{utils.mask_name(x['SP담당'])} ({x['영업구역 수정']})" if pd.notna(x['영업구역 수정']) and x['영업구역 수정'] else utils.mask_name(x['SP담당']), 
                            axis=1
                        )
                        # Mapping for back-reference
                        mgr_candidates['real_name'] = mgr_candidates['SP담당']
                    else:
                        mgr_candidates['display'] = mgr_candidates['SP담당'].apply(utils.mask_name)
                        mgr_candidates['real_name'] = mgr_candidates['SP담당']
                    
                    # Create a mapping dictionary to recover the real name for password check
                    display_to_real_map = dict(zip(mgr_candidates['display'], mgr_candidates['real_name']))
                    mgr_list = sorted(mgr_candidates['display'].unique().tolist())
                else:
                     mgr_list = []
                     display_to_real_map = {}
            else:
                st.warning("데이터가 로드되지 않아 담당자 목록을 불러올 수 없습니다.")
                mgr_list = []
                display_to_real_map = {}
            
            with st.form("login_manager"):
                s_manager_display = st.selectbox("담당자 선택", mgr_list)
                manager_pw = st.text_input("담당자 패스워드", type="password", help="예: kim1234")
                if st.form_submit_button("담당자 접속", type="primary", use_container_width=True):
                    # Get real name for authentication
                    p_real_name = display_to_real_map.get(s_manager_display)
                    
                    if s_manager_display and "(" in s_manager_display and ")" in s_manager_display:
                        p_code = s_manager_display.split("(")[1].replace(")", "").strip()
                    else:
                        p_code = None
                    
                    # Validate password using real name
                    expected_pw = get_manager_password(p_real_name)
                    if manager_pw == expected_pw:
                        st.session_state.user_role = 'manager'
                        st.session_state.user_name = p_real_name
                        st.session_state.user_manager_code = p_code
                        # Also pre-set filters
                        st.session_state.sb_manager = p_real_name
                        # Log access
                        activity_logger.log_access('manager', p_real_name, 'login')
                        st.rerun()
                    else:
                        st.error("패스워드가 올바르지 않습니다.")

        with l_tab2:
            st.info("특정 지사의 데이터만 조회합니다.")
            with st.form("login_branch"):
                s_branch = st.selectbox("지사 선택", global_branch_opts)
                branch_pw = st.text_input("지사 패스워드", type="password", help="예: central123")
                if st.form_submit_button("지사 접속", type="primary", use_container_width=True):
                    # Validate password
                    expected_pw = BRANCH_PASSWORDS.get(s_branch, "")
                    if branch_pw == expected_pw:
                        st.session_state.user_role = 'branch'
                        st.session_state.user_branch = s_branch
                        st.session_state.sb_branch = s_branch # Pre-set filter
                        # Log access
                        activity_logger.log_access('branch', s_branch, 'login')
                        st.rerun()
                    else:
                        st.error("패스워드가 올바르지 않습니다.")

        with l_tab3:
            st.info("관리자 권한으로 접속합니다. (모든 데이터 열람 가능)")
            with st.form("login_admin"):
                pw = st.text_input("관리자 암호", type="password")
                if st.form_submit_button("관리자 로그인", type="primary", use_container_width=True):
                    if pw == "admin1234!":
                        st.session_state.user_role = 'admin'
                        st.session_state.admin_auth = True
                        # Log access
                        activity_logger.log_access('admin', '관리자', 'login')
                        st.rerun()
                    else:
                        st.error("암호가 올바르지 않습니다.")
        
        st.markdown("---")
        st.caption("ⓒ 2026 Field Sales Assistant System")
