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
    
    map_data = display_df[['lat', 'lon', 'title', 'status', 'addr', 'tel', 'close_date', 'permit_date', 'reopen_date', 'modified_date', 'biz_type']].to_dict(orient='records')
    json_data = json.dumps(map_data, ensure_ascii=False)
    
    st.markdown('<div style="background-color: #e3f2fd; border-left: 5px solid #2196F3; padding: 10px; margin-bottom: 10px; border-radius: 4px;"><small><b>Tip:</b> 지도가 보이지 않으면 도메인 등록(http://localhost:8501)을 확인하세요.</small></div>', unsafe_allow_html=True)

    map_css = '''
        html, body { width:100%; height:100%; margin:0; padding:0; overflow:hidden; } 
        #map { width: 100%; height: 500px; border: 1px solid #ddd; background-color: #f8f9fa; }
        .infowindow { padding:10px; font-size:12px; font-family: 'Pretendard', sans-serif; width: 220px; }
        .info-title { font-weight:bold; font-size:14px; margin-bottom:5px; color:#333; border-bottom:1px solid #eee; padding-bottom:5px; }
        .status-badge { display:inline-block; padding:2px 6px; border-radius:4px; color:white; font-size:11px; margin-left:5px; vertical-align:middle; }
    '''

    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8"/>
        <style>{map_css}</style>
    </head>
    <body>
        <div id="map"></div>
        <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={kakao_key}&libraries=services,clusterer,drawing"></script>
        <script>
            var mapContainer = document.getElementById('map'), 
                mapOption = {{ 
                    center: new kakao.maps.LatLng({center_lat}, {center_lon}), 
                    level: 9 
                }};
            
            var map = new kakao.maps.Map(mapContainer, mapOption);
            
            var clusterer = new kakao.maps.MarkerClusterer({{
                map: map, 
                averageCenter: true, 
                minLevel: 10 
            }});
            
            var data = {json_data};
            var markers = [];
            
            // Markers
            var imgSize = new kakao.maps.Size(35, 35); 
            // Blue for Open, Red for Closed
            var openImg = "https://maps.google.com/mapfiles/ms/icons/blue-dot.png";
            var closeImg = "https://maps.google.com/mapfiles/ms/icons/red-dot.png";
            
            var bounds = new kakao.maps.LatLngBounds();
            
            data.forEach(function(item) {{
                var isOpen = item.status.includes('영업') || item.status.includes('정상');
                var imgSrc = isOpen ? openImg : closeImg;
                var markerImage = new kakao.maps.MarkerImage(imgSrc, imgSize);
                var markerPos = new kakao.maps.LatLng(item.lat, item.lon);
                
                var marker = new kakao.maps.Marker({{
                    position: markerPos,
                    image: markerImage
                }});
                
                // Extend bounds
                bounds.extend(markerPos);
                
                // Color Logic for Badge
                var badgeColor = isOpen ? "#2196F3" : "#F44336"; 
                
                var content = '<div class="infowindow">' + 
                              '<div class="info-title">' + item.title + 
                              '<span class="status-badge" style="background-color:' + badgeColor + ';">' + item.status + '</span></div>' +
                              (item.biz_type ? ('<div style="color:#555; font-size:11px; margin-bottom:5px;">[' + item.biz_type + ']</div>') : '') + 
                              (item.permit_date ? ('<div style="color:#666;">인허가: ' + item.permit_date + '</div>') : '') + 
                              (item.close_date ? ('<div style="color:#D32F2F;">폐업: ' + item.close_date + '</div>') : '') + 
                              (item.reopen_date ? ('<div style="color:#1976D2;">재개업: ' + item.reopen_date + '</div>') : '') + 
                              (item.modified_date ? ('<div style="color:#666; font-size:11px;">(수정: ' + item.modified_date + ')</div>') : '') + 
                              '<div style="margin-top:5px; color:#555;">' + item.addr + '</div>' + 
                              (item.tel ? ('<div style="margin-top:5px; font-weight:bold; color:#1976D2;">📞 ' + item.tel + '</div>') : '') + 
                              '<div style="margin-top:10px; padding-top:10px; border-top:1px solid #eee; text-align:center;">' +
                              '<a href="https://map.kakao.com/link/to/' + item.title + ',' + item.lat + ',' + item.lon + '" target="_blank" style="display:inline-block; width:100%; padding:8px 0; background-color:#FEE500; color:#3C1E1E; text-decoration:none; border-radius:6px; font-weight:bold; font-size:13px;">🚗 카카오 네비게이션</a>' +
                              '</div>' +
                              '</div>';
                              
                var infowindow = new kakao.maps.InfoWindow({{
                    content: content,
                    removable: true
                }});
                
                kakao.maps.event.addListener(marker, 'click', function() {{
                    infowindow.open(map, marker);
                }});
                
                markers.push(marker);
            }});
            
            clusterer.addMarkers(markers);
            
            // Auto Fit Bounds if data exists
            if (markers.length > 0) {{
                map.setBounds(bounds);
            }}
            
            // Zoom Control
            var zoomControl = new kakao.maps.ZoomControl();
            map.addControl(zoomControl, kakao.maps.ControlPosition.RIGHT);
            
            // [FEATURE] My Location Button (Custom Control)
            var locBtn = document.createElement('div');
            locBtn.innerHTML = '🎯 내 위치';
            locBtn.style.cssText = 'position:absolute;bottom:30px;right:10px;z-index:999;background:white;padding:8px 12px;border-radius:4px;border:1px solid #ccc;cursor:pointer;font-weight:bold;box-shadow:0 1px 3px rgba(0,0,0,0.2);';
            locBtn.onclick = function() {{
                if (navigator.geolocation) {{
                    navigator.geolocation.getCurrentPosition(function(position) {{
                        var lat = position.coords.latitude; 
                        var lon = position.coords.longitude; 
                        var locPosition = new kakao.maps.LatLng(lat, lon); 
                        
                        var imageSrc = 'https://t1.daumcdn.net/localimg/localimages/07/mapapidoc/marker_red.png', 
                            imageSize = new kakao.maps.Size(64, 69), 
                            imageOption = {{offset: new kakao.maps.Point(27, 69)}}; 
                        var markerImage = new kakao.maps.MarkerImage(imageSrc, imageSize, imageOption);
                        var marker = new kakao.maps.Marker({{ position: locPosition, image: markerImage }}); 
                        marker.setMap(map); 
                        
                        map.setCenter(locPosition);
                        
                        var infowindow = new kakao.maps.InfoWindow({{
                            content: '<div style="padding:5px; text-align:center;">🔴 현재 내 위치</div>'
                        }});
                        infowindow.open(map, marker);
                        
                    }}, function(err) {{
                        alert('위치 정보를 가져올 수 없습니다: ' + err.message);
                    }});
                }} else {{ 
                    alert('이 브라우저에서는 위치 기반 서비스를 사용할 수 없습니다.'); 
                }}
            }};
            document.getElementById('map').appendChild(locBtn);
            
        </script>
    </body>
    </html>
    '''
    
    components.html(html_content, height=520)

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
    
    # [DEBUG] Visible Debug Info Removed
    display_df = valid_rows
    
    # 2. Limit (Reduced to 100 for debugging)
    limit = 100
    if len(display_df) > limit:
         st.warning(f"⚠️ 디버깅을 위해 상위 {limit}개만 표시합니다.")
         display_df = display_df.head(limit)
    
    # 3. Center
    if not display_df.empty:
        avg_lat = display_df['lat'].mean()
        avg_lon = display_df['lon'].mean()
    else:
        avg_lat, avg_lon = 37.5665, 126.9780
        
    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=11, tiles=None)
    
    # Layers
    folium.TileLayer(
        tiles='https://xdworld.vworld.kr/2d/Base/service/{z}/{x}/{y}.png',
        attr='VWorld',
        name='상세 지도 (VWorld)',
        overlay=False,
        control=True,
        show=True
    ).add_to(m)
    
    # [FIX] markers added directly to map (No Cluster)
    # [FIX] Test Marker (Red Circle)
    folium.CircleMarker(
        location=[avg_lat, avg_lon],
        radius=10,
        color='red',
        fill=True,
        fill_color='red',
        tooltip="중심점(Center)"
    ).add_to(m)
    
    # [FEATURE] My Location
    from folium.plugins import LocateControl
    LocateControl(
        auto_start=False,
        strings={"title": "내 위치 보기", "popup": "현재 위치"},
        locateOptions={'enableHighAccuracy': True}
    ).add_to(m)

    count = 0
    for _, row in display_df.iterrows():
        try:
            # Data Preparation
            status = str(row['영업상태명'])
            title = str(row['사업장명']).replace('"', '&quot;').replace("'", "&#39;")
            addr = str(row.get('소재지전체주소', '')).replace('nan', '')
            tel = str(row.get('소재지전화', '')).replace('nan', '')
            
            # Area
            area_val = row.get('평수', 0)
            area_str = f"{float(area_val):.1f}평" if area_val else "-"
            
            # Dates
            def fmt_date(d):
                if pd.isna(d) or str(d) == 'NaT': return '-'
                return str(d)[:10]
                
            permit_date = fmt_date(row.get('인허가일자'))
            close_date = fmt_date(row.get('폐업일자'))
            
            # Color Logic
            if "영업" in status or "정상" in status:
                color = "green"
                icon_type = "info-sign"
                status_style = "color:green; font-weight:bold;"
            elif "폐업" in status:
                color = "red"
                icon_type = "ban-circle"
                status_style = "color:red; font-weight:bold;"
            else:
                color = "gray"
                icon_type = "question-sign"
                status_style = "color:gray;"

            # Popup HTML
            popup_html = f"""
            <div style="font-family:'Pretendard', sans-serif; width:240px; font-size:12px;">
                <h4 style="margin:0 0 8px 0; border-bottom:1px solid #eee; padding-bottom:5px; color:#333;">
                    {title}
                </h4>
                <table style="width:100%; border-collapse:collapse;">
                    <tr><td style="color:#666; width:60px;">업태</td><td style="font-weight:bold; color:#555;">{str(row.get('업태구분명', ''))}</td></tr>
                    <tr><td style="color:#666; width:60px;">상태</td><td style="{status_style}">{status}</td></tr>
                    <tr><td style="color:#666;">주소</td><td>{addr}</td></tr>
                    <tr><td style="color:#666;">평수</td><td>{area_str}</td></tr>
                    <tr><td style="color:#666;">전화</td><td>{tel}</td></tr>
                    <tr><td style="color:#666;">인허가</td><td>{permit_date}</td></tr>
                    <tr><td style="color:#666;">폐업일</td><td>{close_date}</td></tr>
                    <tr><td style="color:#1976D2;">재개업</td><td>{fmt_date(row.get('재개업일자'))}</td></tr>
                    <tr><td style="color:#666; font-size:11px;">수정일</td><td>{fmt_date(row.get('최종수정시점'))}</td></tr>
                </table>
                <div style="margin-top:10px; padding-top:10px; border-top:1px solid #eee; text-align:center;">
                    <a href="https://map.kakao.com/link/to/{title},{row['lat']},{row['lon']}" target="_blank" style="display:inline-block; width:100%; padding:8px 0; background-color:#FEE500; color:#3C1E1E; text-decoration:none; border-radius:6px; font-weight:bold; font-size:13px;">🚗 카카오 네비게이션</a>
                </div>
            </div>
            """
            
            folium.Marker(
                [row['lat'], row['lon']],
                popup=folium.Popup(popup_html, max_width=260),
                tooltip=f"{title} ({status})",
                icon=folium.Icon(color=color, icon=icon_type)
            ).add_to(m) 
            count += 1
        except: continue
        
    st.write(f"🗺️ 지도에 {count}개의 마커를 추가했습니다.")

    # Bounds
    if not display_df.empty:
        sw = display_df[['lat', 'lon']].min().values.tolist()
        ne = display_df[['lat', 'lon']].max().values.tolist()
        m.fit_bounds([sw, ne])
        
    # Render
    map_html = m._repr_html_()
    components.html(map_html, height=500, scrolling=False)
