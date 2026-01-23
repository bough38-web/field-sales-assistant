import os
import unicodedata
import glob

print(f"CWD: {os.getcwd()}")
script_dir = os.path.dirname(os.path.abspath(__file__))
print(f"Script Dir: {script_dir}")

target_rel = os.path.join("reports", "premium_user_manual.html")
target_abs = os.path.join(script_dir, "reports", "premium_user_manual.html")

print(f"Checking Relative: {target_rel} -> {os.path.exists(target_rel)}")
print(f"Checking Absolute: {target_abs} -> {os.path.exists(target_abs)}")

reports_dir = os.path.join(script_dir, "reports")
if os.path.exists(reports_dir):
    print(f"Listing {reports_dir}:")
    for f in os.listdir(reports_dir):
        print(f" - {f!r} (NFC: {unicodedata.normalize('NFC', f)!r})")
        if "premium_user_manual.html" in f:
             print("   ^^^ MATCH FOUND via substring")
else:
    print("Reports dir not found")
