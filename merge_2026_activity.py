#!/usr/bin/env python3
"""
LOCALDATA_ALL_CSV-3 → 2026년 3월 누적 총 활동대상.csv
=====================================================
195개 업종 fulldata에서:
  1) 최종수정시점이 2026년인 데이터만 필터링
  2) 핵심 컬럼(상호, 소재지주소 등)만 추출
  3) 하나의 CSV 파일로 병합
  4) LOCALDATA모음/ALL 3월말 병합/ 폴더에 저장

실행: python3 merge_2026_activity.py
"""
import csv
import os
import sys
import time
from pathlib import Path

# ==========================================
# 설정
# ==========================================
SRC_DIR = Path("/Users/heebonpark/Downloads/LOCALDATA_ALL_CSV-3")
DST_DIR = Path("/Users/heebonpark/Downloads/LOCALDATA모음/ALL 3월말 병합")
OUTPUT_FILE = DST_DIR / "2026년 3월 누적 총 활동대상.csv"

FILTER_YEAR = "2026"

# 최종수정시점 컬럼 후보
DATE_COL_NAMES = ["최종수정시점", "최종 수정시점", "DAT_UPDT_PNT"]

# 추출할 핵심 컬럼 (우선순위 순 - 존재하는 컬럼만 추출)
TARGET_COLUMNS = [
    "개방서비스명",       # 업종 구분
    "사업장명",           # 상호
    "영업상태명",         # 영업/폐업 등
    "상세영업상태명",     # 상세 상태
    "소재지전체주소",     # 소재지주소
    "도로명전체주소",     # 도로명주소
    "도로명우편번호",     # 우편번호
    "소재지전화",         # 전화번호
    "업태구분명",         # 업태
    "인허가일자",         # 인허가일
    "인허가취소일자",     # 취소일
    "폐업일자",           # 폐업일
    "휴업시작일자",       # 휴업시작
    "휴업종료일자",       # 휴업종료
    "최종수정시점",       # 최종수정
    "개방자치단체코드",   # 자치단체코드
]

# 출력 헤더에 "업종파일명" 컬럼 추가 (어떤 파일에서 왔는지 추적)
EXTRA_COL = "원본업종"


def find_col_index(header, candidates):
    """헤더에서 후보 컬럼명 중 매칭되는 인덱스 반환"""
    for i, col in enumerate(header):
        col_clean = col.strip().replace("\ufeff", "")
        for cand in candidates:
            if cand == col_clean or cand in col_clean:
                return i
    return -1


def find_target_col_indices(header):
    """헤더에서 타겟 컬럼들의 인덱스 맵 생성"""
    col_map = {}
    header_clean = [h.strip().replace("\ufeff", "") for h in header]
    for target in TARGET_COLUMNS:
        for i, h in enumerate(header_clean):
            if target == h or target in h:
                col_map[target] = i
                break
    return col_map


def extract_업종_from_filename(filename):
    """파일명에서 업종명 추출: fulldata_01_01_01_P_병원.csv → 병원"""
    name = filename.replace("fulldata_", "").replace(".csv", "")
    parts = name.split("_P_")
    if len(parts) >= 2:
        return parts[1]
    return name


def process_file(src_path, writer, output_cols):
    """파일 하나를 읽어 2026년 데이터의 핵심 컬럼만 추출하여 writer에 기록"""
    업종 = extract_업종_from_filename(src_path.name)
    encodings = ['cp949', 'utf-8', 'euc-kr', 'utf-8-sig']
    
    for enc in encodings:
        try:
            with open(src_path, 'r', encoding=enc, errors='strict') as f:
                reader = csv.reader(f)
                header = next(reader)
                
                # 최종수정시점 컬럼 찾기
                date_idx = find_col_index(header, DATE_COL_NAMES)
                if date_idx == -1:
                    return 0, "날짜컬럼없음"
                
                # 타겟 컬럼 인덱스 맵
                col_map = find_target_col_indices(header)
                
                filtered_count = 0
                for row in reader:
                    if len(row) <= date_idx:
                        continue
                    date_val = row[date_idx]
                    if FILTER_YEAR not in str(date_val):
                        continue
                    
                    # 핵심 컬럼 추출
                    out_row = []
                    for col_name in output_cols:
                        if col_name == EXTRA_COL:
                            out_row.append(업종)
                        elif col_name in col_map:
                            idx = col_map[col_name]
                            out_row.append(row[idx] if idx < len(row) else "")
                        else:
                            out_row.append("")
                    
                    writer.writerow(out_row)
                    filtered_count += 1
                
                return filtered_count, "OK"
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception as e:
            return 0, str(e)
    
    return 0, "인코딩실패"


def main():
    print("=" * 65)
    print("  LOCALDATA 195개 업종 → 2026년 3월 누적 총 활동대상")
    print(f"  필터: 최종수정시점에 '{FILTER_YEAR}' 포함")
    print("=" * 65)
    
    if not SRC_DIR.exists():
        print(f"❌ 소스 디렉토리 없음: {SRC_DIR}")
        return
    
    DST_DIR.mkdir(parents=True, exist_ok=True)
    
    csv_files = sorted(SRC_DIR.glob("fulldata_*.csv"))
    print(f"📁 소스: {SRC_DIR}")
    print(f"📁 대상: {OUTPUT_FILE}")
    print(f"📋 처리할 파일: {len(csv_files)}개\n")
    
    # 출력 컬럼 정의 (원본업종 + 타겟컬럼)
    output_cols = [EXTRA_COL] + TARGET_COLUMNS
    
    total_records = 0
    files_with_data = 0
    errors = 0
    start_time = time.time()
    
    with open(OUTPUT_FILE, 'w', encoding='cp949', newline='', errors='replace') as out_f:
        writer = csv.writer(out_f)
        writer.writerow(output_cols)
        
        for i, f in enumerate(csv_files):
            src_size_mb = f.stat().st_size / (1024 * 1024)
            업종 = extract_업종_from_filename(f.name)
            
            elapsed = time.time() - start_time
            eta = (elapsed / max(i, 1)) * (len(csv_files) - i) if i > 0 else 0
            
            sys.stdout.write(f"\r[{i+1:3d}/{len(csv_files)}] {업종:<30s} ({src_size_mb:>7.1f}MB) ETA:{int(eta//60)}m{int(eta%60):02d}s ... ")
            sys.stdout.flush()
            
            count, status = process_file(f, writer, output_cols)
            
            if count > 0:
                files_with_data += 1
                total_records += count
                print(f"✅ {count:,}건")
            elif status == "OK":
                print(f"⏭️ 0건")
            else:
                errors += 1
                print(f"❌ {status}")
    
    total_time = time.time() - start_time
    out_size_mb = OUTPUT_FILE.stat().st_size / (1024 * 1024) if OUTPUT_FILE.exists() else 0
    
    print(f"\n{'=' * 65}")
    print(f"  📊 완료 요약")
    print(f"{'=' * 65}")
    print(f"  원본 파일: {len(csv_files)}개")
    print(f"  데이터 있는 업종: {files_with_data}개")
    print(f"  총 레코드: {total_records:,}건")
    print(f"  출력 파일: {OUTPUT_FILE.name}")
    print(f"  파일 크기: {out_size_mb:.1f}MB")
    print(f"  오류: {errors}개")
    print(f"  소요 시간: {int(total_time//60)}분 {int(total_time%60)}초")
    print(f"{'=' * 65}")
    print(f"\n📂 결과: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
