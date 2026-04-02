# 📋 Field Survey App (현장 조사 · 조치 관리)

## 목적
- 현업 대상 정기/이벤트성 조사 공지
- 조치 내역 웹 입력 (HTML Form)
- 조치 현황 자동 취합

## 실행 방법
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 구성
- app.py : 조사/이벤트 공지
- 조치작성 : 현업 입력 화면
- 현황모니터링 : 운영자용 취합 화면

## 연동
이 앱은 ops-dashboard-hub에서 버튼 링크로 연결됩니다.