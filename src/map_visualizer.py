import streamlit as st
import pandas as pd
import json
import streamlit.components.v1 as components
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster, HeatMap

@st.cache_data(show_spinner=False)
def generate_map_html(map_df, kakao_key, use_heatmap, center_lat, center_lon):
    """
    Generates the HTML string for the Kakao Map. Cached to prevent re-computation.
    """
    # Prepare JSON for JS
    # Use Vectorized string methods
    def clean_series(series):
        return series.astype(str).str.replace('"', '&quot;', regex=False).str.replace("'", "&#39;", regex=False).str.replace('\n', ' ', regex=False).str.replace('\\', '\\\\', regex=False).replace({'nan': '', 'None': ''})

    map_df['title'] = clean_series(map_df['사업장명'])
    map_df['addr'] = clean_series(map_df['소재지전체주소'].fillna(''))
    
    # [FIX] Directly use the standardized road address column
    if '도로명전체주소' in map_df.columns:
        map_df['road_addr'] = clean_series(map_df['도로명전체주소'].fillna(''))
    else:
        map_df['road_addr'] = ''
    map_df['tel'] = map_df['소재지전화'].fillna('')
    map_df['status'] = map_df['영업상태명'].fillna('')
    
    # Date Formatting Vectorized
    def format_date_series(series):
        return series.astype(str).str.replace('.0', '', regex=False).str.strip().str.slice(0, 10).replace({'nan': '', 'None': '', 'NaT': ''})
    
    map_df['close_date'] = format_date_series(map_df['폐업일자']) if '폐업일자' in map_df.columns else ''
    map_df['permit_date'] = format_date_series(map_df['인허가일자']) if '인허가일자' in map_df.columns else ''
    map_df['reopen_date'] = format_date_series(map_df['재개업일자']) if '재개업일자' in map_df.columns else ''
    map_df['modified_date'] = format_date_series(map_df['최종수정시점']) if '최종수정시점' in map_df.columns else ''
    
    # [FEATURE] Business Type
    map_df['biz_type'] = map_df['업태구분명'].fillna('') if '업태구분명' in map_df.columns else ''
    
    # [FEATURE] Branch & Manager info
    map_df['branch'] = map_df['관리지사'].fillna('') if '관리지사' in map_df.columns else ''
    map_df['manager'] = map_df['SP담당'].fillna('') if 'SP담당' in map_df.columns else ''
    
    # [FEATURE] Large Area Flag (>= 100py approx 330m2) Vectorized
    if '소재지면적' in map_df.columns:
        map_df['is_large'] = pd.to_numeric(map_df['소재지면적'], errors='coerce').fillna(0) >= 330.0
    else:
        map_df['is_large'] = False
    
    # [FEATURE] Area (Py) for display Vectorized
    if '평수' in map_df.columns:
        map_df['area_py'] = map_df['평수'].fillna(0).astype(float).round(1)
    elif '소재지면적' in map_df.columns:
        map_df['area_py'] = (pd.to_numeric(map_df['소재지면적'], errors='coerce').fillna(0) / 3.3058).round(1)
    else:
        map_df['area_py'] = 0.0

    # [NEW] AI Score & Comment
    if 'AI_Score' not in map_df.columns:
        map_df['AI_Score'] = 0
        map_df['AI_Comment'] = ''
        
    # [FIX] data integrity Vectorized
    if 'record_key' not in map_df.columns:
        map_df['record_key'] = map_df['title'] + "_" + map_df['addr']

    # [FEATURE] Pass Activity Status to JS
    if '활동진행상태' in map_df.columns:
        map_df['act_status'] = map_df['활동진행상태'].fillna('')
    else:
        map_df['act_status'] = ''

    map_data = map_df[['lat', 'lon', 'title', 'status', 'act_status', 'addr', 'road_addr', 'tel', 'close_date', 'permit_date', 'reopen_date', 'modified_date', 'biz_type', 'branch', 'manager', 'is_large', 'area_py', 'AI_Score', 'AI_Comment', 'record_key']].to_dict(orient='records')
    json_data = json.dumps(map_data, ensure_ascii=False)

    return json_data

