import streamlit as st
import pandas as pd
import altair as alt
from storage import load_targets, load_results

st.markdown("""
<style>
    @import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.8/dist/web/static/pretendard.css");
    .stApp { background-color: #f8fafc; font-family: 'Pretendard', sans-serif; }
    .styled-table { width: 100%; border-collapse: collapse; box-shadow: 0 0 20px rgba(0,0,0,0.05); border-radius: 10px; overflow: hidden; margin-top: 20px; }
    .styled-table thead tr { background-color: #2563eb; color: #ffffff; text-align: center; }
    .styled-table th, .styled-table td { padding: 12px 15px; text-align: center; border-bottom: 1px solid #dddddd; }
    .progress-bar { background-color: #e2e8f0; border-radius: 5px; overflow: hidden; height: 8px; width: 80px; margin: 0 auto; }
    .progress-fill { height: 100%; background-color: #3b82f6; }
</style>
""", unsafe_allow_html=True)

st.title("💧 등록 현황 대시보드")

targets = load_targets()
results = load_results()

if targets.empty: st.warning("데이터가 없습니다."); st.stop()

# 지사명 표준화
if "관리지사" in targets.columns: targets["지사"] = targets["관리지사"].str.replace("지사","").str.strip()
else: targets["지사"] = "미지정"
if not results.empty and "관리지사" in results.columns: results["지사"] = results["관리지사"].str.replace("지사","").str.strip()

# 필터
with st.sidebar:
    st.header("🔍 필터")
    sel_br = st.multiselect("지사", sorted(targets["지사"].unique()))
    
filt_tgt = targets[targets["지사"].isin(sel_br)] if sel_br else targets
filt_res = results[results["계약번호"].isin(filt_tgt["계약번호"])] if not results.empty else pd.DataFrame()

# KPI
c1, c2, c3 = st.columns(3)
t_n, r_n = len(filt_tgt), len(filt_res)
p = (r_n/t_n*100) if t_n>0 else 0
with c1: st.metric("대상", t_n)
with c2: st.metric("완료", r_n, f"{p:.1f}%")
with c3: st.metric("잔여", t_n - r_n)

# 통계
stat = filt_tgt.groupby("지사").size().reset_index(name="대상")
if not filt_res.empty:
    dstat = filt_res.groupby("지사").size().reset_index(name="완료")
    stat = pd.merge(stat, dstat, on="지사", how="left").fillna(0)
else: stat["완료"] = 0
stat["진행률"] = (stat["완료"]/stat["대상"]*100).fillna(0)

# 차트
st.altair_chart(alt.Chart(stat).mark_bar().encode(x="지사", y="완료"), use_container_width=True)

# HTML 테이블
html = '<table class="styled-table"><thead><tr><th>지사</th><th>대상</th><th>완료</th><th>진행률</th><th>상태</th></tr></thead><tbody>'
for _, r in stat.iterrows():
    rt = r['진행률']
    html += f"<tr><td>{r['지사']}</td><td>{int(r['대상'])}</td><td>{int(r['완료'])}</td><td>{rt:.1f}%</td><td><div class='progress-bar'><div class='progress-fill' style='width:{rt}%'></div></div></td></tr>"
html += "</tbody></table>"
st.markdown(html, unsafe_allow_html=True)
