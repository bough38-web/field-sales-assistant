import streamlit as st
import pandas as pd
import json
import streamlit.components.v1 as components
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster

def render_kakao_map(map_df, kakao_key):
    """
    Renders a Kakao Map using HTML/JS injection.
    """
    # 1. Ensure Coordinates are Numeric
    map_df['lat'] = pd.to_numeric(map_df['lat'], errors='coerce')
    map_df['lon'] = pd.to_numeric(map_df['lon'], errors='coerce')
    
    # 2. Filter Valid
    display_df = map_df.dropna(subset=['lat', 'lon']).copy()
    
    # Limit for performance
    limit = 3000
    if len(display_df) > limit:
        st.warning(f"⚠️ 데이터가 많아 상위 {limit:,}개만 지도에 표시합니다.")
        display_df = display_df.head(limit)
        
    # [FIX] Center Calculation: Default to Seoul (Sudo-gwon)
    # User requested "Start at Sudo-gwon". 
    # If we have data, we usually center on it. But if user insists on fixed start, we can provide it.
    # However, usually centering on data is best. 
    # If data is empty -> Seoul.
    
    if not display_df.empty:
        center_lat = display_df['lat'].mean()
        center_lon = display_df['lon'].mean()
    else:
        # Default Center (Seoul City Hall)
        center_lat, center_lon = 37.5665, 126.9780
        
    # Prepare JSON for JS
    # Escape helper
    def clean_str(s):
        return str(s).replace('"', '').replace("'", "").replace('\n', ' ')

    display_df['title'] = display_df['사업장명'].apply(clean_str)
    display_df['addr'] = display_df['소재지전체주소'].fillna('').apply(clean_str)
    display_df['tel'] = display_df['소재지전화'].fillna('')
    display_df['status'] = display_df['영업상태명'].fillna('')
    
    # Date Formatting
    def format_date(d):
        if pd.isna(d): return ''
        s = str(d).replace('.0', '').strip()[:10]
        return s
    
    display_df['close_date'] = display_df['폐업일자'].apply(format_date) if '폐업일자' in display_df.columns else ''
    display_df['permit_date'] = display_df['인허가일자'].apply(format_date) if '인허가일자' in display_df.columns else ''
    display_df['reopen_date'] = display_df['재개업일자'].apply(format_date) if '재개업일자' in display_df.columns else ''
    display_df['modified_date'] = display_df['최종수정시점'].apply(format_date) if '최종수정시점' in display_df.columns else ''
    
    # [FEATURE] Business Type
    display_df['biz_type'] = display_df['업태구분명'].fillna('') if '업태구분명' in display_df.columns else ''
    
    # [FEATURE] Branch & Manager info
    display_df['branch'] = display_df['관리지사'].fillna('') if '관리지사' in display_df.columns else ''
    display_df['manager'] = display_df['SP담당'].fillna('') if 'SP담당' in display_df.columns else ''
    
    # [FEATURE] Large Area Flag (>= 100py approx 330m2)
    def check_large(row):
        try:
            val = float(row.get('소재지면적', 0))
            # If 0, try '총면적' (rarely used but possible fallback)
            # Actually just stick to 소재지면적 as primary
            if val >= 330.0: return True
        except: pass
        return False
        
    display_df['is_large'] = display_df.apply(check_large, axis=1)
    
    map_data = display_df[['lat', 'lon', 'title', 'status', 'addr', 'tel', 'close_date', 'permit_date', 'reopen_date', 'modified_date', 'biz_type', 'branch', 'manager', 'is_large']].to_dict(orient='records')
    json_data = json.dumps(map_data, ensure_ascii=False)
    
    st.markdown('<div style="background-color: #e3f2fd; border-left: 5px solid #2196F3; padding: 10px; margin-bottom: 10px; border-radius: 4px;"><small><b>Tip:</b> 왼쪽 지도에서 마커를 선택하면 오른쪽에서 <b>상세 위치</b>와 <b>정보</b>를 확인할 수 있습니다.</small></div>', unsafe_allow_html=True)

    map_css = '''
        html, body { width:100%; height:100%; margin:0; padding:0; overflow:hidden; font-family: 'Pretendard', sans-serif; } 
        * { box-sizing: border-box; }
        
        #container { 
            display: grid; 
            grid-template-columns: 65% 35%; /* Fixed ratio */
            width: 100%; 
            height: 100%; 
        }
        
        /* Left: Overview Map */
        #map-overview { 
            width: 100%; 
            height: 100%; 
            position: relative; 
            border-right: 2px solid #ddd; 
        }
        
        /* Right: Detail Panel */
        #right-panel { 
            width: 100%; 
            height: 100%; 
            display: grid; 
            grid-template-rows: 40% 60%; /* Split vertically */
            background: white; 
        }
        
        #map-detail { 
            width: 100%; 
            height: 100%; 
            border-bottom: 2px solid #eee; 
            background: #f0f0f0; 
            position: relative; 
        }
        
        #info-panel { 
            width: 100%; 
            height: 100%; 
            overflow-y: auto; 
            padding: 0; 
        }
        
        /* Info Content Styles */
        .sb-header { padding: 15px; border-bottom: 1px solid #eee; background: #fafafa; }
        .sb-title { margin: 0; font-size: 16px; font-weight: bold; color: #333; display: flex; align-items: center; justify-content: space-between; }
        .sb-body { padding: 15px; }
        .sb-placeholder { text-align: center; margin-top: 60px; color: #aaa; }
        
        /* Details Table */
        .info-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        .info-table td { padding: 8px 0; border-bottom: 1px solid #f9f9f9; font-size: 13px; }
        .info-label { color: #888; width: 70px; font-weight: 500; }
        .info-value { color: #333; font-weight: 500; }
        
        .status-badge { display:inline-block; padding:3px 8px; border-radius:4px; color:white; font-size:12px; font-weight:bold; }
        .navi-btn { display:block; width:100%; padding:12px 0; background-color:#FEE500; color:#3C1E1E; text-decoration:none; border-radius:6px; font-weight:bold; font-size:14px; text-align:center; margin-top:20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .navi-btn:hover { background-color:#FDD835; }
        
        .detail-label { position: absolute; top: 10px; left: 10px; z-index: 10; background: rgba(255,255,255,0.9); padding: 5px 10px; font-size: 12px; font-weight: bold; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.2); pointer-events: none; }
    '''

    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8"/>
        <style>{map_css}</style>
    </head>
    <body>
        <div id="container">
            <div id="map-overview">
                <div class="detail-label">🗺️ 전체 지도 (이곳을 클릭하세요)</div>
            </div>
            <div id="right-panel">
                <div id="map-detail">
                    <div class="detail-label">🔍 상세 위치 (확대됨)</div>
                </div>
                <div id="info-panel">
                     <div class="sb-header">
                        <h3 class="sb-title">상세 정보</h3>
                    </div>
                    <div class="sb-body" id="info-content">
                        <div class="sb-placeholder">
                            <div style="font-size: 40px; margin-bottom: 10px;">👈</div>
                            좌측 지도에서 마커를 선택하면<br>상세 위치와 정보가 표시됩니다.
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={kakao_key}&libraries=services,clusterer,drawing"></script>
        <script>
            // --- 1. Map Overview ---
            var mapContainer1 = document.getElementById('map-overview'), 
                mapOption1 = {{ 
                    center: new kakao.maps.LatLng({center_lat}, {center_lon}), 
                    level: 9 
                }};
            var mapOverview = new kakao.maps.Map(mapContainer1, mapOption1);
            
            // --- 2. Map Detail ---
            var mapContainer2 = document.getElementById('map-detail'), 
                mapOption2 = {{ 
                    center: new kakao.maps.LatLng({center_lat}, {center_lon}), 
                    level: 3 
                }};
            var mapDetail = new kakao.maps.Map(mapContainer2, mapOption2);
            mapDetail.setDraggable(true); 
            mapDetail.setZoomable(true);
            
            // [FIX] Force Relayout to ensure maps render correctly in split view
            setTimeout(function() {{
                mapOverview.relayout();
                mapDetail.relayout();
                mapOverview.setCenter(new kakao.maps.LatLng({center_lat}, {center_lon}));
                mapDetail.setCenter(new kakao.maps.LatLng({center_lat}, {center_lon}));
            }}, 500);

            // --- 3. Data & Clusterer ---
            var clusterer = new kakao.maps.MarkerClusterer({{
                map: mapOverview, 
                averageCenter: true, 
                minLevel: 10 
            }});
            
            var data = {json_data};
            var markers = [];
            
            // Marker Details
            var imgSize = new kakao.maps.Size(35, 35); 
            var openImg = "https://maps.google.com/mapfiles/ms/icons/blue-dot.png";
            var closeImg = "https://maps.google.com/mapfiles/ms/icons/red-dot.png";
            var largeImg = "https://maps.google.com/mapfiles/ms/icons/purple-dot.png";
            
            var bounds = new kakao.maps.LatLngBounds();
            var detailMarker = null; // Single marker for detail map
            
            data.forEach(function(item) {{
                var isOpen = item.status.includes('영업') || item.status.includes('정상');
                var imgSrc = item.is_large ? largeImg : (isOpen ? openImg : closeImg);
                
                var markerImage = new kakao.maps.MarkerImage(imgSrc, imgSize);
                var markerPos = new kakao.maps.LatLng(item.lat, item.lon);
                
                var marker = new kakao.maps.Marker({{
                    position: markerPos,
                    image: markerImage
                }});
                
                bounds.extend(markerPos);
                
                // Click Event
                kakao.maps.event.addListener(marker, 'click', function() {{
                    // Sync Detail Map
                    var moveLatLon = new kakao.maps.LatLng(item.lat, item.lon);
                    
                    // 1. Pan Overview slightly? No, keep context.
                    // mapOverview.panTo(moveLatLon); 
                    
                    // 2. Update Detail Map
                    mapDetail.setCenter(moveLatLon);
                    mapDetail.setLevel(1); // Very Close Zoom
                    
                    // Update Detail Marker
                    if (detailMarker) detailMarker.setMap(null);
                    
                    // Creates a larger marker for detail view
                    var detailImgSize = new kakao.maps.Size(45, 45);
                    var detailImg = new kakao.maps.MarkerImage(imgSrc, detailImgSize);
                    
                    detailMarker = new kakao.maps.Marker({{
                        position: moveLatLon,
                        image: detailImg,
                        map: mapDetail
                    }});
                    
                    // 3. Update Info Panel
                    var badgeColor = item.is_large ? "#9C27B0" : (isOpen ? "#2196F3" : "#F44336");
                    
                    var html = '<div style="margin-bottom:20px;">' +
                               '<h2 style="margin:0 0 8px 0; color:#222; font-size:20px; line-height:1.4;">' + item.title + '</h2>' +
                               '<span class="status-badge" style="background-color:' + badgeColor + ';">' + item.status + '</span>' +
                               (item.is_large ? '<span class="status-badge" style="background-color:#673AB7; margin-left:5px;">🏢 대형시설</span>' : '') +
                               '</div>';
                               
                    html += '<table class="info-table">';
                    if(item.branch) html += '<tr><td class="info-label">관리지사</td><td class="info-value">' + item.branch + '</td></tr>';
                    if(item.manager) html += '<tr><td class="info-label">담당자</td><td class="info-value">' + item.manager + '</td></tr>';
                    html += '<tr><td class="info-label">업종</td><td class="info-value">' + (item.biz_type || '-') + '</td></tr>';
                    html += '<tr><td class="info-label">주소</td><td class="info-value">' + item.addr + '</td></tr>';
                    if(item.tel) html += '<tr><td class="info-label">전화번호</td><td class="info-value">' + item.tel + '</td></tr>';
                    html += '<tr><td colspan="2" style="height:10px;"></td></tr>'; // Spacer
                    
                    if(item.permit_date) html += '<tr><td class="info-label">인허가일</td><td class="info-value">' + item.permit_date + '</td></tr>';
                    if(item.close_date) html += '<tr><td class="info-label" style="color:#D32F2F;">폐업일자</td><td class="info-value" style="color:#D32F2F;">' + item.close_date + '</td></tr>';
                    if(item.reopen_date) html += '<tr><td class="info-label" style="color:#1976D2;">재개업일</td><td class="info-value">' + item.reopen_date + '</td></tr>';
                    if(item.modified_date) html += '<tr><td class="info-label">정보수정</td><td class="info-value">' + item.modified_date + '</td></tr>';
                    html += '</table>';
                    
                    html += '<a href="https://map.kakao.com/link/to/' + item.title + ',' + item.lat + ',' + item.lon + '" target="_blank" class="navi-btn">🚗 카카오내비 길찾기</a>';
                    
                    document.getElementById('info-content').innerHTML = html;
                }});
                
                markers.push(marker);
            }});
            
            clusterer.addMarkers(markers);
            
            if (markers.length > 0) {{
                mapOverview.setBounds(bounds);
            }}
            
            // Standard Zoom Control for Overview
            var zoomControl = new kakao.maps.ZoomControl();
            mapOverview.addControl(zoomControl, kakao.maps.ControlPosition.RIGHT);
            
            // Location Button (Left Map Only)
            var locBtn = document.createElement('div');
            locBtn.innerHTML = '🎯 내 위치';
            locBtn.style.cssText = 'position:absolute;bottom:30px;right:10px;z-index:999;background:white;padding:8px 12px;border-radius:4px;border:1px solid #ccc;cursor:pointer;font-weight:bold;box-shadow:0 1px 3px rgba(0,0,0,0.2);';
            locBtn.onclick = function() {{
                if (navigator.geolocation) {{
                    navigator.geolocation.getCurrentPosition(function(position) {{
                        var lat = position.coords.latitude; 
                        var lon = position.coords.longitude; 
                        var locPosition = new kakao.maps.LatLng(lat, lon); 
                        
                        mapOverview.setCenter(locPosition);
                        mapOverview.setLevel(4);
                        
                        // Marker on Overview
                        var imageSrc = 'https://t1.daumcdn.net/localimg/localimages/07/mapapidoc/marker_red.png', 
                            imageSize = new kakao.maps.Size(64, 69), 
                            imageOption = {{offset: new kakao.maps.Point(27, 69)}}; 
                        var marker = new kakao.maps.Marker({{ position: locPosition, image: new kakao.maps.MarkerImage(imageSrc, imageSize, imageOption) }}); 
                        marker.setMap(mapOverview); 
                        
                        // Also update Detail Map to My Location?
                        mapDetail.setCenter(locPosition);
                        mapDetail.setLevel(2);
                        new kakao.maps.Marker({{ position: locPosition, map: mapDetail }});
                        
                        document.getElementById('info-content').innerHTML = '<div class="sb-placeholder">📍 현재 내 위치입니다.</div>';
                        
                    }}, function(err) {{
                        alert('위치 실패: ' + err.message);
                    }});
                }}
            }};
            document.getElementById('map-overview').appendChild(locBtn);
            
        </script>
    </body>
    </html>
    '''
    
    import hashlib
    data_hash = hashlib.md5(json_data.encode('utf-8')).hexdigest()
    
    components.html(html_content, height=850, key=f"kakao_map_dual_{data_hash}")

def render_folium_map(map_df):
    """
    Renders a Folium Map.
    """
    st.info("⚠️ 카카오 키 미설정 -> 기본 지도(OpenStreetMap) 사용")
    
    # 1. Ensure Coordinates
    map_df['lat'] = pd.to_numeric(map_df['lat'], errors='coerce')
    map_df['lon'] = pd.to_numeric(map_df['lon'], errors='coerce')
    
    total_rows = len(map_df)
    valid_rows = map_df.dropna(subset=['lat', 'lon'])
    n_valid = len(valid_rows)
    
def render_folium_map(display_df):
    """
    Render Map using Leaflet (Client-Side) to prevent Streamlit reruns (flashing).
    Layout: Split View (65% Map, 35% Detail)
    """
    if display_df.empty:
        st.warning("표시할 데이터가 없습니다.")
        return

    # 1. Data Preparation & Date Formatting
    # Create a copy to modify for display
    map_data_df = display_df.copy()
    
    def format_date_simple(d):
        if pd.isna(d) or str(d) == 'NaT': return '-'
        return str(d)[:10] # YYYY-MM-DD
        
    # Apply formatting
    if '인허가일자' in map_data_df.columns: map_data_df['permit_date'] = map_data_df['인허가일자'].apply(format_date_simple)
    if '폐업일자' in map_data_df.columns: map_data_df['close_date'] = map_data_df['폐업일자'].apply(format_date_simple)
    if '최종수정시점' in map_data_df.columns: map_data_df['modified_date'] = map_data_df['최종수정시점'].apply(format_date_simple)
    if '재개업일자' in map_data_df.columns: map_data_df['reopen_date'] = map_data_df['재개업일자'].apply(format_date_simple)
    
    # Fill defaults
    map_data_df['title'] = map_data_df['사업장명'].fillna('상호미상')
    map_data_df['status'] = map_data_df['영업상태명'].fillna("-")
    map_data_df['addr'] = map_data_df['소재지전체주소'].fillna("-")
    map_data_df['tel'] = map_data_df['소재지전화'].fillna("").replace('nan', '')
    map_data_df['branch'] = map_data_df['관리지사'].fillna("-")
    map_data_df['manager'] = map_data_df['SP담당'].fillna("-")
    map_data_df['biz_type'] = map_data_df['업태구분명'].fillna("-")
    
    # Check for '평수' or calculate it (Assuming 1 '소재지면적' unit approx to meters, usually m2)
    # If logic exists elsewhere, reuse. Here we approximate if '평수' column exists.
    if '평수' in map_data_df.columns:
        map_data_df['area_py'] = map_data_df['평수'].fillna(0).astype(float).round(1)
    else:
        map_data_df['area_py'] = 0.0
        
    # Large Area Flag for Coloring
    map_data_df['is_large'] = map_data_df['area_py'] >= 100.0

    # Convert to Dict for JSON
    cols_to_keep = ['lat', 'lon', 'title', 'status', 'addr', 'tel', 
                    'permit_date', 'close_date', 'modified_date', 'reopen_date', 
                    'branch', 'manager', 'biz_type', 'area_py', 'is_large']
                    
    # Ensure cols exist
    for c in cols_to_keep:
        if c not in map_data_df.columns: map_data_df[c] = ""
        
    map_data = map_data_df[cols_to_keep].to_dict(orient='records')
    json_data = json.dumps(map_data, ensure_ascii=False)
    
    # Center calculation
    avg_lat = display_df['lat'].mean()
    avg_lon = display_df['lon'].mean()
    
    st.markdown('<div style="background-color: #e3f2fd; border-left: 5px solid #2196F3; padding: 10px; margin-bottom: 10px; border-radius: 4px;"><small><b>Tip:</b> 지도 우측 상단의 <b>레이어 버튼(📚)</b>을 눌러 <b>브이월드(VWorld)</b>로 배경을 변경할 수 있습니다.</small></div>', unsafe_allow_html=True)
    
    leaflet_template = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css" />
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <!-- Marker Cluster CSS -->
        <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.css" />
        <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.Default.css" />
        
        <style>
            html, body {{ margin: 0; padding: 0; height: 100%; width: 100%; font-family: 'Pretendard', sans-serif; overflow: hidden; }}
            * {{ box-sizing: border-box; }}
            
            #container {{ 
                display: grid; 
                grid-template-columns: 65% 35%; 
                grid-template-rows: 100%;
                width: 100%; 
                height: 100%; 
            }}
            
            #map-container {{ 
                width: 100%; 
                height: 100%; 
                border-right: 2px solid #ddd;
                position: relative;
                z-index: 1; 
            }}
            
            #right-panel {{ 
                width: 100%; 
                height: 100%; 
                background: white; 
                display: flex; 
                flex-direction: column;
                overflow-y: auto;
            }}
            
            /* Responsive Design for Mobile */
            @media (max-width: 768px) {{
                #container {{
                    grid-template-columns: 100%;
                    grid-template-rows: 55% 45%; /* Map top, Details bottom */
                }}
                
                #map-container {{
                    border-right: none;
                    border-bottom: 2px solid #ddd;
                }}
                
                #right-panel {{
                    border-top: 4px solid #2E7D32; /* Visual cue for separation */
                }}
                
                .detail-card {{
                    margin: 10px; /* Smaller margin on mobile */
                    padding: 15px; /* Compact padding */
                }}
                
                .detail-title {{
                    font-size: 18px; /* Slightly smaller title */
                }}
            }}
            
            /* Detail Card Styles */
            .detail-card {{
                margin: 20px;
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 12px;
                padding: 24px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.05);
            }}
            .detail-header {{
                margin-bottom: 20px;
                border-bottom: 2px solid #f5f5f5;
                padding-bottom: 15px;
            }}
            .detail-title {{
                font-size: 20px;
                font-weight: 700;
                color: #1a1a1a;
                margin: 0 0 8px 0;
            }}
            .detail-badge {{
                display: inline-block;
                padding: 4px 10px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
                color: white;
            }}
            .detail-row {{
                display: flex;
                margin-bottom: 8px;
                font-size: 14px;
            }}
            .detail-label {{
                min-width: 70px;
                color: #757575;
                font-weight: 500;
            }}
            .detail-value {{
                font-weight: 600;
                color: #333;
                flex: 1;
            }}
            .detail-meta {{
                margin-top: 20px;
                padding-top: 15px;
                border-top: 1px solid #f0f0f0;
                font-size: 13px;
                color: #909090;
                line-height: 1.6;
            }}
            .navi-btn {{ 
                display:block; width:100%; padding:12px 0; 
                background-color:#FEE500; color:#3C1E1E; 
                text-decoration:none; border-radius:8px; 
                font-weight:bold; font-size:14px; text-align:center; 
                margin-top:20px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .navi-btn:hover {{ background-color:#FDD835; }}
            
            .placeholder-box {{
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 100%;
                color: #bdbdbd;
                padding: 20px;
                text-align: center;
            }}
            
            /* Custom CSS Icons */
            .custom-marker {{
                display: flex;
                align-items: center;
                justify-content: center;
                width: 30px;
                height: 30px;
                border-radius: 50%;
                color: white;
                box-shadow: 0 2px 5px rgba(0,0,0,0.3);
                border: 2px solid white;
            }}
            .custom-marker i {{
                font-size: 14px;
            }}
            .marker-green {{ background-color: #2E7D32; }}
            .marker-red {{ background-color: #d32f2f; }}
            .marker-purple {{ background-color: #7B1FA2; }}
            .marker-gray {{ background-color: #757575; }}
            
            .marker_label {{
                background: rgba(255,255,255,0.9);
                border: 1px solid #999;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 700;
                white-space: nowrap;
                box-shadow: 0 1px 3px rgba(0,0,0,0.2);
                color: #333;
            }}
        </style>
    </head>
    <body>
        <div id="container">
            <div id="map-container"></div>
            <div id="right-panel">
                <div id="detail-content" style="height:100%;">
                    <div class="placeholder-box">
                        <div style="font-size:48px; margin-bottom:10px;">👈</div>
                        <div style="font-size:18px; font-weight:600;">마커를 선택해주세요</div>
                        <div style="font-size:14px; margin-top:10px;">지도에서 마커를 클릭하면<br>상세 정보가 바로 표시됩니다.</div>
                    </div>
                </div>
            </div>
        </div>

        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <!-- Marker Cluster JS -->
        <script src="https://unpkg.com/leaflet.markercluster@1.4.1/dist/leaflet.markercluster.js"></script>
        <script>
            // Data
            var mapData = {json_data};
            
            // Map Layers
            var osm = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                attribution: '&copy; OpenStreetMap',
                maxZoom: 19
            }});
            
            var vworldBase = L.tileLayer('https://xdworld.vworld.kr/2d/Base/service/{{z}}/{{x}}/{{y}}.png', {{
                attribution: '&copy; VWorld',
                maxZoom: 19
            }});
            
            var vworldSat = L.tileLayer('https://xdworld.vworld.kr/2d/Satellite/service/{{z}}/{{x}}/{{y}}.jpeg', {{
                attribution: '&copy; VWorld',
                maxZoom: 19
            }});
            
            // Init Map
            var map = L.map('map-container', {{
                center: [{avg_lat}, {avg_lon}],
                zoom: 11,
                layers: [osm], 
                zoomControl: false 
            }});
            
            // Controls
            var baseMaps = {{
                "기본 지도 (OSM)": osm,
                "브이월드 (상세)": vworldBase,
                "브이월드 (위성)": vworldSat
            }};
            L.control.layers(baseMaps, null, {{ position: 'topright' }}).addTo(map);
            L.control.zoom({{ position: 'topright' }}).addTo(map);
            
            // Marker Cluster Group
            var markers = L.markerClusterGroup({{
                disableClusteringAtZoom: 16,
                spiderfyOnMaxZoom: true,
                showCoverageOnHover: false,
                chunkedLoading: true
            }});
            
            // Markers
            mapData.forEach(function(item) {{
                var isOpen = (item.status && (item.status.includes('영업') || item.status.includes('정상')));
                var className, iconHtml;
                
                if (item.is_large) {{
                    className = "custom-marker marker-purple";
                    iconHtml = '<i class="fa-solid fa-star"></i>';
                }} else if (isOpen) {{
                    className = "custom-marker marker-green";
                    iconHtml = '<i class="fa-solid fa-check"></i>';
                }} else if (item.status && item.status.includes('폐업')) {{
                    className = "custom-marker marker-red";
                    iconHtml = '<i class="fa-solid fa-xmark"></i>';
                }} else {{
                    className = "custom-marker marker-gray";
                    iconHtml = '<i class="fa-solid fa-circle"></i>';
                }}
                
                var myIcon = L.divIcon({{
                    className: '', // Clear default class to avoid white square
                    html: '<div class="' + className + '">' + iconHtml + '</div>',
                    iconSize: [30, 30],
                    iconAnchor: [15, 15]
                }});
                
                var marker = L.marker([item.lat, item.lon], {{ icon: myIcon }});
                
                // Tooltip
                marker.bindTooltip(item.title, {{ direction: 'top', offset: [0, -18], className: 'marker_label' }});
                
                // Click Event
                marker.on('click', function(e) {{
                    var statusColor = (item.is_large) ? "#9C27B0" : (isOpen ? "#2196F3" : "#F44336");
                    
                    var html = `
                    <div class="detail-card">
                        <div class="detail-header">
                            <h3 class="detail-title">${{item.title}}</h3>
                            <span class="detail-badge" style="background-color:${{statusColor}};">${{item.status}}</span>
                        </div>
                        <div class="detail-body">
                            <div class="detail-row"><span class="detail-label">담당</span><span class="detail-value">${{item.branch}} / ${{item.manager}}</span></div>
                            <div class="detail-row"><span class="detail-label">전화</span><span class="detail-value">${{item.tel || "(정보없음)"}}</span></div>
                            <div class="detail-row"><span class="detail-label">업태</span><span class="detail-value">${{item.biz_type}}</span></div>
                            <div class="detail-row"><span class="detail-label">면적</span><span class="detail-value">${{item.area_py}}평</span></div>
                            <div style="margin-top:10px;"><b>📍 주소:</b><br>${{item.addr}}</div>
                        </div>
                        <div class="detail-meta">
                            인허가: ${{item.permit_date}}<br>
                            폐업일: ${{item.close_date}}<br>
                            최종수정: ${{item.modified_date}}
                        </div>
                        
                        <a href="https://map.kakao.com/link/to/${{item.title}},${{item.lat}},${{item.lon}}" target="_blank" class="navi-btn">🚗 카카오내비 길찾기</a>
                    </div>
                    `;
                    document.getElementById('detail-content').innerHTML = html;
                }});
                
                markers.addLayer(marker);
            }});
            
            map.addLayer(markers);
            
            if (mapData.length > 0) {{
                var group = new L.featureGroup(mapData.map(d => L.marker([d.lat, d.lon])));
                map.fitBounds(group.getBounds(), {{ padding: [50, 50] }});
            }}

            // Current Location Button
            var locBtn = document.createElement('div');
            locBtn.innerHTML = '🎯 내 위치';
            locBtn.style.cssText = 'position:absolute;bottom:30px;left:10px;z-index:1000;background:white;padding:8px 12px;border-radius:4px;border:1px solid #ccc;cursor:pointer;font-weight:bold;box-shadow:0 1px 3px rgba(0,0,0,0.2);';
            locBtn.onclick = function() {
                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(function(position) {
                        var lat = position.coords.latitude; 
                        var lon = position.coords.longitude; 
                        var locPosition = [lat, lon];
                        
                        map.setView(locPosition, 16);
                        
                        var locMarker = L.marker(locPosition).addTo(map)
                            .bindTooltip("현재 내 위치", { permanent: true, direction: 'top' })
                            .openTooltip();
                            
                        document.getElementById('detail-content').innerHTML = `
                            <div class="placeholder-box">
                                <div style="font-size:48px; margin-bottom:10px;">📍</div>
                                <div style="font-size:18px; font-weight:600;">현재 내 위치입니다</div>
                                <div style="font-size:14px; margin-top:10px;">위도: ${lat.toFixed(6)}<br>경도: ${lon.toFixed(6)}</div>
                            </div>
                        `;
                    }, function(err) {
                        alert('위치 정보를 가져올 수 없습니다: ' + err.message);
                    });
                } else {
                    alert('이 브라우저는 위치 정보를 지원하지 않습니다.');
                }
            };
            document.getElementById('map-container').appendChild(locBtn);

        </script>
    </body>
    </html>
    '''
    
    components.html(leaflet_template, height=750)
