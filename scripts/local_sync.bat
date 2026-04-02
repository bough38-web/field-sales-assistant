@echo off
:: local_sync.bat (Windows용)
:: 작업 스케줄러에서 매일 오전 8시 10분에 실행되도록 설정하세요.

echo 🚀 최신 데이터를 가져오는 중...
cd /d %~dp0
git pull origin main
echo ✅ 동기화 완료!
pause
