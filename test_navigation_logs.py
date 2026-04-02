"""
Test script to generate sample navigation logs for testing
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src import usage_logger

# Generate sample navigation logs
sample_navigations = [
    {
        'user_role': 'manager',
        'user_name': '김철수',
        'user_branch': '중앙지사',
        'business_name': '(주)삼성전자',
        'address': '서울특별시 서초구 서초대로74길 11',
        'lat': 37.4979,
        'lon': 127.0276
    },
    {
        'user_role': 'manager',
        'user_name': '김철수',
        'user_branch': '중앙지사',
        'business_name': 'LG전자 본사',
        'address': '서울특별시 영등포구 여의대로 128',
        'lat': 37.5219,
        'lon': 126.9245
    },
    {
        'user_role': 'branch',
        'user_name': '강북지사',
        'user_branch': '강북지사',
        'business_name': '현대백화점 압구정점',
        'address': '서울특별시 강남구 압구정로 165',
        'lat': 37.5273,
        'lon': 127.0276
    },
    {
        'user_role': 'manager',
        'user_name': '이영희',
        'user_branch': '서대문지사',
        'business_name': '롯데마트 서울역점',
        'address': '서울특별시 중구 청파로 426',
        'lat': 37.5547,
        'lon': 126.9707
    },
    {
        'user_role': 'manager',
        'user_name': '김철수',
        'user_branch': '중앙지사',
        'business_name': '(주)삼성전자',
        'address': '서울특별시 서초구 서초대로74길 11',
        'lat': 37.4979,
        'lon': 127.0276
    }
]

print("샘플 네비게이션 로그 생성 중...")

for nav in sample_navigations:
    usage_logger.log_navigation(
        user_role=nav['user_role'],
        user_name=nav['user_name'],
        user_branch=nav['user_branch'],
        business_name=nav['business_name'],
        address=nav['address'],
        lat=nav['lat'],
        lon=nav['lon']
    )
    print(f"✓ {nav['user_name']} -> {nav['business_name']}")

print(f"\n완료! 총 {len(sample_navigations)}개의 네비게이션 로그가 생성되었습니다.")
print("관리자 대시보드에서 '🚗 네비게이션 이력' 탭을 확인하세요.")
