import streamlit as st
import pandas as pd
import altair as alt
from storage import load_results, check_admin_password

# 🔒 인증 실행
check_admin_password()

st.title("📊 등록 결과 모니터링")

# 1. 데이터 로드
results = load_results()

if results.empty:
    st.info("데이터가 없습니다.")
    st.stop()

# -----------------------------------------------------------------------------
# [핵심] 정렬 및 전처리 로직 적용
# -----------------------------------------------------------------------------
# 정렬 순서 정의
BRANCH_ORDER = ["중앙", "강북", "서대문", "고양", "의정부", "남양주", "강릉", "원주"]

# (1) '지사' 컬럼 생성 (전처리: '지사' 글자 제거)
if "관리지사" in results.columns:
    results["지사"] = results["관리지사"].astype(str).str.replace("지사", "").str.strip()
else:
    results["지사"] = "미지정"

# (2) 순서 정보 심기 (Categorical)
# sort_values를 할 때 가나다순이 아닌 BRANCH_ORDER 순서를 따르게 됩니다.
results["지사"] = pd.Categorical(
    results["지사"],
    categories=BRANCH_ORDER,
    ordered=True
)

# (3) 데이터프레임 정렬 수행 (지사 순서 우선 -> 그 다음 처리일시 역순)
if "처리일시" in results.columns:
    results["처리일시"] = pd.to_datetime(results["처리일시"], errors='coerce')
    results = results.sort_values(by=["지사", "처리일시"], ascending=[True, False])
else:
    results = results.sort_values(by="지사")

# -----------------------------------------------------------------------------
# 상단 지표 (Metrics)
# -----------------------------------------------------------------------------
c1, c2, c3 = st.columns(3)
with c1: 
    st.metric("총 건수", f"{len(results):,} 건")
with c2: 
    # 최다 지사 계산 시 전처리된 '지사' 컬럼 사용
    mode_val = results["지사"].mode()[0] if not results["지사"].empty else "-"
    st.metric("최다 지사", str(mode_val))
with c3: 
    recent_time = results["처리일시"].max().strftime("%m-%d %H:%M") if "처리일시" in results.columns else "-"
    st.metric("최근 업데이트", recent_time)

st.markdown("---")

# -----------------------------------------------------------------------------
# 시각화 (Altair) - 정렬 순서 적용
# -----------------------------------------------------------------------------
col1, col2 = st.columns(2)

with col1:
    st.subheader("지사별 처리 현황")
    # value_counts()를 하면 인덱스가 섞일 수 있으므로 다시 정렬 정보 확인 필요하지만,
    # Altair에 직접 sort 리스트를 넣어주는 것이 가장 확실합니다.
    
    cnt_branch = results["지사"].value_counts().reset_index()
    cnt_branch.columns = ["지사", "건수"]
    
    chart_branch = alt.Chart(cnt_branch).mark_bar().encode(
        x=alt.X("건수", title="건수"),
        y=alt.Y(
            "지사", 
            title="관리지사", 
            sort=BRANCH_ORDER  # 👈 [중요] 여기에 리스트를 넣어야 차트 순서가 고정됨
        ), 
        color=alt.Color("지사", legend=None),
        tooltip=["지사", "건수"]
    )
    st.altair_chart(chart_branch, use_container_width=True)

with col2:
    st.subheader("유형별 현황")
    if "해지사유" in results.columns:
        cnt_reason = results["해지사유"].value_counts().reset_index()
        cnt_reason.columns = ["사유", "건수"]
        
        chart_reason = alt.Chart(cnt_reason).mark_arc(innerRadius=50).encode(
            theta=alt.Theta("건수", stack=True),
            color=alt.Color("사유", title="해지 사유"),
            tooltip=["사유", "건수"],
            order=alt.Order("건수", sort="descending")
        )
        st.altair_chart(chart_reason, use_container_width=True)

# -----------------------------------------------------------------------------
# 상세 내역 (데이터프레임)
# -----------------------------------------------------------------------------
st.markdown("### 📋 상세 내역 (지사순 정렬)")
st.dataframe(
    results, 
    use_container_width=True,
    hide_index=True,
    column_order=["지사", "계약번호", "상호", "해지사유", "불만유형", "처리일시", "비고"] # 보여줄 컬럼 순서 지정 추천
)

st.download_button(
    "📥 CSV 다운로드", 
    results.to_csv(index=False).encode('utf-8-sig'), 
    "monitoring_results.csv",
    type="primary"
)
