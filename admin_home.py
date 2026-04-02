import streamlit as st
import pandas as pd
from storage import load_targets, load_results, check_admin_password

# 🔒 인증 실행
check_admin_password()

st.title("📌 관리자 홈 (Admin Hub)")
st.markdown("---")

targets = load_targets()
results = load_results()

col1, col2, col3 = st.columns(3)
t_cnt = len(targets)
r_cnt = len(results)
prog = (r_cnt / t_cnt * 100) if t_cnt > 0 else 0

with col1: st.metric("총 조사 대상", f"{t_cnt}건")
with col2: st.metric("조치 완료", f"{r_cnt}건")
with col3: st.metric("진행률", f"{prog:.1f}%")
st.progress(prog / 100)

st.info("👈 좌측 사이드바에서 '조사 대상 업로드' 또는 '등록 결과 모니터링'을 선택하세요.")
