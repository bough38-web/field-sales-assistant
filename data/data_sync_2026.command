#!/bin/bash
# Move to the project root directory where the script is located
cd "/Users/heebonpark/Downloads/내프로젝트모음/영업기회"

echo "------------------------------------------------"
echo "🚀 2026년 데이터 동기화 및 웹 배포를 시작합니다."
echo "------------------------------------------------"

# Run the python sync script
python3 data_sync_2026.py

echo ""
echo "------------------------------------------------"
echo "🏁 작업이 완료되었습니다. 이 창을 닫으셔도 됩니다."
echo "------------------------------------------------"
# Keep the terminal open so the user can see the result
read -p "Press enter to exit..."
