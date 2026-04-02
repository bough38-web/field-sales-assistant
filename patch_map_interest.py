"""
Add interest button to map visualizer

This script adds the triggerInterest function and button to the map interface.
Run this script to patch the map_visualizer.py file.
"""

import re

# Read the file
with open('src/map_visualizer.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add triggerInterest function after triggerVisit
trigger_visit_pattern = r'(window\.triggerVisit = function\(title, addr, key\) \{\{.*?\}\};)'
trigger_interest_code = '''
            
            // [FEATURE] Interest Trigger Function
            window.triggerInterest = function(title, addr, lat, lon) {{
                // No confirmation needed - just mark as interested
                var url = window.parent.location.href;
                var separator = url.includes('?') ? '&' : '?';
                var newUrl = url + separator + 'interest_action=true&title=' + encodeURIComponent(title) + '&addr=' + encodeURIComponent(addr) + '&lat=' + lat + '&lon=' + lon;
                
                // Append User Context
                var u_role = "{user_context.get('user_role', '')}";
                if(u_role) newUrl += '&user_role=' + encodeURIComponent(u_role);
                
                var u_branch = "{user_context.get('user_branch', '')}";
                if(u_branch && u_branch != 'None') newUrl += '&user_branch=' + encodeURIComponent(u_branch);
                
                var u_mgr = "{user_context.get('user_manager_name', '')}";
                if(u_mgr && u_mgr != 'None') newUrl += '&user_manager_name=' + encodeURIComponent(u_mgr);
                
                var u_code = "{user_context.get('user_manager_code', '')}";
                if(u_code && u_code != 'None') newUrl += '&user_manager_code=' + encodeURIComponent(u_code);
                
                var u_auth = "{user_context.get('admin_auth', 'false')}";
                newUrl += '&admin_auth=' + u_auth;

                window.parent.location.assign(newUrl);
            }};'''

if 'window.triggerInterest' not in content:
    content = re.sub(trigger_visit_pattern, r'\1' + trigger_interest_code, content, flags=re.DOTALL)
    print("✓ Added triggerInterest function")
else:
    print("⚠ triggerInterest function already exists")

# 2. Add interest button to InfoWindow (first occurrence)
infowindow_pattern = r"('<a href=\"javascript:void\(0\);\" onclick=\"triggerVisit\(.*?\)\" style=\"flex:1; background:#4CAF50.*?방문</a>' \+)"
interest_button = r"'<a href=\"javascript:void(0);\" onclick=\"triggerInterest(\\'' + item.title + '\\', \\'' + item.addr + '\\', ' + item.lat + ', ' + item.lon + ')\" style=\"flex:1; background:#FF9800; color:white; text-decoration:none; padding:8px 0; border-radius:4px; text-align:center; font-size:12px; font-weight:bold;\">⭐ 관심</a>' + \n                                    \1"

if '⭐ 관심' not in content:
    content = re.sub(infowindow_pattern, interest_button, content, count=1)
    print("✓ Added interest button to InfoWindow")
else:
    print("⚠ Interest button already exists in InfoWindow")

# 3. Add interest button to detail panel (around line 426)
detail_panel_pattern = r"(html \+= '<a href=\"javascript:void\(0\);\" onclick=\"triggerVisit\(.*?\)\" class=\"navi-btn\" style=\"background-color:#4CAF50.*?방문 처리</a>';)"
detail_interest_button = r"html += '<a href=\"javascript:void(0);\" onclick=\"triggerInterest(\\'' + item.title + '\\', \\'' + item.addr + '\\', ' + item.lat + ', ' + item.lon + ')\" class=\"navi-btn\" style=\"background-color:#FF9800; color:white;\">⭐ 관심 업체</a>';\n                    \1"

content = re.sub(detail_panel_pattern, detail_interest_button, content, count=1)
print("✓ Added interest button to detail panel")

# Write back
with open('src/map_visualizer.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n✅ Map visualizer patched successfully!")
print("관심 업체 버튼이 지도에 추가되었습니다.")
