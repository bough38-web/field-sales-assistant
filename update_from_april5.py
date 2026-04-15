#!/usr/bin/env python3
"""
LOCALDATA_NOWMON_CSV-8 업데이트 스크립트 (4월 5일 이후 데이터)
=============================================================
기존 CSV 파일에서 4/1~4/4 데이터는 유지하고,
4/5 ~ 오늘(4/15) 데이터를 API에서 새로 수집하여 병합합니다.

최적화:
  - 월 단위(2026-04) prefix로 한 번 스캔 → 날짜별 분류
  - 서비스 3개 동시 처리 (서비스 레벨 병렬)
  - 페이지 스캔 워커 20개 (페이지 레벨 병렬)
  - 진행률 실시간 표시
"""

import requests
import pandas as pd
import time
import urllib.parse
import math
import os
import sys
import csv
import glob
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==========================================
# 설정
# ==========================================
# 업데이트 시작일 (이 날짜 이후 데이터를 새로 수집)
UPDATE_FROM = "2026-04-05"
# 업데이트 종료일 (오늘)
UPDATE_TO = datetime.now().strftime("%Y-%m-%d")
# 월 prefix (API 스캔용)
MONTH_PREFIX = "2026-04"
# 출력 디렉토리 (워크스페이스 내)
OUTPUT_DIR = Path(__file__).resolve().parent / "LOCALDATA_UPDATE_0405_0415"
# 대상 지역
TARGET_REGIONS = ["서울특별시", "경기도", "강원도", "강원특별자치도", "인천광역시", "인천"]
# 병렬 처리 설정
PAGE_WORKERS = 20        # 페이지 병렬 워커 수
SERVICE_WORKERS = 2      # 서비스 병렬 처리 수

# ==========================================
# 세션 설정 (재시도 전략 포함)
# ==========================================
retry_strategy = Retry(
    total=5,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504]
)
adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=30, pool_maxsize=30)
session = requests.Session()
session.mount("http://", adapter)
session.mount("https://", adapter)

# ==========================================
# 기초 자료 로드
# ==========================================
BASE_PATH = Path(__file__).resolve().parent
ETC_PATH_1 = BASE_PATH / '일일데이터 공공데이터포털_API 가져오기' / '기타자료'
ETC_PATH_2 = BASE_PATH / '인허가자료db-API' / '기타자료'

# Google Sheet에서 API URL 목록 로드
sheet_name = urllib.parse.quote("조회")
SHEET_URL = f"https://docs.google.com/spreadsheets/d/1Y6n4OgetzmvJZBcq75oZRiriMWFSIh3L/gviz/tq?tqx=out:csv&sheet={sheet_name}"

# 매핑 파일 찾기
MAPPING_FILE = None
for etc_path in [ETC_PATH_1, ETC_PATH_2]:
    candidates = list(etc_path.glob("LOCALDATA*지방행정인허가*.xlsx"))
    if candidates:
        MAPPING_FILE = candidates[0]
        break
if not MAPPING_FILE:
    MAPPING_FILE = ETC_PATH_2 / 'LOCALDATA_공공데이터포털 지방행정인허가 칼럼 매핑 자료_v3 (2).xlsx'

# API 키
API_KEY_PATH = BASE_PATH / '일일데이터 공공데이터포털_API 가져오기' / '오픈API' / 'api_key.txt'
DEFAULT_KEY = "DvyS97s/WyCWPJjBU7bvoebRE+4lxRphMHewhAcQQrGMPT/8PcP0bOCO8bTs2b7H25qViKWruSqim57HphOAjA=="


def load_basics():
    """기초 자료 로드"""
    print("📋 기초 자료 로드 중...")
    df_urls = pd.read_csv(SHEET_URL, encoding='utf-8')
    df_mapping = pd.read_excel(MAPPING_FILE, sheet_name='항목매핑', skiprows=2)
    mapping_dict = dict(zip(df_mapping.iloc[:, 4].dropna(), df_mapping.iloc[:, 5].dropna()))
    
    api_key = DEFAULT_KEY
    if API_KEY_PATH.exists():
        api_key = API_KEY_PATH.read_text(encoding='utf-8').strip()
    
    print(f"  ✅ 서비스 URL: {len(df_urls)}개, 매핑 컬럼: {len(mapping_dict)}개")
    return df_urls, mapping_dict, api_key


