#!/usr/bin/env python3
"""
LOCALDATA_UPDATE_0405_0415 데이터를 LOCALDATA_2026_ONLY.csv에 병합
컬럼명 매핑을 적용하여 기존 파일에 추가합니다.
"""
import csv
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE / "data"
MAIN_CSV = DATA_DIR / "LOCALDATA_2026_ONLY.csv"
UPDATE_DIR = BASE / "LOCALDATA_UPDATE_0405_0415"
OUTPUT_CSV = DATA_DIR / "LOCALDATA_2026_ONLY.csv"  # 덮어쓰기
BACKUP_CSV = DATA_DIR / "LOCALDATA_2026_ONLY_backup_0317.csv"

# UPDATE 파일 → MAIN 파일 컬럼 매핑
# UPDATE 컬럼명 : MAIN 컬럼명
COL_MAPPING = {
    "사업장명": "사업장명",
    "영업상태명": "영업상태명",
    "상세영업상태명": "상세영업상태명",
    "소재지전화번호": "소재지전화",
    "지번주소": "소재지전체주소",
    "도로명주소": "도로명전체주소",
    "도로명우편번호": "도로명우편번호",
    "인허가일자": "인허가일자",
    "인허가취소일자": "인허가취소일자",
    "폐업일자": "폐업일자",
    "휴업시작일자": "휴업시작일자",
    "휴업종료일자": "휴업종료일자",
    "최종수정시점": "최종수정시점",
    "개방자치단체코드": "개방자치단체코드",
    "소재지우편번호": "소재지우편번호",
    "좌표X": "좌표정보(x)",
    "좌표Y": "좌표정보(y)",
    "데이터갱신시점": "데이터갱신일자",
}


def extract_업종_from_filename(filename):
    """파일명에서 업종/서비스명 추출"""
    name = filename.replace(".csv", "")
    # (20260405~20260415)_ID_100_P_문화_외국인관광도시민박업_데이터_조회
    parts = name.split("_P_")
    if len(parts) >= 2:
        svc = parts[1].replace("_데이터_조회", "").replace("_", " ")
        return svc
    return name


def main():
    print("=" * 60)
    print("  LOCALDATA_2026_ONLY.csv 4월 데이터 병합")
    print("=" * 60)

    if not MAIN_CSV.exists():
        print(f"❌ 메인 CSV 없음: {MAIN_CSV}")
        return
    if not UPDATE_DIR.exists():
        print(f"❌ 업데이트 디렉토리 없음: {UPDATE_DIR}")
        return

    # 1. 메인 CSV 헤더 읽기
    print("📋 메인 CSV 헤더 읽는 중...")
    main_enc = 'utf-8'
    with open(MAIN_CSV, encoding=main_enc) as f:
        reader = csv.reader(f)
        main_header = next(reader)
    
    main_col_indices = {c.strip(): i for i, c in enumerate(main_header)}
    print(f"  메인 CSV 컬럼 수: {len(main_header)}")

    # 2. 백업 생성
    if not BACKUP_CSV.exists():
        print(f"💾 백업 생성: {BACKUP_CSV.name}")
        import shutil
        shutil.copy2(MAIN_CSV, BACKUP_CSV)

    # 3. 메인 CSV 기존 행 수 / 최대 날짜 확인
    existing_count = 0
    max_date = ""
    with open(MAIN_CSV, encoding=main_enc) as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        date_idx = main_col_indices.get("최종수정시점", -1)
        for row in reader:
            existing_count += 1
            if date_idx >= 0 and len(row) > date_idx:
                if row[date_idx] > max_date:
                    max_date = row[date_idx]
    
    print(f"  기존 레코드: {existing_count:,}건, 최신 날짜: {max_date}")

    # 4. 업데이트 파일 처리
    upd_files = sorted([f for f in os.listdir(UPDATE_DIR) if f.endswith('.csv')])
    print(f"\n🚀 업데이트 파일 {len(upd_files)}개 병합 시작...\n")

    added_total = 0
    files_added = 0

    with open(MAIN_CSV, 'a', encoding=main_enc, newline='') as out_f:
        writer = csv.writer(out_f)

        for fi, uf in enumerate(upd_files):
            업종 = extract_업종_from_filename(uf)
            upd_path = os.path.join(UPDATE_DIR, uf)

            for enc in ['cp949', 'utf-8']:
                try:
                    with open(upd_path, encoding=enc) as f:
                        reader = csv.reader(f)
                        upd_header = next(reader)
                        upd_header_clean = [h.strip() for h in upd_header]

                        # 매핑 테이블: upd_col_idx → main_col_idx
                        mapping = {}
                        for ui, uc in enumerate(upd_header_clean):
                            main_col_name = COL_MAPPING.get(uc, uc)
                            if main_col_name in main_col_indices:
                                mapping[ui] = main_col_indices[main_col_name]

                        # 개방서비스명 인덱스 (없으면 업종으로 채움)
                        svc_idx = main_col_indices.get("개방서비스명", -1)

                        count = 0
                        for row in reader:
                            out_row = [""] * len(main_header)
                            for upd_i, main_i in mapping.items():
                                if upd_i < len(row):
                                    out_row[main_i] = row[upd_i]
                            
                            # 개방서비스명이 비어있으면 업종명으로 채움
                            if svc_idx >= 0 and not out_row[svc_idx]:
                                out_row[svc_idx] = 업종

                            writer.writerow(out_row)
                            count += 1

                        if count > 0:
                            added_total += count
                            files_added += 1
                            print(f"  [{fi+1:3d}/{len(upd_files)}] {업종:<30s} +{count:,}건")
                        break
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    print(f"  [{fi+1:3d}] ❌ {업종}: {e}")
                    break

    # 5. 결과 확인
    final_count = 0
    final_max = ""
    with open(MAIN_CSV, encoding=main_enc) as f:
        reader = csv.reader(f)
        header = next(reader)
        date_idx = main_col_indices.get("최종수정시점", -1)
        for row in reader:
            final_count += 1
            if date_idx >= 0 and len(row) > date_idx:
                if row[date_idx] > final_max:
                    final_max = row[date_idx]

    final_size = MAIN_CSV.stat().st_size / (1024 * 1024)

    print(f"\n{'=' * 60}")
    print(f"  📊 병합 완료 요약")
    print(f"{'=' * 60}")
    print(f"  기존 레코드: {existing_count:,}건 (~ {max_date})")
    print(f"  추가 레코드: {added_total:,}건 ({files_added}개 파일)")
    print(f"  최종 레코드: {final_count:,}건")
    print(f"  최신 날짜: {final_max}")
    print(f"  파일 크기: {final_size:.1f}MB")
    print(f"  파일: {MAIN_CSV}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
