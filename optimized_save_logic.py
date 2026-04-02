# Optimized save logic for data grid
# Replace lines 3280-3345 in app.py with this code

if st.button("💾 변경사항 저장", use_container_width=True):
    # [OPTIMIZATION] Batch collect all changes first
    changes = []
    for idx, row in edited_df.iterrows():
        orig_row = df_display.iloc[idx]
        if (row['활동진행상태'] != orig_row['활동진행상태'] or 
            row['특이사항'] != orig_row['특이사항']):
            changes.append({
                'idx': idx,
                'row': row,
                'status': row['활동진행상태'],
                'notes': row['특이사항'],
                'key': row['record_key'],
                'name': row.get('사업장명', '')
            })
    
    if not changes:
        st.info("변경된 항목이 없습니다.")
    else:
        # [OPTIMIZATION] Load JSON once
        status_data = activity_logger.load_json_file(activity_logger.ACTIVITY_STATUS_FILE)
        
        # Progress bar for visual feedback
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        current_user = st.session_state.get('user_manager_name') or st.session_state.get('user_branch') or '관리자'
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Process all changes
        for i, change in enumerate(changes):
            # Update progress
            progress = (i + 1) / len(changes)
            progress_bar.progress(progress)
            status_text.text(f"저장 중... {i+1}/{len(changes)}")
            
            # [OPTIMIZATION] Update in-memory dict
            status_data[change['key']] = {
                "활동진행상태": change['status'],
                "특이사항": change['notes'],
                "변경일시": timestamp,
                "변경자": current_user
            }
        
        # [OPTIMIZATION] Write JSON once at the end
        activity_logger.save_json_file(activity_logger.ACTIVITY_STATUS_FILE, status_data)
        
        progress_bar.empty()
        status_text.empty()
        
        st.success(f"✅ {len(changes)}건의 변경사항이 저장되었습니다!")
        st.cache_data.clear()
        
        import time
        time.sleep(0.5)
        st.rerun()
