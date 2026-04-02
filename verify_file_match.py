import glob
import os
import unicodedata

print("--- Listing Data Directory ---")
files = glob.glob("data/*.xlsx")
print(f"Found {len(files)} xlsx files.")

for f in files:
    print(f"File: {f}")
    print(f"Repr: {repr(f)}")
    print(f"NFC: {unicodedata.normalize('NFC', f)}")
    print(f"NFD: {unicodedata.normalize('NFD', f)}")
    
    if '20260119' in f:
        print("  ✅ Match '20260119'")
    else:
        print("  ❌ NO Match '20260119'")
        
    base = os.path.basename(f)
    if '20260119' in base:
        print("  ✅ Base Match '20260119'")
