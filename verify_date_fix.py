import pandas as pd
import numpy as np

# Simulate data
df = pd.DataFrame({
    '최종수정시점': ['2026-03-27 10:00:00', '2026-04-01 05:00:00', '2026-04-15 22:00:00']
})

# 1. Standardization (The fix I applied in app.py)
temp_dt = pd.to_datetime(df['최종수정시점'], errors='coerce', utc=True)
df['최종수정시점'] = temp_dt.dt.tz_convert('Asia/Seoul').dt.tz_localize(None)

print(f"Standardized Dtypes:\n{df.dtypes}")
print(f"Data:\n{df}")

# 2. Filter Logic (The fix I applied in app.py)
g_start = '2026-03-01'
g_end = '2026-04-30'

ts_start = pd.Timestamp(g_start).normalize()
ts_end = pd.Timestamp(g_end).normalize() + pd.Timedelta(hours=23, minutes=59, seconds=59)

mask = (df['최종수정시점'] >= ts_start) & (df['최종수정시점'] <= ts_end)
filtered_df = df[mask]

print(f"\nFilter range: {ts_start} ~ {ts_end}")
print(f"Filtered Count: {len(filtered_df)}")
assert len(filtered_df) == 3, "Should match all 3 records"

# Test narrow range (March 27)
g_start2 = '2026-03-27'
g_end2 = '2026-03-28'
ts_start2 = pd.Timestamp(g_start2).normalize()
ts_end2 = pd.Timestamp(g_end2).normalize() + pd.Timedelta(hours=23, minutes=59, seconds=59)
mask2 = (df['최종수정시점'] >= ts_start2) & (df['최종수정시점'] <= ts_end2)
print(f"Narrow Filtered Count: {len(df[mask2])}")
assert len(df[mask2]) == 1, "Should only match the March 27 record"

print("\n✅ Verification Successful: Naive KST comparison is robust.")