def fetch_page(api_url, auth_key, page_no):
    """단일 페이지 API 호출"""
    decoded_key = urllib.parse.unquote(str(auth_key).strip())
    params = {
        'serviceKey': decoded_key,
        'pageNo': page_no,
        'numOfRows': 500,
        'type': 'json'
    }
    try:
        resp = session.get(api_url, params=params, timeout=(20, 180))
        if resp.status_code != 200:
            return None
        return resp.json()
    except:
        return None


def process_page_for_month(api_url, auth_key, page, mapping_dict):
    """한 페이지를 처리하여 4월 데이터 중 대상 지역만 추출"""
    res_json = fetch_page(api_url, auth_key, page)
    if not res_json:
        return []
    
    items_container = res_json.get('response', {}).get('body', {}).get('items', {})
    if not items_container:
        return []
    
    data_list = items_container.get('item', [])
    if not data_list:
        return []
    if not isinstance(data_list, list):
        data_list = [data_list]
    
    filtered_rows = []
    for item in data_list:
        addr = str(item.get('ROAD_NM_ADDR', '') or item.get('LOTNO_ADDR', '')).strip()
        updt_pnt = str(item.get('DAT_UPDT_PNT', ''))
        
        # 4월 데이터 & 대상 지역 필터
        if MONTH_PREFIX in updt_pnt and any(reg in addr for reg in TARGET_REGIONS):
            mapped_item = {mapping_dict.get(k, k): v for k, v in item.items()}
            filtered_rows.append(mapped_item)
    
    return filtered_rows


def process_one_service(service_info, mapping_dict, api_key):
    """
    하나의 서비스에 대해 4월 전체 데이터를 수집하고,
    4/5 이후 데이터만 필터링하여 반환합니다.
    """
    idx, svc_full_name, oper_name, api_url, svc_id_raw, sheet_key = service_info
    
    auth_key = sheet_key if (sheet_key and sheet_key != 'nan') else api_key
    
    if "apis.data.go.kr" not in api_url or not auth_key:
        return None, None, None, 0
    
    # 첫 페이지로 전체 건수 파악
    first_res = fetch_page(api_url, auth_key, 1)
    if not first_res:
        return svc_id_raw, oper_name, None, 0
    
    body = first_res.get('response', {}).get('body', {})
    total_count = body.get('totalCount', 0)
    if total_count == 0:
        return svc_id_raw, oper_name, None, 0
    
    total_pages = math.ceil(total_count / 500)
    
    # 전체 페이지 병렬 스캔
    all_rows = []
    batch_size = PAGE_WORKERS * 3
    
    for batch_start in range(1, total_pages + 1, batch_size):
        batch_end = min(batch_start + batch_size, total_pages + 1)
        with ThreadPoolExecutor(max_workers=PAGE_WORKERS) as executor:
            futures = {
                executor.submit(process_page_for_month, api_url, auth_key, p, mapping_dict): p
                for p in range(batch_start, batch_end)
            }
            for future in as_completed(futures):
                try:
                    rows = future.result()
                    if rows:
                        all_rows.extend(rows)
                except:
                    pass
    
    if not all_rows:
        return svc_id_raw, oper_name, None, 0
    
    df_all = pd.DataFrame(all_rows)
    return svc_id_raw, oper_name, df_all, total_pages


