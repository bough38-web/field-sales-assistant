#!/usr/bin/env python3
"""
LOCALDATA_ALL_CSV-3 → LOCALDATA모음/ALL 3월말 병합
195개 업종 fulldata에서 2026년 최종수정시점 데이터만 필터링하여 저장
"""
import csv
import os
import sys
import time
from pathlib import Path

# 소스: LOCALDATA_ALL_CSV-3
SRC_DIR = Path("/Users/heebonpark/Downloads/LOCALDATA_ALL_CSV-3")
# 대상: LOCALDATA모음/ALL 3월말 병합
DST_DIR = Path("/Users/heebonpark/Downloads/LOCALDATA모음/ALL 3월말 병합")

# 필터 조건: 최종수정시점에 "2026" 포함
FILTER_YEAR = "2026"

# 최종수정시점으로 사용될 수 있는 컬럼명들
DATE_COL_CANDIDATES = ["최종수정시점", "최종 수정시점", "DAT_UPDT_PNT"]


def find_date_col_index(header):
    """헤더에서 최종수정시점 컬럼 인덱스 찾기"""
    for i, col in enumerate(header):
        col_clean = col.strip().replace("\ufeff", "")
        for candidate in DATE_COL_CANDIDATES:
            if candidate in col_clean:
                return i
    return -1


def process_file(src_path, dst_path):
    """한 파일을 읽어 2026년 데이터만 필터링하여 저장"""
    # 인코딩 시도 순서
    encodings = ['cp949', 'utf-8', 'euc-kr', 'utf-8-sig']
    
    for enc in encodings:
        try:
            with open(src_path, 'r', encoding=enc, errors='strict') as f:
                reader = csv.reader(f)
                header = next(reader)
                
                date_col_idx = find_date_col_index(header)
                if date_col_idx == -1:
                    # 최종수정시점 컬럼이 없으면 전체 복사
                    return _copy_whole_file(src_path, dst_path, enc), "전체복사(날짜컬럼없음)"
                
                # 필터링하면서 저장
                filtered_count = 0
                total_count = 0
                
                with open(dst_path, 'w', encoding='cp949', newline='', errors='replace') as out_f:
                    writer = csv.writer(out_f)
                    writer.writerow(header)
                    
                    for row in reader:
                        total_count += 1
                        if len(row) > date_col_idx:
                            date_val = row[date_col_idx]
                            if FILTER_YEAR in str(date_val):
                                writer.writerow(row)
                                filtered_count += 1
                
                return filtered_count, f"{filtered_count:,}/{total_count:,}"
                
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception as e:
            return 0, f"오류: {e}"
    
    return 0, "인코딩 실패"


def _copy_whole_file(src_path, dst_path, enc):
    """날짜 컬럼이 없는 경우 전체 복사"""
    count = 0
    with open(src_path, 'r', encoding=enc, errors='replace') as f:
        reader = csv.reader(f)
        header = next(reader)
        with open(dst_path, 'w', encoding='cp949', newline='', errors='replace') as out_f:
            writer = csv.writer(out_f)
            writer.writerow(header)
            for row in reader:
                writer.writerow(row)
                count += 1
    return count


def main():
    print("=" * 65)
    print("  LOCALDATA_ALL_CSV → ALL 3월말 병합 (2026년 필터)")
    print(f"  필터 조건: 최종수정시점에 '{FILTER_YEAR}' 포함")
    print("=" * 65)
    
    if not SRC_DIR.exists():
        print(f"❌ 소스 디렉토리 없음: {SRC_DIR}")
        return
    
    DST_DIR.mkdir(parents=True, exist_ok=True)
    print(f"📁 소스: {SRC_DIR}")
    print(f"📁 대상: {DST_DIR}\n")
    
    csv_files = sorted(SRC_DIR.glob("fulldata_*.csv"))
    print(f"📋 처리할 파일: {len(csv_files)}개\n")
    
    processed = 0
    total_filtered = 0
    errors = 0
    start_time = time.time()
    
    for i, f in enumerate(csv_files):
        src_size_mb = f.stat().st_size / (1024 * 1024)
        short_name = f.name.replace("fulldata_", "").replace(".csv", "")
        
        elapsed = time.time() - start_time
        eta = (elapsed / max(i, 1)) * (len(csv_files) - i) if i > 0 else 0
        
        sys.stdout.write(f"\r[{i+1:3d}/{len(csv_files)}] {short_name[:40]:<40s} ({src_size_mb:>7.1f}MB) ... ")
        sys.stdout.flush()
        
        dst_file = DST_DIR / f.name
        
        try:
            count, detail = process_file(f, dst_file)
            
            if isinstance(count, int) and count > 0:
                dst_size_mb = dst_file.stat().st_size / (1024 * 1024)
                print(f"✅ {detail} → {dst_size_mb:.1f}MB")
                total_filtered += count
                processed += 1
            elif isinstance(count, int) and count == 0:
                # 2026년 데이터가 없으면 빈 파일 제거
                if dst_file.exists():
                    dst_file.unlink()
                print(f"⏭️ 2026년 데이터 없음")
            else:
                print(f"❌ {detail}")
                errors += 1
        except Exception as e:
            print(f"❌ {e}")
            errors += 1
    
    total_time = time.time() - start_time
    
    # 최종 결과 파일 수 확인
    result_files = list(DST_DIR.glob("fulldata_*.csv"))
    total_dst_size = sum(f.stat().st_size for f in result_files) / (1024 * 1024 * 1024)
    
    print(f"\n{'=' * 65}")
    print(f"  📊 완료 요약")
    print(f"{'=' * 65}")
    print(f"  원본 파일: {len(csv_files)}개")
    print(f"  생성 파일: {len(result_files)}개 (2026년 데이터 있는 파일)")
    print(f"  총 필터 레코드: {total_filtered:,}건")
    print(f"  총 용량: {total_dst_size:.2f}GB")
    print(f"  오류: {errors}개")
    print(f"  소요 시간: {int(total_time//60)}분 {int(total_time%60)}초")
    print(f"  대상 폴더: {DST_DIR}")
    print(f"{'=' * 65}")


if __name__ == "__main__":
    main()
