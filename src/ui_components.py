import streamlit as st
import streamlit.components.v1 as components

def inject_custom_css():
    """Injects premium custom CSS for the application UI."""
    st.markdown("""
    <style>
        div[data-testid="stExpander"] details {
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        
        .dashboard-card {
            background-color: white;
            border-radius: 12px;
            padding: 16px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            border: 1px solid #f0f0f0;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            margin-bottom: 10px;
            text-align: center;
        }
        .dashboard-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 12px rgba(0,0,0,0.1);
        }
        
        .card-header {
            font-size: 1.1rem;
            font-weight: 700;
            color: #1a237e;
            margin-bottom: 8px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }
        
        .stat-value {
            font-size: 1.8rem;
            font-weight: 800;
            color: #333;
            margin: 4px 0;
        }
        
        .stat-sub {
            font-size: 0.85rem;
            color: #666;
            display: flex;
            gap: 8px;
            justify-content: center;
        }
        
        .status-dot {
            height: 8px;
            width: 8px;
            border-radius: 50%;
            display: inline-block;
            margin-right: 4px;
        }
        .dot-green { background-color: #4CAF50; }
        .dot-red { background-color: #F44336; }
        .dot-gray { background-color: #9E9E9E; }
        
        /* Button Tweaks */
        .stButton button {
            border-radius: 6px;
            font-weight: 600;
            transition: all 0.2s;
        }
        .stButton button:hover {
            transform: translateY(-1px);
        }
        
        /* [FIX] Feature Box Vertical Centering */
        .feature-box-centered {
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            height: 50px;
            border: 1px solid rgba(49, 51, 63, 0.2);
            border-radius: 8px;
            background-color: white;
            color: #31333F;
            font-weight: 800;
            font-size: 0.85rem;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }

        /* Mobile Grid Card Styles */
        .card-tile {
            background-color: white;
            border: 1px solid #eee;
            border-radius: 10px;
            padding: 12px;
            margin-bottom: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            transition: all 0.2s ease;
            height: 100%;
            display: flex;
            flex-direction: column;
        }
        .card-tile:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            border-color: #3F51B5;
        }
        .card-title-grid {
            font-weight: 800;
            font-size: 0.95rem;
            color: #222;
            margin-bottom: 5px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .status-badge {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: bold;
            color: white;
            margin-bottom: 4px;
        }
        .status-open { background-color: #4CAF50; }
        .status-closed { background-color: #F44336; }
    </style>
    """, unsafe_allow_html=True)

def inject_button_color_script():
    """Injects JavaScript to dynamically apply status colors to buttons with a safety throttle."""
    js = """
    <script>
        (function() {
            function applyStatusColors() {
                try {
                    const buttons = window.parent.document.querySelectorAll('button');
                    buttons.forEach(btn => {
                        const txt = btn.innerText.trim();
                        if (txt === '영업') {
                            if (btn.style.backgroundColor !== 'rgb(174, 213, 129)') {
                                btn.style.setProperty('background-color', '#AED581', 'important');
                                btn.style.setProperty('color', '#1B5E20', 'important');
                                btn.style.setProperty('border-color', '#AED581', 'important');
                            }
                        } else if (txt === '폐업') {
                            if (btn.style.backgroundColor !== 'rgb(239, 154, 154)') {
                                btn.style.setProperty('background-color', '#EF9A9A', 'important');
                                btn.style.setProperty('color', '#B71C1C', 'important');
                                btn.style.setProperty('border-color', '#EF9A9A', 'important');
                            }
                        }
                    });
                } catch(e) {}
            }
            
            // Initial call
            applyStatusColors();
            
            // Cleanup previous observer to prevent memory leak and racial conditions
            if (window.parent._stButtonObserver) {
                window.parent._stButtonObserver.disconnect();
            }
            
            // Throttled MutationObserver
            let timeout;
            window.parent._stButtonObserver = new MutationObserver((mutations) => {
                if (timeout) return;
                timeout = setTimeout(() => {
                    applyStatusColors();
                    timeout = null;
                }, 100); // 100ms throttle to prevent React sync issues
            });
            
            window.parent._stButtonObserver.observe(window.parent.document.body, { 
                childList: true, 
                subtree: true 
            });
        })();
    </script>
    """
    components.html(js, height=0, width=0)
