#!/bin/bash
# local_sync.sh (Mac/Linux용)
# 8시 10분에 실행되도록 설정하면 좋습니다.

echo "🚀 최신 데이터를 가져오는 중..."
cd "$(dirname "$0")"
git pull origin main
echo "✅ 동기화 완료! 이제 최신 데이터를 확인하세요."