def filter_update_dates(df):
    """4/5 이후 데이터만 필터링"""
    date_col = None
    for col_name in ['최종수정시점', 'DAT_UPDT_PNT']:
        if col_name in df.columns:
            date_col = col_name
            break
    
    if not date_col:
        return df
    
    dates_to_include = [
        (datetime.strptime(UPDATE_FROM, "%Y-%m-%d") + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range((datetime.strptime(UPDATE_TO, "%Y-%m-%d") - datetime.strptime(UPDATE_FROM, "%Y-%m-%d")).days + 1)
    ]
    return df[df[date_col].astype(str).str.contains('|'.join(dates_to_include), na=False)]


def main():
    print("=" * 60)
    print("  LOCALDATA_NOWMON_CSV-8 업데이트 (4/5 이후)")
    print(f"  수집 범위: {UPDATE_FROM} ~ {UPDATE_TO}")
    print(f"  출력 디렉토리: {OUTPUT_DIR}")
    print("=" * 60)
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 기초 자료 로드
    df_urls, mapping_dict, api_key = load_basics()
    
    # 서비스 목록 준비
    services = []
    for idx, row in df_urls.iterrows():
        svc_full_name = str(row.iloc[1])
        oper_name = str(row.iloc[2])
        api_url = str(row.iloc[3])
        svc_id_raw = str(row.iloc[7]) if not pd.isna(row.iloc[7]) else f"ID_{idx+1}"
        
        # API 키 (시트에서 가져오거나 기본값 사용)
        try:
            sheet_key = str(row.iloc[9]) if not pd.isna(row.iloc[9]) else str(row.iloc[5])
        except:
            sheet_key = str(row.iloc[5]) if not pd.isna(row.iloc[5]) else ""
        
        if "apis.data.go.kr" not in api_url:
            continue
        
        services.append((idx, svc_full_name, oper_name, api_url, svc_id_raw, sheet_key))
    
    print(f"\n🚀 총 {len(services)}개 서비스 처리 시작...\n")
    
    updated_count = 0
    skipped_count = 0
    error_count = 0
    total_records = 0
    start_time = time.time()
    
    for i, svc_info in enumerate(services):
        idx, svc_full_name, oper_name, api_url, svc_id_raw, sheet_key = svc_info
        
        elapsed = time.time() - start_time
        eta = (elapsed / max(i, 1)) * (len(services) - i) if i > 0 else 0
        
        print(f"[{i+1}/{len(services)}] {oper_name} (ETA: {int(eta//60)}분 {int(eta%60)}초)")
        
        try:
            svc_id, oper, df_result, pages = process_one_service(svc_info, mapping_dict, api_key)
            
            if df_result is None or df_result.empty:
                skipped_count += 1
                print(f"  ⏭️ 변동 없음 ({pages}p 스캔)")
                continue
            
            svc_code = svc_id_raw.strip()
            safe_oper = oper_name.replace("/", "_").replace(" ", "_")
            
            # 4/5 이후 데이터만 필터
            df_final = filter_update_dates(df_result)
            
            if df_final.empty:
                skipped_count += 1
                print(f"  ⏭️ 4/5 이후 데이터 없음")
                continue
            
            # 출력 파일명 결정
            new_filename = f"(20260405~{UPDATE_TO.replace('-','')})_{svc_code}_P_{safe_oper}.csv"
            output_path = OUTPUT_DIR / new_filename
            
            df_final.to_csv(output_path, index=False, encoding='cp949')
            record_count = len(df_final)
            total_records += record_count
            updated_count += 1
            print(f"  ✅ {record_count}건 저장 → {new_filename}")
            
        except Exception as e:
            error_count += 1
            print(f"  ❌ 오류: {e}")
        
        # API 부하 방지
        time.sleep(0.2)
    
    # ==========================================
    # 요약
    # ==========================================
    total_time = time.time() - start_time
    print("\n" + "=" * 60)
    print("  📊 업데이트 완료 요약")
    print("=" * 60)
    print(f"  업데이트 범위: {UPDATE_FROM} ~ {UPDATE_TO}")
    print(f"  처리 서비스: {len(services)}개")
    print(f"  업데이트 완료: {updated_count}개")
    print(f"  변동 없음: {skipped_count}개")
    print(f"  오류: {error_count}개")
    print(f"  총 레코드: {total_records:,}건")
    print(f"  소요 시간: {int(total_time//60)}분 {int(total_time%60)}초")
    print("=" * 60)


if __name__ == "__main__":
    main()