def render_kakao_map(map_df, kakao_key, use_heatmap=False, user_context={}):
    """
    Renders a Kakao Map using HTML/JS injection.
    """
    # 1. Ensure Coordinates are Numeric
    map_df['lat'] = pd.to_numeric(map_df['lat'], errors='coerce')
    map_df['lon'] = pd.to_numeric(map_df['lon'], errors='coerce')
    
    # 2. Filter Valid
    display_df = map_df.dropna(subset=['lat', 'lon']).copy()
    
    # Limit for performance
    limit = 7000
    if len(display_df) > limit:
        st.warning(f"⚠️ 데이터가 많아 상위 {limit:,}개만 지도에 표시합니다.")
        display_df = display_df.head(limit)
        
    # [FIX] Center Calculation: Default to Seoul (Sudo-gwon)
    if not display_df.empty:
        center_lat = display_df['lat'].mean()
        center_lon = display_df['lon'].mean()
    else:
        # Default Center (Seoul City Hall)
        center_lat, center_lon = 37.5665, 126.9780

    # [OPTIMIZATION] Generate Cached JSON Data
    json_data = generate_map_html(display_df, kakao_key, use_heatmap, center_lat, center_lon)
    
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
        
        /* Scrollbar Styling */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-thumb { background: #ccc; border-radius: 3px; }
        ::-webkit-scrollbar-track { background: #f0f0f0; }
        
        /* Mobile Responsive Layout */
        @media (max-width: 768px) {
            #container { 
                grid-template-columns: 1fr !important; 
                grid-template-rows: 60% 40%; /* Map top, Info bottom */
            }
            #map-overview { 
                border-right: none; 
                border-bottom: 2px solid #ddd; 
            }
            #right-panel {
                grid-template-rows: 1fr; /* Unified panel or keep split? Let's just scroll */
                display: block; 
                overflow-y: auto;
            }
            #map-detail { display: none; } /* Hide detail map on mobile to save space/perf */
            #info-panel { height: 100% !important; }
            
            .navi-btn { padding: 15px 0; font-size: 16px; } /* Larger touch target */
        }
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
                <!-- [NEW] Interactive Map Legend -->
                <div id="map-legend" style="position: absolute; bottom: 30px; left: 30px; z-index: 999; background: rgba(255,255,255,0.95); padding: 10px 15px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); font-size: 13px; border: 1px solid #ddd; width: fit-content; min-width: 160px;">
                    <div id="legend-header" onclick="toggleLegend(event)" style="font-weight: bold; display: flex; justify-content: space-between; align-items: center; cursor: pointer; color: #333; font-size: 14px; border-bottom: 1px solid #eee; padding-bottom: 5px; margin-bottom: 5px;">
                        <span>📍 마커 색상 범례</span>
                        <span id="legend-arrow" style="transition: transform 0.3s ease;">▼</span>
                    </div>
                    <div id="legend-content" style="display: none;">
                        <div style="display: flex; flex-direction: column; gap: 5px;">
                            <div style="font-weight: 600; color: #666; font-size: 12px; margin-top: 5px;">[기본 상태]</div>
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                                <div><img src="https://maps.google.com/mapfiles/ms/icons/blue-dot.png" style="width:18px; vertical-align:middle;"> 영업</div>
                                <div><img src="https://maps.google.com/mapfiles/ms/icons/red-dot.png" style="width:18px; vertical-align:middle;"> 폐업</div>
                                <div style="grid-column: span 2;"><img src="https://maps.google.com/mapfiles/ms/icons/purple-dot.png" style="width:18px; vertical-align:middle;"> 대형(100평↑)</div>
                            </div>
                            <div style="font-weight: 600; color: #666; font-size: 12px; margin-top: 5px;">[활동 이력]</div>
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                                <div><img src="https://maps.google.com/mapfiles/ms/icons/green-dot.png" style="width:18px; vertical-align:middle;"> 방문</div>
                                <div><img src="https://maps.google.com/mapfiles/ms/icons/yellow-dot.png" style="width:18px; vertical-align:middle;"> 상담중</div>
                                <div><img src="https://maps.google.com/mapfiles/ms/icons/ltblue-dot.png" style="width:18px; vertical-align:middle;"> 상담완료</div>
                                <div><img src="https://maps.google.com/mapfiles/ms/icons/pink-dot.png" style="width:18px; vertical-align:middle;"> 상담불가</div>
                                <div style="grid-column: span 2;"><img src="https://maps.google.com/mapfiles/ms/icons/orange-dot.png" style="width:18px; vertical-align:middle;"> <b>계약완료</b></div>
                            </div>
                        </div>
                    </div>
                </div>
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
        
        <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={kakao_key}&libraries=services,clusterer,drawing,visualization"></script>
        <script>
            // --- SDK Check ---
            if (typeof kakao === 'undefined' || typeof kakao.maps === 'undefined') {{
                document.getElementById('map-overview').innerHTML = 
                    '<div style="padding:40px; text-align:center; color:#d32f2f; font-family:sans-serif;">' +
                    '<h3>❌ 카카오 맵 로드 실패</h3>' +
                    '<p>API 키가 잘못되었거나 도메인이 등록되지 않았습니다.</p>' +
                    '<p style="font-size:12px; color:#777;">(Kakao SDK is undefined)</p>' +
                    '</div>';
                // Stop further execution
                throw new Error("Kakao Maps SDK not loaded");
            }}
            // --- Legend Toggle Logic ---
            window.toggleLegend = function(e) {{
                if(e) e.stopPropagation();
                var content = document.getElementById('legend-content');
                var arrow = document.getElementById('legend-arrow');
                if (content.style.display === 'none' || content.style.display === '') {{
                    content.style.display = 'block';
                    arrow.style.transform = 'rotate(180deg)';
                }} else {{
                    content.style.display = 'none';
                    arrow.style.transform = 'rotate(0deg)';
                }}
            }};

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
            
            // [NEW] Heatmap Layer (Kakao)
            var useHeatmap = {str(use_heatmap).lower()};
            if (useHeatmap && kakao.maps.visualization) {{
                // Prepare data for Heatmap (Weighted by AI Score or default)
                var heatData = [];
                data.forEach(function(item) {{
                    if (item.lat && item.lon) {{
                        var w = (item.AI_Score) ? item.AI_Score : 10;
                        heatData.push({{x: item.lon, y: item.lat, v: w}}); 
                    }}
                }});
                
                var heatmap = new kakao.maps.visualization.HeatmapLayer({{
                    data: heatData,
                    opacity: 0.8, // Slightly higher opacity
                    radius: 25 // Readable radius
                }});
                
                heatmap.setMap(mapOverview);
                // Hint: hide clusterer if heatmap is on?
                // clusterer.clear(); 
            }}
            
            // [FEATURE] Places Service for Auto-Phone Search
            var ps = new kakao.maps.services.Places();
            
            var data = {json_data};
            var markers = [];
            
            // Marker Details
            var imgSize = new kakao.maps.Size(35, 35); 
            var openImg = "https://maps.google.com/mapfiles/ms/icons/blue-dot.png";
            var closeImg = "https://maps.google.com/mapfiles/ms/icons/red-dot.png";
            var largeImg = "https://maps.google.com/mapfiles/ms/icons/purple-dot.png";
            
            // [FEATURE] Activity Status Icons (Green=Visit, Yellow=Consulting)
            var visitImg = "https://maps.google.com/mapfiles/ms/icons/green-dot.png";
            var consultImg = "https://maps.google.com/mapfiles/ms/icons/yellow-dot.png";
            var consultDoneImg = "https://maps.google.com/mapfiles/ms/icons/ltblue-dot.png";
            var consultFailImg = "https://maps.google.com/mapfiles/ms/icons/pink-dot.png";
            var contractDoneImg = "https://maps.google.com/mapfiles/ms/icons/orange-dot.png";
            
            var bounds = new kakao.maps.LatLngBounds();
            var detailMarker = null; // Single marker for detail map
            
            data.forEach(function(item) {{
                var isOpen = item.status.includes('영업') || item.status.includes('정상');
                var imgSrc = item.is_large ? largeImg : (isOpen ? openImg : closeImg);
                
                // [FEATURE] Override Color based on Activity Status
                // Priority: Activity > Size > Public Status
                // [FIX] Priority order is highest (contract) to lowest (visit)
                if (item.act_status) {{
                     if(item.act_status.includes('계약완료') || item.act_status.includes('계약')) imgSrc = contractDoneImg;
                     else if(item.act_status.includes('상담완료')) imgSrc = consultDoneImg;
                     else if(item.act_status.includes('상담불가') || item.act_status.includes('불가')) imgSrc = consultFailImg;
                     else if(item.act_status.includes('상담중') || item.act_status.includes('진행중')) imgSrc = consultImg;
                     else if(item.act_status.includes('방문')) imgSrc = visitImg;
                     else if(item.act_status.includes('완료')) imgSrc = contractDoneImg;
                }}
                
                var markerImage = new kakao.maps.MarkerImage(imgSrc, imgSize);
                var markerPos = new kakao.maps.LatLng(item.lat, item.lon);
                
                var marker = new kakao.maps.Marker({{
                    position: markerPos,
                    image: markerImage
                }});
                
                // [FEATURE] Permanent Label
                var dominantStatusStr = '';
                if (item.act_status) {{
                     if(item.act_status.includes('계약완료') || item.act_status.includes('계약')) dominantStatusStr = '계약완료';
                     else if(item.act_status.includes('상담완료')) dominantStatusStr = '상담완료';
                     else if(item.act_status.includes('상담불가') || item.act_status.includes('불가')) dominantStatusStr = '상담불가';
                     else if(item.act_status.includes('상담중') || item.act_status.includes('진행중')) dominantStatusStr = '상담중';
                     else if(item.act_status.includes('방문')) dominantStatusStr = '방문';
                     else if(item.act_status.includes('완료')) dominantStatusStr = '계약완료';
                }}
                
                var actBadge = '';
                if (dominantStatusStr) {{
                     actBadge = '<span style="color:#D32F2F; font-weight:900; margin-right:4px;">[' + dominantStatusStr + ']</span>';
                }}
                var content = '<div class ="marker_label" style="display:block;">' + actBadge + item.title + '</div>';
                
                var customOverlay = new kakao.maps.CustomOverlay({{
                    position: markerPos,
                    content: content,
                    yAnchor: 2.2 // Position above marker
                }});
                
                customOverlay.setMap(mapOverview);
                // Can toggle based on zoom level if needed, but 'immediately visible' implies always.

                
                bounds.extend(markerPos);
                
                // Click Event
                kakao.maps.event.addListener(marker, 'click', function() {{
                    // [FEATURE] Rich InfoWindow on Map
                    var badgeColor = item.is_large ? "#9C27B0" : (isOpen ? "#AED581" : "#EF9A9A");
                    
                    var iwContent = '<div style="padding:15px; width:250px;">' + 
                                    '<h4 style="margin:0 0 5px 0; font-size:16px;">' + item.title + '</h4>' +
                                    '<div style="margin-bottom:10px;"><span class="status-badge" style="background-color:' + badgeColor + ';">' + item.status + '</span></div>' +
                                    '<div style="font-size:13px; line-height:1.6; color:#555;">' +
                                    '<b>👤 담당:</b> ' + (item.branch || '-') + ' / ' + (item.manager || '-') + '<br>' +
                                    '<b>📞 전화:</b> ' + (item.tel || '-') + '<br>' +
                                    '<b>🏢 업태:</b> ' + (item.biz_type || '-') + '<br>' +
                                    '<b>📏 면적:</b> ' + (item.is_large ? '대형' : '일반') + '<br>' + 
                                    '<b>📍 소재지:</b> ' + item.addr + '<br>' +
                                    (item.road_addr ? '<b>🛣️ 도로명:</b> ' + item.road_addr + '<br>' : '') +
                                    '<span style="color:#777; font-size:12px;">📅 인허가: ' + (item.permit_date || '-') + '</span><br>' +
                                    '<span style="color:#777; font-size:12px;">📅 최종수정: ' + (item.modified_date || '-') + '</span><br>' +
                                    (item.close_date ? '<span style="color:#D32F2F; font-size:12px;">❌ 폐업일: ' + item.close_date + '</span>' : '') +
                                    '</div>' +
                                    '<div style="margin-top:10px; display:flex; gap:5px;">' +
                                    '<a href="https://map.kakao.com/link/to/' + item.title + ',' + item.lat + ',' + item.lon + '" target="_blank" style="flex:1; background:#FEE500; color:black; text-decoration:none; padding:8px 0; border-radius:4px; text-align:center; font-size:12px; font-weight:bold;">🚗 길찾기</a>' +
                                    '</div>' +
                                    '</div>';
                                    
                    var infowindow = new kakao.maps.InfoWindow({{
                        content: iwContent,
                        removable: true
                    }});
                    
                    infowindow.open(mapOverview, marker);


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
                    html += '<tr><td class="info-label">소재지주소</td><td class="info-value">' + item.addr + '</td></tr>';
                    if(item.road_addr) html += '<tr><td class="info-label">도로명주소</td><td class="info-value">' + item.road_addr + '</td></tr>';
                    if(item.tel && item.tel != '-') {{
                        html += '<tr><td class="info-label">전화번호</td><td class="info-value">' + item.tel + '</td></tr>';
                    }} else {{
                        // [FEATURE] Missing Phone Number - Auto Search Button
                        html += '<tr><td class="info-label">전화번호</td><td class="info-value" id="tel-box-' + item.title + '">';
                        html += '<button onclick="findPhoneNumber(\'' + item.title + '\', \'' + item.addr + '\')" style="background:white; border:1px solid #ddd; border-radius:4px; padding:2px 6px; cursor:pointer; font-size:11px; color:#555;">🔍 전화번호 찾기</button>';
                        html += '</td></tr>';
                    }}
                    html += '<tr><td colspan="2" style="height:10px;"></td></tr>'; // Spacer
                    
                    if(item.permit_date) html += '<tr><td class="info-label">인허가일</td><td class="info-value">' + item.permit_date + '</td></tr>';
                    if(item.close_date) html += '<tr><td class="info-label" style="color:#D32F2F;">폐업일자</td><td class="info-value" style="color:#D32F2F;">' + item.close_date + '</td></tr>';
                    if(item.reopen_date) html += '<tr><td class="info-label" style="color:#1976D2;">재개업일</td><td class="info-value">' + item.reopen_date + '</td></tr>';
                    if(item.modified_date) html += '<tr><td class="info-label">정보수정</td><td class="info-value">' + item.modified_date + '</td></tr>';
                    html += '</table>';
                    
                    html += '<div style="display:flex; gap:10px; margin-top:20px;">';
                    html += '<a href="https://map.kakao.com/link/to/' + item.title + ',' + item.lat + ',' + item.lon + '" target="_blank" class="navi-btn">🚗 길찾기</a>';
                    html += '</div>';
                    
                    document.getElementById('info-content').innerHTML = html;
                }});
                
                markers.push(marker);
            }});
            
            // [FEATURE] Find Phone Number Function
            window.findPhoneNumber = function(title, addr) {{
                var btnBox = document.getElementById('tel-box-' + title);
                if(btnBox) btnBox.innerHTML = '⏳ 검색중...';
                
                // Search by Title
                ps.keywordSearch(title, function(data, status, pagination) {{
                    if (status === kakao.maps.services.Status.OK) {{
                        // Filter by similarity or just take the first one?
                        // Simple check: take first result
                        var foundTel = data[0].phone;
                        var placeUrl = data[0].place_url;
                        
                        if(foundTel) {{
                            if(btnBox) btnBox.innerHTML = '<span style="color:#2E7D32; font-weight:bold;">' + foundTel + '</span> <span style="font-size:10px; color:#aaa;">(자동발견)</span>';
                        }} else {{
                             if(btnBox) btnBox.innerHTML = '<span style="color:#d32f2f;">번호없음</span> <a href="' + placeUrl + '" target="_blank" style="font-size:10px; color:#aaa;">[상세보기]</a>';
                        }}
                    }} else {{
                        if(btnBox) btnBox.innerHTML = '<span style="color:#999;">검색실패</span>';
                    }}
                }});
            }};
            
            // [FEATURE] Visit Trigger Function (with Session Persistence)
            window.triggerVisit = function(title, addr, key) {{
                if(confirm("'" + title + "' 업체를 [방문] 상태로 변경하시겠습니까? (페이지가 새로고침됩니다)")) {{
                    // Normalize for URL
                    var url = window.parent.location.href; // Access parent Streamlit URL
                    // Check if already has query params
                    var separator = url.includes('?') ? '&' : '?';
                    var newUrl = url + separator + 'visit_action=true&title=' + encodeURIComponent(title) + '&addr=' + encodeURIComponent(addr);
                    
                    if(key) newUrl += '&key=' + encodeURIComponent(key);
                    
                    // [FIX] Append User Context to URL to restore session
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

                    window.parent.location.replace(newUrl); // [FIX] Use replace to avoid history loop
                }}
            }};
            
            // [FEATURE] Interest Trigger Function
            window.triggerInterest = function(title, addr, lat, lon) {{
                // Immediate Feedback
                alert("⭐ '" + title + "' 업체를 관심 목록에 등록합니다.\\n잠시만 기다려주세요...");
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

                window.parent.location.replace(newUrl); // [FIX] Use replace to avoid history loop
            }};
            
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
            locBtn.innerHTML = '🎯 내 위치';
            locBtn.style.cssText = 'position:absolute; top:10px; left:10px; z-index:999; background:white; padding:12px 16px; border-radius:8px; border:1px solid #ccc; cursor:pointer; font-weight:bold; font-size:14px; box-shadow:0 2px 6px rgba(0,0,0,0.2);';
            locBtn.onclick = function(e) {{
                if(e) e.stopPropagation();
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

            // [FEATURE] Route Optimization Button
            var routeBtn = document.createElement('div');
            routeBtn.innerHTML = '⚡ 추천 동선 (15곳) [UPDATED]';
            routeBtn.style.cssText = 'position:absolute; top:60px; left:10px; z-index:999; background:white; padding:12px 16px; border-radius:8px; border:2px solid #FF5722; cursor:pointer; font-weight:bold; font-size:14px; box-shadow:0 2px 6px rgba(0,0,0,0.2); color:#FF5722;';
            routeBtn.onclick = function(e) {{
                if(e) e.stopPropagation();
                if (navigator.geolocation) {{
                    // Show loading state
                    routeBtn.innerHTML = '⏳ 계산중...';
                    
                    navigator.geolocation.getCurrentPosition(function(position) {{
                        var lat = position.coords.latitude; 
                        var lon = position.coords.longitude; 
                        var startPos = new kakao.maps.LatLng(lat, lon); 
                        
                        // 1. My Location Marker
                        mapOverview.setCenter(startPos);
                        mapOverview.setLevel(5);
                        
                        var imageSrc = 'https://t1.daumcdn.net/localimg/localimages/07/mapapidoc/marker_red.png', 
                            imageSize = new kakao.maps.Size(64, 69), 
                            imageOption = {{offset: new kakao.maps.Point(27, 69)}}; 
                        var myMarker = new kakao.maps.Marker({{ position: startPos, image: new kakao.maps.MarkerImage(imageSrc, imageSize, imageOption) }}); 
                        myMarker.setMap(mapOverview); 
                        
                        // 2. Find Optimized Route (Greedy Nearest Neighbor)
                        findOptimizedRoute(startPos);
                        
                        routeBtn.innerHTML = '⚡ 추천 동선 (15곳) [UPDATED]';
                        
                    }}, function(err) {{
                        alert('위치 정보를 가져올 수 없습니다: ' + err.message);
                        routeBtn.innerHTML = '⚡ 추천 동선 (15곳) [UPDATED]';
                    }});
                }} else {{
                    alert('이 브라우저는 위치 정보를 지원하지 않습니다.');
                }}
            }};
            document.getElementById('map-overview').appendChild(routeBtn);
            
            // Route Variables
            var routePolylines = [];
            var routeMarkers = [];
            var routeOverlays = [];

            function findOptimizedRoute(startPos) {{
                // Get all valid markers data
                // We use 'data' variable which is already available
                var candidates = data.filter(function(item) {{
                    return item.lat && item.lon;
                }});
                
                if (candidates.length === 0) {{
                    alert('방문할 대상이 없습니다.');
                    return;
                }}
                
                var route = [];
                var currentPos = startPos;
                var visitedIndices = new Set();
                var maxStops = 15;
                
                for (var i = 0; i < maxStops; i++) {{
                    if (visitedIndices.size >= candidates.length) break;
                    
                    var nearestIdx = -1;
                    var minDist = Infinity;
                    
                    for (var j = 0; j < candidates.length; j++) {{
                        if (visitedIndices.has(j)) continue;
                        
                        var item = candidates[j];
                        var dist = getDistance(currentPos.getLat(), currentPos.getLng(), item.lat, item.lon);
                        
                        if (dist < minDist) {{
                            minDist = dist;
                            nearestIdx = j;
                        }}
                    }}
                    
                    if (nearestIdx !== -1) {{
                        visitedIndices.add(nearestIdx);
                        var nearestItem = candidates[nearestIdx];
                        route.push(nearestItem);
                        currentPos = new kakao.maps.LatLng(nearestItem.lat, nearestItem.lon);
                    }}
                }}
                
                drawRoute(startPos, route);
            }}
            
            // Simple distance
            function getDistance(lat1, lon1, lat2, lon2) {{
                var R = 6371; // Radius of the earth in km
                var dLat = deg2rad(lat2-lat1);  
                var dLon = deg2rad(lon2-lon1); 
                var a = 
                    Math.sin(dLat/2) * Math.sin(dLat/2) +
                    Math.cos(deg2rad(lat1)) * Math.cos(deg2rad(lat2)) * 
                    Math.sin(dLon/2) * Math.sin(dLon/2)
                    ; 
                var c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a)); 
                var d = R * c; // Distance in km
                return d;
            }}

            function deg2rad(deg) {{
                return deg * (Math.PI/180)
            }}
            
            function formatDistance(distKm) {{
                if (distKm < 1) {{
                    return Math.round(distKm * 1000) + 'm';
                }} else {{
                    return distKm.toFixed(1) + 'km';
                }}
            }}
            
            function drawRoute(startPos, routeItems) {{
                // Clear previous route
                clearRoute();
                
                var linePath = [startPos];
                var bounds = new kakao.maps.LatLngBounds();
                bounds.extend(startPos);
                
                var headerHtml = '';
                var bodyHtml = '<div class="sb-body">';
                bodyHtml += '<div style="margin-bottom:10px; color:#666; font-size:13px;">현재 위치에서 가장 가까운 순서대로<br>최적의 동선을 제안합니다.</div>';
                
                // Distance Tracking
                var totalDist = 0;
                
                routeItems.forEach(function(item, index) {{
                    var seq = index + 1;
                    var pos = new kakao.maps.LatLng(item.lat, item.lon);
                    
                    // [FEATURE] Calculate Segment Distance & Add Overlay
                    var prevPos = linePath[linePath.length - 1]; // Last added point
                    var dist = getDistance(prevPos.getLat(), prevPos.getLng(), pos.getLat(), pos.getLng());
                    totalDist += dist;
                    
                    if (dist > 0) {{
                        var midLat = (prevPos.getLat() + pos.getLat()) / 2;
                        var midLon = (prevPos.getLng() + pos.getLng()) / 2;
                        var midPos = new kakao.maps.LatLng(midLat, midLon);
                        
                        var distText = formatDistance(dist);
                        var distContent = '<div style="padding:2px 6px; background:white; border:1px solid #E65100; color:#E65100; font-size:11px; border-radius:12px; font-weight:bold; box-shadow:0 1px 3px rgba(0,0,0,0.2); white-space:nowrap; z-index:9999;">' + distText + '</div>';
                        
                        var distOverlay = new kakao.maps.CustomOverlay({{
                            position: midPos,
                            content: distContent,
                            yAnchor: 0.5,
                            zIndex: 9999
                        }});
                        distOverlay.setMap(mapOverview);
                        routeOverlays.push(distOverlay);
                    }}
                    
                    linePath.push(pos);
                    bounds.extend(pos);
                    
                    // Numbered Marker
                    var imageSrc = 'https://t1.daumcdn.net/localimg/localimages/07/mapapidoc/marker_number_blue.png', 
                        imageSize = new kakao.maps.Size(36, 37),
                        imgOptions =  {{
                            spriteSize : new kakao.maps.Size(36, 691), 
                            spriteOrigin : new kakao.maps.Point(0, (seq * 46) + 10), 
                            offset: new kakao.maps.Point(13, 37)
                        }};
                        
                    var marker = new kakao.maps.Marker({{
                        position: pos,
                        map: mapOverview,
                        zIndex: 1000 + seq
                    }});
                    routeMarkers.push(marker);
                    
                    var content = '<div style="background:#E65100; color:white; border-radius:50%; width:24px; height:24px; text-align:center; line-height:24px; font-weight:bold; border:2px solid white; box-shadow:0 2px 4px rgba(0,0,0,0.3);">' + seq + '</div>';
                    var customOverlay = new kakao.maps.CustomOverlay({{
                        position: pos,
                        content: content,
                        yAnchor: 1.5,
                        zIndex: 2000 + seq
                    }});
                    customOverlay.setMap(mapOverview);
                    routeOverlays.push(customOverlay);
                    
                    // Rich Card Item Construction
                    bodyHtml += '<div style="background:white; border:1px solid #ddd; border-radius:8px; margin-bottom:12px; box-shadow:0 2px 4px rgba(0,0,0,0.05); overflow:hidden;">';
                    
                    // Card Header
                    bodyHtml += '<div style="background:#f8f9fa; padding:10px 12px; border-bottom:1px solid #eee; display:flex; justify-content:space-between; align-items:center;">';
                    bodyHtml += '  <div style="font-weight:bold; color:#333; display:flex; align-items:center;">';
                    bodyHtml += '    <span style="background:#E65100; color:white; border-radius:12px; padding:2px 8px; font-size:11px; margin-right:8px;">#' + seq + '</span>';
                    bodyHtml += '    ' + item.title;
                    bodyHtml += '  </div>';
                    bodyHtml += '  <div style="font-size:11px; color:#E65100; font-weight:bold; background:#FFF3E0; padding:2px 6px; border-radius:4px;">+' + formatDistance(dist) + '</div>';
                    bodyHtml += '</div>';

                    // Card Body
                    bodyHtml += '<div style="padding:12px;">';
                    
                    var statusColor = (item.status.includes('영업') || item.status.includes('정상')) ? '#E8F5E9' : '#FFEBEE';
                    var statusTextColor = (item.status.includes('영업') || item.status.includes('정상')) ? '#2E7D32' : '#C62828';
                    
                    bodyHtml += '  <div style="margin-bottom:8px; display:flex; gap:6px; flex-wrap:wrap;">';
                    bodyHtml += '    <span style="background:' + statusColor + '; color:' + statusTextColor + '; font-size:11px; padding:2px 6px; border-radius:4px;">' + item.status + '</span>';
                    if(item.biz_type) bodyHtml += '    <span style="background:#F3E5F5; color:#7B1FA2; font-size:11px; padding:2px 6px; border-radius:4px;">' + item.biz_type + '</span>';
                    if(item.is_large) bodyHtml += '    <span style="background:#EDE7F6; color:#512DA8; font-size:11px; padding:2px 6px; border-radius:4px; font-weight:bold;">🏢 대형매장</span>';
                    bodyHtml += '  </div>';

                    // Info Rows
                    bodyHtml += '  <div style="font-size:12px; color:#555; line-height:1.6;">';
                    bodyHtml += '    <div style="display:flex;"><span style="color:#888; width:50px;">주소</span> <span style="flex:1;">' + item.addr + '</span></div>';
                    bodyHtml += '    <div style="display:flex;"><span style="color:#888; width:50px;">전화</span> <span style="flex:1;">' + (item.tel && item.tel != '-' ? item.tel : '<span style="color:#ccc;">(미등록)</span>') + '</span></div>';
                    bodyHtml += '    <div style="display:flex;"><span style="color:#888; width:50px;">면적</span> <span style="flex:1;">' + (item.area_py || 0) + '평</span></div>';
                    
                    if(item.branch || item.manager) {{
                        bodyHtml += '    <div style="display:flex; margin-top:4px; padding-top:4px; border-top:1px dashed #eee;"><span style="color:#888; width:50px;">담당</span> <span style="flex:1; color:#1565C0;">' + (item.branch || '') + ' ' + (item.manager || '') + '</span></div>';
                    }}
                    bodyHtml += '  </div>';
                    bodyHtml += '</div>'; // End Card Body


                    // Card Footer
                    bodyHtml += '<div style="padding:8px 12px; background:#fafafa; border-top:1px solid #eee; display:flex; gap:8px;">';
                    
                    if (dist < 1.0) {{
                        bodyHtml += '    <a href="https://map.kakao.com/link/to/' + item.title + ',' + item.lat + ',' + item.lon + '" target="_blank" style="flex:1; text-align:center; padding:6px 0; background:#2E7D32; border:1px solid #2E7D32; color:white; border-radius:4px; font-size:12px; font-weight:bold; text-decoration:none;">🚶 도보 길안내</a>';
                    }} else {{
                        bodyHtml += '    <a href="https://map.kakao.com/link/to/' + item.title + ',' + item.lat + ',' + item.lon + '" target="_blank" style="flex:1; text-align:center; padding:6px 0; background:#E65100; border:1px solid #E65100; color:white; border-radius:4px; font-size:12px; font-weight:bold; text-decoration:none;">🚗 차량 길안내</a>';
                    }}
                    bodyHtml += '</div>'; // End Footer
                    
                    bodyHtml += '</div>'; // End Card Item
                }});
                
                bodyHtml += '</div>'; // End sb-body
                
                // [FEATURE] Update Header with Total Distance
                var totalDistStr = formatDistance(totalDist);
                
                // [NEW] AI Analysis Review Generation
                var aiReview = generateAIAnalysis(routeItems, totalDist);
                
                headerHtml = '<div class="sb-header"><h3 class="sb-title">⚡ 추천 방문 코스 (' + routeItems.length + '곳 / 총 ' + totalDistStr + ')</h3></div>';
                headerHtml += aiReview; // Insert AI Review
                
                // Cleanest Update: Replace innerHTML with robustly built strings
                requestAnimationFrame(function() {{
                    var infoPanel = document.getElementById('info-panel');
                    if (infoPanel) infoPanel.innerHTML = headerHtml + bodyHtml;
                    
                    var mapDetail = document.getElementById('map-detail');
                    if (mapDetail) mapDetail.innerHTML = '<div class="detail-label">⚡ 추천 동선 모드</div><div style="width:100%; height:100%; display:flex; flex-direction:column; justify-content:center; align-items:center; color:#E65100; font-weight:bold; background:#fafafa; text-align:center;"><div>총 예상 이동거리</div><div style="font-size:24px; color:#E65100; margin:5px 0 15px 0;">' + totalDistStr + '</div><div style="font-size:13px; color:#777;">지도에 표시된 순서대로<br>방문하세요</div></div>';
                }});
                
                // Draw Polyline (Segment by Segment)
                
                // Clear existing
                linePath = []; 
                
                // Re-iterate to draw segments with specific styles
                var prev = startPos;
                
                routeItems.forEach(function(item) {{
                    var curr = new kakao.maps.LatLng(item.lat, item.lon);
                    var dist = getDistance(prev.getLat(), prev.getLng(), curr.getLat(), curr.getLng());
                    
                    var strokeColor = '#E65100'; // Default Car (Orange)
                    var strokeStyle = 'solid';
                    
                    // [FEATURE] Walking Route (< 1km)
                    if (dist < 1.0) {{
                        strokeColor = '#2E7D32'; // Green
                        strokeStyle = 'shortdash';
                    }}
                    
                    var polyline = new kakao.maps.Polyline({{
                        path: [prev, curr], 
                        strokeWeight: 6, 
                        strokeColor: strokeColor, 
                        strokeOpacity: 0.8, 
                        strokeStyle: strokeStyle
                    }});
                    
                    polyline.setMap(mapOverview);
                    routePolylines.push(polyline);
                    
                    prev = curr;
                }});
                
                mapOverview.setBounds(bounds);
            }}
            
            function clearRoute() {{
                for (var i = 0; i < routePolylines.length; i++) {{
                    routePolylines[i].setMap(null);
                }}
                routePolylines = [];
                
                for (var i = 0; i < routeMarkers.length; i++) {{
                    routeMarkers[i].setMap(null);
                }}
                routeMarkers = [];
                
                for (var i = 0; i < routeOverlays.length; i++) {{
                    routeOverlays[i].setMap(null);
                }}
                routeOverlays = [];
            }}
            
            // [NEW] AI Analysis Logic
            function generateAIAnalysis(items, totalDistKm) {{
                if(!items || items.length === 0) return '';
                
                var walkCount = 0;
                var telCount = 0;
                var maxArea = 0;
                var maxAreaItem = null;
                
                items.forEach(function(item, idx) {{
                    if(idx > 0) {{ // Check distance from prev
                       var prev = items[idx-1];
                       var d = getDistance(prev.lat, prev.lon, item.lat, item.lon);
                       if(d < 1.0) walkCount++;
                    }}
                    if(item.tel && item.tel != '-') telCount++;
                    if(item.area_py > maxArea) {{
                        maxArea = item.area_py;
                        maxAreaItem = item;
                    }}
                }});
                
                var strategy = '';
                if(walkCount >= items.length / 2) strategy = '🏃 <b>도보 이동 추천</b> (대부분 1km 이내)';
                else strategy = '🚗 <b>차량 이동 효율적</b> (거리가 멉니다)';
                
                var telListHtml = '';
                if(telCount > 0) {{
                    telListHtml = '<div style="margin-top:5px; background:rgba(255,255,255,0.7); padding:5px; border-radius:4px; max-height:80px; overflow-y:auto;">';
                    items.forEach(function(item) {{
                        if(item.tel && item.tel != '-') {{
                             telListHtml += '<div style="font-size:11px; color:#555;">📞 ' + item.title + ' (' + item.tel + ')</div>';
                        }}
                    }});
                    telListHtml += '</div>';
                }}
                
                // [FIX] Priority Logic for Missing Area
                var priorityHtml = '';
                var tipHtml = '';
                
                if (maxArea > 0) {{
                     priorityHtml = '2️⃣ <b>우선 타겟:</b> ' + maxAreaItem.title + ' (' + maxAreaItem.area_py + '평, 대형)';
                     tipHtml = '💡 <b>Tip:</b> ' + maxAreaItem.title + '부터 공략하여 대형 계약을 노리세요!';
                }} else {{
                     priorityHtml = '2️⃣ <b>우선 타겟:</b> 면적 정보 없음 (판단 유보)';
                     tipHtml = '💡 <b>Tip:</b> 데이터상 면적 정보가 없습니다. 현장 규모를 눈으로 직접 확인 후 방문 순서를 정하세요.';
                }}
                
                var html = '<div style="margin:10px 15px; padding:15px; background:linear-gradient(135deg, #E3F2FD 0%, #BBDEFB 100%); border-radius:8px; border-left:5px solid #1976D2; box-shadow:0 2px 5px rgba(0,0,0,0.05);">';
                html += '<div style="font-weight:bold; color:#0D47A1; margin-bottom:8px; display:flex; align-items:center;"><span style="font-size:18px; margin-right:5px;">🤖</span> AI 전략 분석 리포트</div>';
                
                html += '<div style="font-size:13px; color:#333; line-height:1.6;">';
                html += '1️⃣ <b>이동 전략:</b> ' + strategy + '<br>';
                html += priorityHtml + '<br>';
                html += '3️⃣ <b>컨택 준비:</b> 대상 중 <b>' + telCount + '곳</b> 전화번호 보유';
                html += telListHtml + '<br>'; // Add list here
                html += '</div>';
                
                html += '<div style="margin-top:8px; font-size:12px; color:#555; background:rgba(255,255,255,0.5); padding:5px; border-radius:4px;">';
                html += tipHtml;
                html += '</div>';
                html += '</div>';
                
                return html;
            }}
    </body>
    </html>
    '''
    
    import hashlib
    data_hash = hashlib.md5(json_data.encode('utf-8')).hexdigest()
    
    components.html(html_content, height=850, key=f"kakao_map_dual_{data_hash}")



def render_folium_map(display_df, use_heatmap=False, user_context={}):
    """
    Render Map using Leaflet (Client-Side) to prevent Streamlit reruns (flashing).
    Layout: Split View (65% Map, 35% Detail)
    """
    if display_df.empty:
        st.warning("표시할 데이터가 없습니다.")
        return

    # [PERFORMANCE] Enforce limit for Folium rendering to prevent browser crash
    limit = 10000
    if len(display_df) > limit:
        st.warning(f"⚠️ 데이터가 너무 많아({len(display_df):,}건) 상위 {limit:,}개만 지도에 표시합니다. 필터를 사용하여 범위를 좁혀보세요.")
        display_df = display_df.head(limit)

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
    
    # Fill defaults with safety checks
    map_data_df['title'] = map_data_df['사업장명'] if '사업장명' in map_data_df.columns else pd.Series(['상호미상']*len(map_data_df))
    map_data_df['title'] = map_data_df['title'].fillna('상호미상')
    
    map_data_df['status'] = map_data_df['영업상태명'] if '영업상태명' in map_data_df.columns else pd.Series(['-']*len(map_data_df))
    map_data_df['status'] = map_data_df['status'].fillna("-")
    
    map_data_df['addr'] = map_data_df['소재지전체주소'] if '소재지전체주소' in map_data_df.columns else pd.Series(['-']*len(map_data_df))
    map_data_df['addr'] = map_data_df['addr'].fillna("-")
    
    # [NEW] Explicitly extract road address for leaflet/카카오맵 혼합뷰
    if '도로명전체주소' in map_data_df.columns:
        map_data_df['road_addr'] = map_data_df['도로명전체주소'].fillna("")
    else:
        map_data_df['road_addr'] = ""
    
    map_data_df['tel'] = map_data_df['소재지전화'] if '소재지전화' in map_data_df.columns else pd.Series(['']*len(map_data_df))
    map_data_df['tel'] = map_data_df['tel'].fillna("").replace('nan', '')
    
    map_data_df['branch'] = map_data_df['관리지사'] if '관리지사' in map_data_df.columns else pd.Series(['-']*len(map_data_df))
    map_data_df['branch'] = map_data_df['branch'].fillna("-")
    
    map_data_df['manager'] = map_data_df['SP담당'] if 'SP담당' in map_data_df.columns else pd.Series(['-']*len(map_data_df))
    map_data_df['manager'] = map_data_df['manager'].fillna("-")
    
    map_data_df['biz_type'] = map_data_df['업태구분명'] if '업태구분명' in map_data_df.columns else pd.Series(['-']*len(map_data_df))
    map_data_df['biz_type'] = map_data_df['biz_type'].fillna("-")
    
    # Check for '평수' or calculate it (Assuming 1 '소재지면적' unit approx to meters, usually m2)
    # If logic exists elsewhere, reuse. Here we approximate if '평수' column exists.
    if '평수' in map_data_df.columns:
        map_data_df['area_py'] = map_data_df['평수'].fillna(0).astype(float).round(1)
    else:
        map_data_df['area_py'] = 0.0
        
    # Large Area Flag for Coloring
    map_data_df['is_large'] = map_data_df['area_py'] >= 100.0

    # Convert to Dict for JSON
    cols_to_keep = ['lat', 'lon', 'title', 'status', 'addr', 'road_addr', 'tel', 
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
            /* [NEW] Activity Status Colors */
            .marker-yellow {{ background-color: #FBC02D; color: #333 !important; }}
            .marker-cyan {{ background-color: #00BCD4; }}
            .marker-pink {{ background-color: #E91E63; }}
            .marker-orange {{ background-color: #F57C00; }}
            
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
            <div id="map-container">
                <!-- [NEW] Interactive Map Legend for Leaflet -->
                <div id="map-legend" style="position: absolute; bottom: 30px; left: 10px; z-index: 1000; background: rgba(255,255,255,0.95); padding: 10px 15px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); font-size: 13px; border: 1px solid #ddd; width: fit-content; min-width: 160px;">
                    <div id="legend-header-leaf" onclick="toggleLegend(event)" style="font-weight: bold; display: flex; justify-content: space-between; align-items: center; cursor: pointer; color: #333; font-size: 14px; border-bottom: 1px solid #eee; padding-bottom: 5px; margin-bottom: 5px;">
                        <span>📍 마커 색상 범례</span>
                        <span id="legend-arrow-leaf" style="transition: transform 0.3s ease;">▼</span>
                    </div>
                    <div id="legend-content-leaf" style="display: none;">
                        <div style="display: flex; flex-direction: column; gap: 5px;">
                            <div style="font-weight: 600; color: #666; font-size: 12px; margin-top: 5px;">[기본 상태]</div>
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                                <div><span style="display:inline-block; width:12px; height:12px; border-radius:50%; background:#2E7D32; margin-right:4px;"></span>영업</div>
                                <div><span style="display:inline-block; width:12px; height:12px; border-radius:50%; background:#d32f2f; margin-right:4px;"></span>폐업</div>
                                <div style="grid-column: span 2;"><span style="display:inline-block; width:12px; height:12px; border-radius:50%; background:#7B1FA2; margin-right:4px;"></span>대형(100평↑)</div>
                            </div>
                            <div style="font-weight: 600; color: #666; font-size: 12px; margin-top: 5px;">[활동 이력]</div>
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                                <div><span style="display:inline-block; width:12px; height:12px; border-radius:50%; background:#2E7D32; margin-right:4px;"></span>방문</div>
                                <div><span style="display:inline-block; width:12px; height:12px; border-radius:50%; background:#FBC02D; margin-right:4px;"></span>상담중</div>
                                <div><span style="display:inline-block; width:12px; height:12px; border-radius:50%; background:#00BCD4; margin-right:4px;"></span>상담완료</div>
                                <div><span style="display:inline-block; width:12px; height:12px; border-radius:50%; background:#E91E63; margin-right:4px;"></span>상담불가</div>
                                <div style="grid-column: span 2;"><span style="display:inline-block; width:12px; height:12px; border-radius:50%; background:#F57C00; margin-right:4px;"></span>계약완료</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
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
        <!-- Heatmap JS -->
        <script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
        <script>
            // --- Legend Toggle Logic (Leaflet) ---
            window.toggleLegend = function(e) {{
                if(e) e.stopPropagation();
                var content = document.getElementById('legend-content-leaf');
                var arrow = document.getElementById('legend-arrow-leaf');
                if (content.style.display === 'none' || content.style.display === '') {{
                    content.style.display = 'block';
                    arrow.style.transform = 'rotate(180deg)';
                }} else {{
                    content.style.display = 'none';
                    arrow.style.transform = 'rotate(0deg)';
                }}
            }};

            // Data
            var mapData = {json_data};
            var useHeatmap = {str(use_heatmap).lower()};
            
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
                layers: [vworldBase], 
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
            
            // [NEW] EXPERT FEATURE 2: HEATMAP
            if (useHeatmap) {{
                try {{
                    var heatPoints = mapData.map(function(p) {{ 
                        // Weighted by Score
                        return [p.lat, p.lon, (p.AI_Score || 0)]; 
                    }});
                    // Heatmap Layer
                    var heat = L.heatLayer(heatPoints, {{
                        radius: 30, // [FIX] Increased radius for visibility
                        blur: 20, // [FIX] Smoother blur
                        maxZoom: 12, // Lower max zoom to show density at higher levels
                        max: 100,
                        gradient: {{0.2: 'blue', 0.4: 'cyan', 0.6: 'lime', 0.8: 'yellow', 1.0: 'red'}} // [FIX] Better gradient
                    }}).addTo(map);
                    
                    // If heatmap is on, maybe don't cluster? Or keep clustering but heatmap underneath.
                    // Usually heatmap is standalone. Let's keep clusters but they might obscure heatmap.
                    // Let's make cluster markers toggleable or just show both.
                }} catch(e) {{
                    console.log("Heatmap error:", e);
                }}
            }}
            
            // Markers
            mapData.forEach(function(item) {{
                var isOpen = (item.status && (item.status.includes('영업') || item.status.includes('정상')));
                
                // [NEW] AI Score Logic
                var scoreHtml = '';
                if (item.AI_Score && item.AI_Score >= 80) {{
                     scoreHtml = '<div style="background:#FFD700; color:black; font-size:10px; font-weight:bold; border-radius:4px; padding:0 3px; position:absolute; top:-10px; right:-10px; border:1px solid white; box-shadow:0 1px 2px rgba(0,0,0,0.2);">⭐' + item.AI_Score + '</div>';
                }}
                
                // DivIcon for Custom Marker Appearance
                var markerColor = item.is_large ? '#673AB7' : (isOpen ? '#2E7D32' : '#d32f2f');
                var iconHtml = '<div style="position:relative; width:30px; height:30px; background:' + markerColor + '; border-radius:50%; border:2px solid white; box-shadow:0 2px 4px rgba(0,0,0,0.3); display:flex; align-items:center; justify-content:center; color:white;">' +
                               '<i class="fas fa-map-marker-alt"></i>' + scoreHtml + '</div>';
                               
                var customIcon = L.divIcon({{
                    html: iconHtml,
                    className: '',
                    iconSize: [30, 30],
                    iconAnchor: [15, 30]
                }});
                
                var marker = L.marker([item.lat, item.lon], {{ icon: customIcon }});
                var className, iconHtml;
                
                // [FEATURE] Enhanced Status Colors Including Activity Overrides
                if (item.act_status && item.act_status.includes('계약완료')) {{
                    className = "custom-marker marker-orange";
                    iconHtml = '<i class="fa-solid fa-handshake"></i>';
                }} else if (item.act_status && item.act_status.includes('상담완료')) {{
                    className = "custom-marker marker-cyan";
                    iconHtml = '<i class="fa-solid fa-comments"></i>';
                }} else if (item.act_status && item.act_status.includes('상담불가')) {{
                    className = "custom-marker marker-pink";
                    iconHtml = '<i class="fa-solid fa-ban"></i>';
                }} else if (item.act_status && (item.act_status.includes('상담중') || item.act_status.includes('진행중'))) {{
                    className = "custom-marker marker-yellow";
                    iconHtml = '<i class="fa-solid fa-spinner"></i>';
                }} else if (item.act_status && item.act_status.includes('방문')) {{
                    className = "custom-marker marker-green";
                    iconHtml = '<i class="fa-solid fa-walking"></i>';
                }} else if (item.is_large) {{
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
                
                // Tooltip (Permanent Label)
                var tooltipText = item.title;
                if (item.act_status) {{
                     var dominantStatusStr = '';
                     if(item.act_status.includes('계약완료') || item.act_status.includes('계약')) dominantStatusStr = '계약완료';
                     else if(item.act_status.includes('상담완료')) dominantStatusStr = '상담완료';
                     else if(item.act_status.includes('상담불가') || item.act_status.includes('불가')) dominantStatusStr = '상담불가';
                     else if(item.act_status.includes('상담중') || item.act_status.includes('진행중')) dominantStatusStr = '상담중';
                     else if(item.act_status.includes('방문')) dominantStatusStr = '방문';
                     else if(item.act_status.includes('완료')) dominantStatusStr = '계약완료';
                     else dominantStatusStr = item.act_status;
                     
                     tooltipText = '[' + dominantStatusStr + '] ' + tooltipText;
                }}
                
                marker.bindTooltip(tooltipText, {{ 
                    permanent: true, 
                    direction: 'top', 
                    offset: [0, -18], 
                    className: 'marker_label' 
                }});
                
                // [FEATURE] Rich Popup on Map
                var badgeColor = item.is_large ? "#9C27B0" : (isOpen ? "#2196F3" : "#F44336");
                var popupContent = `
                    <div style="width:220px; font-family:'Pretendard';">
                        <h4 style="margin:0 0 5px 0; font-size:15px;">${{item.title}}</h4>
                        <div style="margin-bottom:8px;"><span class="detail-badge" style="background-color:${{badgeColor}}; font-size:11px;">${{item.status}}</span></div>
                        <div style="font-size:12px; line-height:1.5; color:#444; margin-bottom:10px;">
                            <b>👤 담당:</b> ${{item.branch || '-'}} / ${{item.manager || '-'}}<br>
                            <b>📞 전화:</b> ${{item.tel || '-'}}<br>
                            <b>🏢 업태:</b> ${{item.biz_type || '-'}}<br>
                            <b>📏 면적:</b> ${{item.area_py}}평 (${{item.is_large ? '대형' : '일반'}})<br> 
                            <b>📍 주소:</b> ${{item.addr}}<br>
                            ${{item.road_addr ? '<span style="color:#666; font-size:11px;">(도로명) ' + item.road_addr + '</span><br>' : ''}}
                            <span style="color:#777; font-size:11px;">📅 인허가: ${{item.permit_date || '-'}}</span><br>
                            <span style="color:#777; font-size:11px;">📅 최종수정: ${{item.modified_date || '-'}}</span><br>
                            ${{item.close_date ? '<span style="color:#D32F2F; font-size:11px;">❌ 폐업일: ' + item.close_date + '</span>' : ''}}
                        </div>
                        <div style="display:flex; gap:5px;">
                            <a href="https://map.kakao.com/link/to/${{item.title}},${{item.lat}},${{item.lon}}" target="_blank" style="flex:1; background:#FEE500; color:black; text-decoration:none; padding:6px 0; border-radius:4px; text-align:center; font-size:11px; font-weight:bold; display:block;">🚗 길찾기</a>
                        </div>
                    </div>
                `;
                marker.bindPopup(popupContent);
                
                // Click Event
                marker.on('click', function(e) {{
                    L.DomEvent.stopPropagation(e);
                    var statusColor = (item.is_large) ? "#9C27B0" : (isOpen ? "#AED581" : "#EF9A9A");
                    
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
                            <div style="margin-top:10px;">
                                <b>📍 소재지:</b><br>${{item.addr}}
                                ${{item.road_addr ? '<br><b style="margin-top:5px; display:inline-block;">📍 도로명:</b><br>' + item.road_addr : ''}}
                            </div>
                        </div>
                        <div class="detail-meta">
                            인허가: ${{item.permit_date}}<br>
                            폐업일: ${{item.close_date}}<br>
                            최종수정: ${{item.modified_date}}
                        </div>
                        
                        <div style="display:flex; gap:10px; margin-top:20px;">
                            <a href="https://map.kakao.com/link/to/${{item.title}},${{item.lat}},${{item.lon}}" target="_blank" class="navi-btn">🚗 길찾기</a>
                        </div>
                    </div>
                    `;
                    document.getElementById('detail-content').innerHTML = html;
                }});
                
                markers.addLayer(marker);
            }});
            
            // [FEATURE] Visit Trigger Function
            // [FEATURE] Visit Trigger Function (with Session Persistence)
            window.triggerVisit = function(title, addr) {{
                if(confirm("'" + title + "' 업체를 [방문] 상태로 변경하시겠습니까? (페이지가 새로고침됩니다)")) {{
                    // Show immediate feedback as requested
                    alert("방문처리 되었습니다.");
                    
                     // Normalize for URL
                    var url = window.parent.location.href; // Access parent Streamlit URL
                    
                    // [FIX] Clean existing params to avoid duplication/infinite growth if possible
                    // But simpler to just append unique action for now or replace query if we could parse it.
                    // Let's stick to appending but maybe cleaner if we use URL object?
                    // Given iframe constraints, simple string append is safest for now.
                    
                    try {{
                        var currentUrl = new URL(window.parent.location.href);
                        var params = currentUrl.searchParams;
                        
                        params.set('visit_action', 'true');
                        if(item.record_key) params.set('key', item.record_key); // [FIX] Use item.record_key
                        params.set('title', title);
                        params.set('addr', addr);
                        
                        var u_role = "{user_context.get('user_role', '')}";
                        if(u_role) params.set('user_role', u_role);
                        
                        var u_branch = "{user_context.get('user_branch', '')}";
                        if(u_branch && u_branch != 'None') params.set('user_branch', u_branch);
                        
                        var u_mgr = "{user_context.get('user_manager_name', '')}";
                        if(u_mgr && u_mgr != 'None') params.set('user_manager_name', u_mgr);
                        
                        var u_code = "{user_context.get('user_manager_code', '')}";
                        if(u_code && u_code != 'None') params.set('user_manager_code', u_code);
                        
                        var u_auth = "{user_context.get('admin_auth', 'false')}";
                        params.set('admin_auth', u_auth);
                        
                        window.parent.location.replace(currentUrl.toString()); // [FIX] Use replace
                    }} catch(e) {{
                        console.error("URL failed", e);
                        var u = window.parent.location.href;
                        var s = u.includes('?') ? '&' : '?';
                        window.parent.location.replace(u + s + 'visit_action=true&title=' + encodeURIComponent(title) + '&addr=' + encodeURIComponent(addr)); // [FIX] Use replace
                    }}
                }}
            }};
            
            // [FEATURE] Interest Trigger Function (Detail View)
            window.triggerInterest = function(title, addr, lat, lon) {{
                // Immediate Feedback
                alert("⭐ '" + title + "' 업체를 관심 목록에 등록합니다.\\n잠시만 기다려주세요...");
                
                try {{
                    var currentUrl = new URL(window.parent.location.href);
                    var params = currentUrl.searchParams;
                    
                    params.set('interest_action', 'true');
                    params.set('title', title);
                    params.set('addr', addr);
                    params.set('lat', lat);
                    params.set('lon', lon);
                    
                    var u_role = "{user_context.get('user_role', '')}";
                    if(u_role) params.set('user_role', u_role);
                    
                    var u_branch = "{user_context.get('user_branch', '')}";
                    if(u_branch && u_branch != 'None') params.set('user_branch', u_branch);
                    
                    var u_mgr = "{user_context.get('user_manager_name', '')}";
                    if(u_mgr && u_mgr != 'None') params.set('user_manager_name', u_mgr);
                    
                    var u_code = "{user_context.get('user_manager_code', '')}";
                    if(u_code && u_code != 'None') params.set('user_manager_code', u_code);
                    
                    var u_auth = "{user_context.get('admin_auth', 'false')}";
                    params.set('admin_auth', u_auth);
                    
                    window.parent.location.replace(currentUrl.toString()); // [FIX] Use replace
                }} catch(e) {{
                    console.error("Interest URL failed", e);
                    var u = window.parent.location.href;
                    var s = u.includes('?') ? '&' : '?';
                    window.parent.location.replace(u + s + 'interest_action=true&title=' + encodeURIComponent(title) + '&addr=' + encodeURIComponent(addr) + '&lat=' + lat + '&lon=' + lon); // [FIX] Use replace
                }}
            }};
            
            map.addLayer(markers);
            
            if (mapData.length > 0) {{
                var group = new L.featureGroup(mapData.map(d => L.marker([d.lat, d.lon])));
                map.fitBounds(group.getBounds(), {{ padding: [50, 50] }});
            }}

            // Current Location Button
            var locBtn = document.createElement('div');
            locBtn.innerHTML = '🎯 내 위치';
            locBtn.innerHTML = '🎯 내 위치';
            locBtn.style.cssText = 'position:absolute; top:10px; left:10px; z-index:1000; background:white; padding:12px 16px; border-radius:8px; border:1px solid #ccc; cursor:pointer; font-weight:bold; font-size:14px; box-shadow:0 2px 6px rgba(0,0,0,0.2);';
            locBtn.onclick = function(e) {{
                if(e) e.stopPropagation();
                if (navigator.geolocation) {{
                    navigator.geolocation.getCurrentPosition(function(position) {{
                        var lat = position.coords.latitude; 
                        var lon = position.coords.longitude; 
                        var locPosition = [lat, lon];
                        
                        map.setView(locPosition, 16);
                        
                        var locMarker = L.marker(locPosition).addTo(map)
                            .bindTooltip("현재 내 위치", {{ permanent: true, direction: 'top' }})
                            .openTooltip();
                            
                        document.getElementById('detail-content').innerHTML = `
                            <div class="placeholder-box">
                                <div style="font-size:48px; margin-bottom:10px;">📍</div>
                                <div style="font-size:18px; font-weight:600;">현재 내 위치입니다</div>
                                <div style="font-size:14px; margin-top:10px;">위도: ${{lat.toFixed(6)}}<br>경도: ${{lon.toFixed(6)}}</div>
                            </div>
                        `;
                    }}, function(err) {{
                        alert('위치 정보를 가져올 수 없습니다: ' + err.message);
                    }});
                }} else {{
                    alert('이 브라우저는 위치 정보를 지원하지 않습니다.');
                }}
            }};
            document.getElementById('map-container').appendChild(locBtn);

            // [FEATURE] Route Optimization Button (Leaflet)
            var routeBtn = document.createElement('div');
            routeBtn.innerHTML = '⚡ 추천 동선 (15곳)';
            routeBtn.style.cssText = 'position:absolute; top:70px; left:10px; z-index:1000; background:white; padding:12px 16px; border-radius:8px; border:2px solid #FF5722; cursor:pointer; font-weight:bold; font-size:14px; box-shadow:0 2px 6px rgba(0,0,0,0.2); color:#FF5722;';
            routeBtn.onclick = function(e) {{
                if(e) e.stopPropagation();
                if (navigator.geolocation) {{
                    routeBtn.innerHTML = '⏳ 계산중...';
                    navigator.geolocation.getCurrentPosition(function(position) {{
                        var lat = position.coords.latitude; 
                        var lon = position.coords.longitude; 
                        var startPos = [lat, lon];
                        
                        // 1. My Location Marker
                        map.setView(startPos, 14);
                        var myMarker = L.marker(startPos).addTo(map);
                        myMarker.bindTooltip("출발", {{ permanent: true, direction: 'top' }}).openTooltip();

                        // 2. Find Optimized Route
                        findOptimizedRoute(startPos);
                        
                        routeBtn.innerHTML = '⚡ 추천 동선 (15곳)';
                        
                    }}, function(err) {{
                        alert('위치 정보를 가져올 수 없습니다: ' + err.message);
                        routeBtn.innerHTML = '⚡ 추천 동선 (15곳)';
                    }});
                }} else {{
                    alert('이 브라우저는 위치 정보를 지원하지 않습니다.');
                }}
            }};
            document.getElementById('map-container').appendChild(routeBtn);
            
            // Route Variables
            var routeLayerGroup = L.layerGroup().addTo(map);

            // [NEW] AI Analysis Logic (Leaflet)
            function generateAIAnalysisLeaflet(items, totalDistKm) {{
                if(!items || items.length === 0) return '';
                
                var walkCount = 0;
                var telCount = 0;
                var maxArea = 0;
                var maxAreaItem = null;
                
                items.forEach(function(item, idx) {{
                    if(idx > 0) {{
                       var prev = items[idx-1];
                       var d = getDistance(prev.lat, prev.lon, item.lat, item.lon);
                       if(d < 1.0) walkCount++;
                    }}
                    if(item.tel && item.tel != '-') telCount++;
                    if(item.area_py > maxArea) {{
                        maxArea = item.area_py;
                        maxAreaItem = item;
                    }}
                }});
                
                var strategy = '';
                if(walkCount >= items.length / 2) strategy = '🏃 <b>도보 이동 추천</b> (대부분 1km 이내)';
                else strategy = '🚗 <b>차량 이동 효율적</b> (거리가 멉니다)';
                
                var telListHtml = '';
                if(telCount > 0) {{
                    telListHtml = '<div style="margin-top:5px; background:rgba(255,255,255,0.7); padding:5px; border-radius:4px; max-height:80px; overflow-y:auto;">';
                    items.forEach(function(item) {{
                        if(item.tel && item.tel != '-') {{
                             telListHtml += '<div style="font-size:11px; color:#555;">📞 ' + item.title + ' (' + item.tel + ')</div>';
                        }}
                    }});
                    telListHtml += '</div>';
                }}
                
                // [FIX] Priority Logic for Missing Area
                var priorityHtml = '';
                var tipHtml = '';
                
                if (maxArea > 0) {{
                     priorityHtml = '2️⃣ <b>우선 타겟:</b> ' + maxAreaItem.title + ' (' + maxAreaItem.area_py + '평, 대형)';
                     tipHtml = '💡 <b>Tip:</b> ' + maxAreaItem.title + '부터 방문하여 효율을 높이세요!';
                }} else {{
                     priorityHtml = '2️⃣ <b>우선 타겟:</b> 면적 정보 없음 (판단 유보)';
                     tipHtml = '💡 <b>Tip:</b> 면적 정보가 불충분합니다. 현장 확인 후 방문 순서를 정하는 것을 추천합니다.';
                }}
                
                var html = '<div style="margin-bottom:15px; padding:15px; background:linear-gradient(135deg, #E3F2FD 0%, #BBDEFB 100%); border-radius:8px; border-left:5px solid #1976D2; box-shadow:0 2px 5px rgba(0,0,0,0.05);">';
                html += '<div style="font-weight:bold; color:#0D47A1; margin-bottom:8px; display:flex; align-items:center;"><span style="font-size:18px; margin-right:5px;">🤖</span> AI 전략 분석 리포트</div>';
                
                html += '<div style="font-size:13px; color:#333; line-height:1.6;">';
                html += '1️⃣ <b>이동 전략:</b> ' + strategy + '<br>';
                html += priorityHtml + '<br>';
                html += '3️⃣ <b>컨택 준비:</b> 대상 중 <b>' + telCount + '곳</b> 전화번호 보유';
                html += telListHtml + '<br>';
                html += '</div>';
                html += '<div style="margin-top:8px; font-size:12px; color:#555; background:rgba(255,255,255,0.5); padding:5px; border-radius:4px;">';
                html += tipHtml ;
                html += '</div></div>';
                
                return html;
            }}

            function findOptimizedRoute(startPos) {{
                 // Filter valid data
                 var candidates = mapData.filter(function(item) {{
                    return item.lat && item.lon;
                }});
                
                if (candidates.length === 0) {{
                    alert('방문할 대상이 없습니다.');
                    return;
                }}
                
                var route = [];
                var currentPos = {{ lat: startPos[0], lon: startPos[1] }};
                var visitedIndices = new Set();
                var maxStops = 15;
                
                for (var i = 0; i < maxStops; i++) {{
                    if (visitedIndices.size >= candidates.length) break;
                    
                    var nearestIdx = -1;
                    var minDist = Infinity;
                    
                    for (var j = 0; j < candidates.length; j++) {{
                        if (visitedIndices.has(j)) continue;
                        
                        var item = candidates[j];
                        var dist = getDistance(currentPos.lat, currentPos.lon, item.lat, item.lon);
                        
                        if (dist < minDist) {{
                            minDist = dist;
                            nearestIdx = j;
                        }}
                    }}
                    
                    if (nearestIdx !== -1) {{
                        visitedIndices.add(nearestIdx);
                        var nearestItem = candidates[nearestIdx];
                        route.push(nearestItem);
                        currentPos = {{ lat: nearestItem.lat, lon: nearestItem.lon }};
                    }}
                }}
                
                drawRoute(startPos, route);
            }}
            
            function getDistance(lat1, lon1, lat2, lon2) {{
                var R = 6371; 
                var dLat = deg2rad(lat2-lat1);  
                var dLon = deg2rad(lon2-lon1); 
                var a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                        Math.cos(deg2rad(lat1)) * Math.cos(deg2rad(lat2)) * 
                        Math.sin(dLon/2) * Math.sin(dLon/2); 
                var c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a)); 
                return R * c;
            }}

            function deg2rad(deg) {{ return deg * (Math.PI/180); }}
            
            function formatDistance(distKm) {{
                if (distKm < 1) {{
                    return Math.round(distKm * 1000) + 'm';
                }} else {{
                    return distKm.toFixed(1) + 'km';
                }}
            }}
            
            function drawRoute(startPos, routeItems) {{
                routeLayerGroup.clearLayers();
                
                var latlngs = [startPos];
                // [FEATURE] Distance Variable
                var totalDist = 0;
                
                var listHtml = '<div class="detail-header"><h3 class="detail-title" style="color:#E65100;">⚡ 추천 방문 코스 (' + routeItems.length + '곳)</h3><div style="font-size:13px; color:#666;">현재 위치에서 가장 가까운 최적 동선입니다.</div></div><div class="detail-body">';
                
                routeItems.forEach(function(item, index) {{
                    var seq = index + 1;
                    var pos = [item.lat, item.lon];
                    
                    // [FEATURE] Calculate Distance
                    var prevPos = latlngs[latlngs.length - 1]; // [lat, lon] array
                    var dist = getDistance(prevPos[0], prevPos[1], pos[0], pos[1]);
                    totalDist += dist;
                    
                    // [FEATURE] Distance Badge on Map
                    if (dist > 0) {{
                         var midLat = (prevPos[0] + pos[0]) / 2;
                         var midLon = (prevPos[1] + pos[1]) / 2;
                         var distText = formatDistance(dist);
                         
                         var distIcon = L.divIcon({{
                             className: '',
                             html: '<div style="padding:2px 6px; background:white; border:1px solid #E65100; color:#E65100; font-size:11px; border-radius:12px; font-weight:bold; box-shadow:0 1px 3px rgba(0,0,0,0.2); white-space:nowrap;">' + distText + '</div>',
                             iconSize: [40, 20], // Approx
                             iconAnchor: [20, 10]
                         }});
                         L.marker([midLat, midLon], {{ icon: distIcon, zIndexOffset: 9999 }}).addTo(routeLayerGroup);
                    }}
                    
                    latlngs.push(pos);
                    
                    // Numbered Marker (Custom HTML Icon)
                    var numIcon = L.divIcon({{
                        className: '',
                        html: '<div style="background:#E65100; color:white; border-radius:50%; width:24px; height:24px; text-align:center; line-height:24px; font-weight:bold; border:2px solid white; box-shadow:0 2px 4px rgba(0,0,0,0.3);">' + seq + '</div>',
                        iconSize: [24, 24],
                        iconAnchor: [12, 12]
                    }});
                    
                    L.marker(pos, {{ icon: numIcon, zIndexOffset: 1000 }}).addTo(routeLayerGroup);
                    
                    // Add to list
                    listHtml += `
                        <div class="detail-card" style="margin:10px 0; padding:15px; border-left:4px solid #E65100;">
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:5px;">
                                <div style="font-weight:bold; color:#E65100;">#${{seq}}. ${{item.title}}</div>
                                <div style="font-size:11px; color:#E65100; font-weight:bold;">+${{formatDistance(dist)}}</div>
                            </div>
                            <div style="font-size:12px; color:#555; margin-bottom:8px;">${{item.addr}}</div>
                            
                            <div style="font-size:11px; color:#777; line-height:1.4; margin-bottom:10px; background:#f9f9f9; padding:8px; border-radius:4px;">
                                📏 면적: ${{item.area_py || 0}}평 ${{item.is_large ? '<span style="color:#673AB7; font-weight:bold;">(대형)</span>' : ''}}<br>
                                📅 인허가: ${{item.permit_date || '-'}} / 수정: ${{item.modified_date || '-'}}<br>
                                ${{item.close_date ? '<span style="color:#D32F2F;">❌ 폐업일: ' + item.close_date + '</span>' : ''}}
                            </div>

                             <div style="display:flex; gap:5px;">
                                
                                ${{ (dist < 1.0) 
                                    ? `<a href="https://map.kakao.com/link/to/${{item.title}},${{item.lat}},${{item.lon}}" target="_blank" style="flex:1; background:#C8E6C9; color:#1B5E20; text-decoration:none; padding:5px 0; border-radius:4px; text-align:center; font-size:11px; font-weight:bold;">🚶 도보 (${{Math.ceil(dist*15)}}분)</a>` 
                                    : `<a href="https://map.kakao.com/link/to/${{item.title}},${{item.lat}},${{item.lon}}" target="_blank" style="flex:1; background:#FFCCBC; color:#BF360C; text-decoration:none; padding:5px 0; border-radius:4px; text-align:center; font-size:11px; font-weight:bold;">🚗 차량 (${{Math.ceil(dist*3)}}분)</a>` 
                                }}
                            </div>
                        </div>
                    `;
                }});
                
                listHtml += '</div>';
                
                var totalDistStr = formatDistance(totalDist);
                // [NEW] AI Analysis Review
                var aiReview = generateAIAnalysisLeaflet(routeItems, totalDist);
                
                var headerHtml = '<div class="detail-header" style="background:#fafafa; border-bottom:1px solid #ddd; padding:15px;"><h3 class="detail-title" style="font-size:18px;">⚡ 추천 방문 코스 (' + routeItems.length + '곳 / 총 ' + totalDistStr + ')</h3></div>';
                
                // Insert AI Review
                headerHtml += aiReview;
                
                // Hackily replace the header part of listHtml or just reconstruct.
                // Reconstruct is cleaner but listHtml already has body.
                // Replace strategy:
                var bodyPart = listHtml.substring(listHtml.indexOf('<div class="detail-body">'));
                document.getElementById('detail-content').innerHTML = headerHtml + bodyPart;
                
                // Draw Polyline (Segment by Segment for Smart Styles)
                var prev = startPos;
                routeItems.forEach(function(item) {{
                    var curr = [item.lat, item.lon];
                    var d = getDistance(prev[0], prev[1], curr[0], curr[1]);
                    
                    var color = (d < 1.0) ? '#2E7D32' : '#E65100';
                    var dashArray = (d < 1.0) ? '5, 10' : null;
                    
                    L.polyline([prev, curr], {{color: color, weight: 6, opacity: 0.8, dashArray: dashArray}}).addTo(routeLayerGroup);
                    prev = curr;
                }});
                
                // Bound to route
                var group = new L.featureGroup(routeItems.map(d => L.marker([d.lat, d.lon])));
                map.fitBounds(group.getBounds(), {{ padding: [50, 50] }});
            }}

        </script>
    </body>
    </html>
    '''
    
    components.html(leaflet_template, height=750)
