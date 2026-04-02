
import unicodedata

clean_block = """            st.markdown("---")
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
"""

with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = lines[:503] + [clean_block] + lines[645:]

with open('app.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
    
print("Successfully fixed indentation in app.py")
