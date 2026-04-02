import pandas as pd
import os
import datetime
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_loader import load_and_process_data

def generate_static_report(zip_path, district_path):
    # 1. Load Data
    print("Loading Data...")
    df, _ = load_and_process_data(zip_path, district_path)
    
    if df is None or df.empty:
        print("No data found.")
        return

    # 2. Calculate Statistics
    total_count = len(df)
    active_count = len(df[df['영업상태명'].str.contains('영업|정상', na=False)])
    closed_count = len(df[df['영업상태명'].str.contains('폐업', na=False)])
    
    # Branch Stats
    branch_counts = df['관리지사'].value_counts()
    
    # Recent Activity (Last 30 Days)
    today = pd.Timestamp.now()
    month_ago = today - pd.Timedelta(days=30)
    
    # Safe date parsing
    df['reopen_dt'] = pd.to_datetime(df['재개업일자'], errors='coerce')
    df['modified_dt'] = pd.to_datetime(df['최종수정시점'], errors='coerce')
    
    recent_reopen = len(df[df['reopen_dt'] >= month_ago])
    recent_mod = len(df[df['modified_dt'] >= month_ago])

    # 3. Generate HTML
    from src import utils
    now_str = utils.get_now_kst().strftime("%Y-%m-%d %H:%M")
    
    branch_rows = ""
    for branch, count in branch_counts.items():
        if branch in ["미지정", "nan", ""]: continue
        
        b_df = df[df['관리지사'] == branch]
        b_active = len(b_df[b_df['영업상태명'].str.contains('영업|정상', na=False)])
        b_closed = len(b_df[b_df['영업상태명'].str.contains('폐업', na=False)])
        rate = (b_active / count * 100) if count > 0 else 0
        
        branch_rows += f"""
        <tr>
            <td>{branch}</td>
            <td style="text-align:right; font-weight:bold;">{count:,}</td>
            <td style="text-align:right; color:#2E7D32;">{b_active:,}</td>
            <td style="text-align:right; color:#d32f2f;">{b_closed:,}</td>
            <td style="text-align:right;">{rate:.1f}%</td>
        </tr>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <title>영업기회 파이프라인 현황 보고서</title>
        <style>
            body {{ font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; background: #f4f6f8; margin: 0; padding: 40px; color: #333; }}
            .container {{ max-width: 900px; margin: 0 auto; background: white; padding: 50px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }}
            h1 {{ color: #1565C0; border-bottom: 2px solid #1565C0; padding-bottom: 15px; margin-bottom: 40px; }}
            .summary-cards {{ display: flex; justify-content: space-between; margin-bottom: 40px; gap: 20px; }}
            .card {{ flex: 1; background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; border: 1px solid #e0e0e0; }}
            .card h3 {{ margin: 0 0 10px 0; color: #666; font-size: 14px; }}
            .card .value {{ font-size: 28px; font-weight: bold; color: #333; }}
            .card.active .value {{ color: #2E7D32; }}
            .card.closed .value {{ color: #d32f2f; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ padding: 12px; border-bottom: 1px solid #eee; text-align: left; }}
            th {{ background: #f1f3f5; font-weight: bold; color: #444; }}
            .badge {{ display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; background: #e3f2fd; color: #1565C0; }}
            .footer {{ margin-top: 50px; text-align: center; color: #888; font-size: 12px; border-top: 1px solid #eee; padding-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div style="display:flex; justify-content:space-between; align-items:flex-end; margin-bottom:20px;">
                <h1>📊 영업기회 파이프라인 현황 보고</h1>
                <div style="margin-bottom:45px; color:#666;">기준일: {now_str}</div>
            </div>

            <!-- Summary Statistics -->
            <div class="summary-cards">
                <div class="card">
                    <h3>총 관리 지점</h3>
                    <div class="value">{total_count:,}</div>
                    <div style="font-size:12px; color:#888; margin-top:5px;">전체 데이터베이스</div>
                </div>
                <div class="card active">
                    <h3>영업중 (Active)</h3>
                    <div class="value">{active_count:,}</div>
                    <div style="font-size:12px; color:#888; margin-top:5px;">유효 영업 기회</div>
                </div>
                <div class="card closed">
                    <h3>폐업 (Closed)</h3>
                    <div class="value">{closed_count:,}</div>
                    <div style="font-size:12px; color:#888; margin-top:5px;">관리/회수 대상</div>
                </div>
                <div class="card">
                    <h3>최근 변동 (30일)</h3>
                    <div class="value">{recent_reopen + recent_mod:,}</div>
                    <div style="font-size:12px; color:#888; margin-top:5px;">재개업 {recent_reopen}건 / 정보수정 {recent_mod}건</div>
                </div>
            </div>

            <!-- Branch Breakdown -->
            <h2>🏢 지사별 현황 상세</h2>
            <p style="color:#666; margin-bottom:20px;">각 권역별 관리 지사의 영업/폐업 비율 및 관리 수량 현황입니다.</p>
            <table>
                <thead>
                    <tr>
                        <th>관리지사</th>
                        <th style="text-align:right;">총 관리수</th>
                        <th style="text-align:right;">영업</th>
                        <th style="text-align:right;">폐업</th>
                        <th style="text-align:right;">영업율</th>
                    </tr>
                </thead>
                <tbody>
                    {branch_rows}
                </tbody>
            </table>

            <div style="margin-top:40px; padding:20px; background:#e8f5e9; border-radius:8px;">
                <h3 style="margin-top:0; color:#2E7D32;">💡 Insight & Action Plan</h3>
                <ul>
                    <li><strong>영업 기회</strong>: 전체 관리 지점 중 <strong>{active_count:,}개</strong>({(active_count/total_count*100):.1f}%)가 현재 영업 중입니다.</li>
                    <li><strong>최근 동향</strong>: 지난 30일간 <strong>{recent_reopen}개</strong>의 업소가 재개업했습니다. 우선 방문을 권장합니다.</li>
                    <li><strong>집중 관리 지역</strong>: {branch_counts.index[0]}가 가장 많은 잠재 고객을 보유하고 있습니다.</li>
                </ul>
            </div>

            <div class="footer">
                Field Sales Assistant System | Generated by Auto-Report Module
            </div>
        </div>
    </body>
    </html>
    """
    
    output_path = "reports/dashboard_snapshot_realtime.html"
    os.makedirs("reports", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"Report generated: {os.path.abspath(output_path)}")

if __name__ == "__main__":
    # Auto-detect sources from data folder (simple logic)
    import glob
    # Need to mimic app.py logic roughly or use known paths
    # Assuming paths from context or hardcoded for this utility
    # User has specific paths in mind usually, but we'll try to find them.
    
    # We will try to find the standard files
    zip_files = glob.glob("전체분/*.zip") + glob.glob("*.zip")
    dist_files = glob.glob("data/*.xlsx")
    
    if zip_files:
        z = zip_files[0]
        d = dist_files[0] if dist_files else None
        generate_static_report(z, d)
    else:
        print("Could not find data files automatically.")
