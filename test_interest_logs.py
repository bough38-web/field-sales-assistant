"""
Test script to generate sample interest logs for testing
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src import usage_logger

# Generate sample interest logs
sample_interests = [
    {
        'user_role': 'manager',
        'user_name': '김철수',
        'user_branch': '중앙지사',
        'business_name': '스타벅스 강남점',
        'address': '서울특별시 강남구 테헤란로 152',
        'road_address': '서울특별시 강남구 테헤란로 152',
        'lat': 37.5048,
        'lon': 127.0495
    },
    {
        'user_role': 'manager',
        'user_name': '이영희',
        'user_branch': '서대문지사',
        'business_name': '이디야커피 신촌점',
        'address': '서울특별시 서대문구 신촌로 83',
        'road_address': '서울특별시 서대문구 신촌로 83',
        'lat': 37.5591,
        'lon': 126.9368
    },
    {
        'user_role': 'branch',
        'user_name': '강북지사',
        'user_branch': '강북지사',
        'business_name': '투썸플레이스 노원점',
        'address': '서울특별시 노원구 동일로 1414',
        'road_address': '서울특별시 노원구 동일로 1414',
        'lat': 37.6543,
        'lon': 127.0615
    },
    {
        'user_role': 'manager',
        'user_name': '김철수',
        'user_branch': '중앙지사',
        'business_name': '스타벅스 강남점',
        'address': '서울특별시 강남구 테헤란로 152',
        'road_address': '서울특별시 강남구 테헤란로 152',
        'lat': 37.5048,
        'lon': 127.0495
    },
    {
        'user_role': 'manager',
        'user_name': '박민수',
        'user_branch': '고양지사',
        'business_name': '할리스커피 일산점',
        'address': '경기도 고양시 일산동구 중앙로 1261',
        'road_address': '경기도 고양시 일산동구 중앙로 1261',
        'lat': 37.6584,
        'lon': 126.7729
    }
]

print("샘플 관심 업체 로그 생성 중...")

for interest in sample_interests:
    usage_logger.log_interest(
        user_role=interest['user_role'],
        user_name=interest['user_name'],
        user_branch=interest['user_branch'],
        business_name=interest['business_name'],
        address=interest['address'],
        road_address=interest['road_address'],
        lat=interest['lat'],
        lon=interest['lon']
    )
    print(f"✓ {interest['user_name']} -> {interest['business_name']}")

print(f"\n완료! 총 {len(sample_interests)}개의 관심 업체 로그가 생성되었습니다.")
print("관리자 대시보드에서 '⭐ 관심 업체' 탭을 확인하세요.")
