import pandas as pd
import glob
import os

# Find properly
d = "data"
files = glob.glob(os.path.join(d, "*.xlsx"))
files.sort(key=os.path.getmtime, reverse=True)
target = files[0]

print(f"Analyzing File: {target}")

df = pd.read_excel(target)
print(f"Columns: {list(df.columns)}")

addr_col = '주소'
if '주소' not in df.columns:
    if '주소시' in df.columns:
        # Create full address for check
        df['주소'] = df[['주소시', '주소군구', '주소동']].astype(str).agg(' '.join, axis=1)
        addr_col = '주소'
    else:
        # Try finding anything with '주소'
        potential = [c for c in df.columns if '주소' in c]
        if potential:
            addr_col = potential[0]
            print(f"Using '{addr_col}' as Address column")
        else:
             print("Cannot find Address column")
             exit()

# Group by Branch 
branches = df['관리지사'].dropna().unique()

# Check specifically for Seong Jin-su
target_mgr = "성진수"
mgr_rows = df[df['SP담당'] == target_mgr]
print(f"\n[{target_mgr}] Found {len(mgr_rows)} rows:")
print(mgr_rows[['관리지사', '주소', 'SP담당']].head(10))

# Check unique branches for this manager
mgr_branches = mgr_rows['관리지사'].unique()
print(f"Branches for {target_mgr}: {mgr_branches}")

# Check for duplicate addresses in the whole file
if '주소' in df.columns:
    addr_counts = df['주소'].value_counts()
    dupes = addr_counts[addr_counts > 1]
    print(f"\nTotal Duplicate Addresses: {len(dupes)}")
    if len(dupes) > 0:
        print("Sample duplicates:")
        print(dupes.head(5))
        
        # Check if any of Seong Jin-su's addresses are duplicates
        s_addrs = mgr_rows['주소'].tolist()
        for addr in s_addrs:
            if addr in dupes.index:
                print(f"WARNING: {target_mgr} address '{addr}' is duplicated {dupes[addr]} times!")
                # Show who else shares this address
                shares = df[df['주소'] == addr]
                print(shares[['관리지사', 'SP담당']])

