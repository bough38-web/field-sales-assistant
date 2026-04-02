"""
Navigation Click Tracker Component

This module provides a simple way to track navigation clicks from the map.
"""

import streamlit as st
import streamlit.components.v1 as components

def render_navigation_tracker():
    """
    Renders a hidden component that listens for navigation clicks
    and stores them in session state for logging.
    """
    
    # JavaScript to capture navigation clicks
    tracker_html = """
    <script>
    // Listen for navigation events from parent window
    window.addEventListener('message', function(event) {
        if (event.data.type === 'navigation_click') {
            // Send to Streamlit via query params
            var data = event.data;
            var url = window.location.href;
            var separator = url.includes('?') ? '&' : '?';
            var newUrl = url + separator + 
                'nav_action=true' +
                '&nav_title=' + encodeURIComponent(data.title) +
                '&nav_addr=' + encodeURIComponent(data.addr) +
                '&nav_lat=' + data.lat +
                '&nav_lon=' + data.lon;
            window.location.href = newUrl;
        }
    });
    </script>
    """
    
    components.html(tracker_html, height=0)
