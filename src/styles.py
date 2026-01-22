
def get_main_style():
    return """
<style>
    /* Global Font & Colors */
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Pretendard', sans-serif;
    }
    
    /* Layout Adjustments */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 100%; 
    }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
        border-right: 1px solid #eee;
    }
    
    /* Card/Metric Styling */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        color: #333;
    }
    
    /* Custom Small Card Class */
    .small-card {
        background-color: #fff;
        border: 1px solid #eee;
        border-radius: 8px;
        padding: 10px;
        text-align: center;
        margin-bottom: 5px;
    }
    .small-card-title { font-size: 0.85rem; color: #555 !important; font-weight: 600; margin-bottom: 2px; }
    .small-card-value { font-size: 1.1rem; color: #333 !important; font-weight: 700; }
    .small-card-active { color: #2E7D32 !important; font-size: 0.8rem; }
    
    /* Ensure text visibility on forced white backgrounds */
    .metric-label { color: #555 !important; }
    .metric-value { color: #333 !important; }

    /* Mobile Card Styling */
    .card-container {
        background-color: white;
        padding: 16px;
        border-radius: 12px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        margin-bottom: 16px;
        border-left: 5px solid #2E7D32;
        transition: transform 0.2s;
    }
    .card-container:active {
        transform: scale(0.98);
    }
    .card-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #1a1a1a;
        margin-bottom: 4px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .card-badges {
        display: flex;
        gap: 5px;
    }
    .status-badge {
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .status-open { background-color: #e8f5e9; color: #2e7d32; }
    .status-closed { background-color: #ffebee; color: #c62828; }
    
    .card-meta {
        font-size: 0.85rem;
        color: #555;
        margin-bottom: 8px;
    }
    .card-address {
        font-size: 0.85rem;
        color: #777;
        margin-bottom: 12px;
        display: flex;
        align-items: start;
        gap: 5px;
    }
    
    /* Action Buttons Area */
    .card-actions {
        display: flex;
        gap: 10px;
        margin-top: 10px;
        border-top: 1px solid #eee;
        padding-top: 10px;
    }
    
    /* Tabs Customization */
    .stTabs [data-baseweb="tab-list"] {
        gap: 20px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 4px 4px 0 0;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: transparent;
        border-bottom: 2px solid #2E7D32;
        color: #2E7D32;
    }
</style>
"""

def get_theme_css(theme):
    if theme == "모던 다크 (Modern Dark)":
        return """
        <style>
            [data-testid="stAppViewContainer"] { background-color: #1E1E1E; color: #E0E0E0; }
            [data-testid="stSidebar"] { background-color: #252526; border-right: 1px solid #333; }
            [data-testid="stHeader"] { background-color: rgba(30,30,30,0.9); }
            .stMarkdown, .stText, h1, h2, h3, h4, h5, h6 { color: #E0E0E0 !important; }
            .stDataFrame { border: 1px solid #444; }
            div[data-testid="metric-container"] { background-color: #333333; border: 1px solid #444; color: #fff; padding: 10px; border-radius: 8px; }
        </style>
        """
    elif theme == "웜 페이퍼 (Warm Paper)":
        return """
        <style>
            [data-testid="stAppViewContainer"] { background-color: #F5F5DC; color: #4A403A; }
            [data-testid="stSidebar"] { background-color: #E8E4D9; border-right: 1px solid #D8D4C9; }
            .stMarkdown, .stText, h1, h2, h3, h4, h5, h6 { color: #5C4033 !important; font-family: 'Georgia', serif; }
            div[data-testid="metric-container"] { background-color: #FFF8E7; border: 1px solid #D2B48C; color: #5C4033; padding: 10px; border-radius: 4px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
            .stButton button { background-color: #D2B48C !important; color: #fff !important; border-radius: 0px; }
        </style>
        """
    elif theme == "고대비 (High Contrast)":
        return """
        <style>
            [data-testid="stAppViewContainer"] { background-color: #FFFFFF; color: #000000; }
            [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 2px solid #000000; }
            .stMarkdown, .stText, h1, h2, h3, h4, h5, h6 { color: #000000 !important; font-weight: 900 !important; }
            div[data-testid="metric-container"] { background-color: #FFFFFF; border: 2px solid #000000; color: #000000; padding: 15px; border-radius: 0px; }
            .stButton button { background-color: #000000 !important; color: #FFFFFF !important; border: 2px solid #000000; font-weight: bold; }
        </style>
        """
    elif theme == "코퍼레이트 블루 (Corporate Blue)":
        return """
        <style>
            [data-testid="stAppViewContainer"] { background-color: #F0F4F8; color: #243B53; }
            [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #BCCCDC; }
            h1, h2, h3 { color: #102A43 !important; }
            div[data-testid="metric-container"] { background-color: #FFFFFF; border-left: 5px solid #334E68; box-shadow: 0 4px 6px rgba(0,0,0,0.1); padding: 15px; border-radius: 4px; }
            .stButton button { background-color: #334E68 !important; color: white !important; border-radius: 4px; }
        </style>
        """
    else: # Default
        return """
        <style>
            /* Global Font & Background */
            @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@300;400;500;600;700&display=swap');
            
            html, body, [class*="css"] {
                font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif;
            }
            
            [data-testid="stAppViewContainer"] { 
                background-color: #F8F9FA; 
                color: #343A40; 
            }
            
            [data-testid="stSidebar"] { 
                background-color: #FFFFFF; 
                border-right: 1px solid #DEE2E6; 
                box-shadow: 2px 0 12px rgba(0,0,0,0.03);
            }
            
            /* Headers */
            h1, h2, h3 { color: #212529 !important; font-weight: 700 !important; letter-spacing: -0.5px; }
            h4, h5, h6 { color: #495057 !important; font-weight: 600 !important; }
            
            /* Sidebar Headers & Text */
            [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
                    color: #212529 !important;
            }
            [data-testid="stSidebar"] .stMarkdown p {
                color: #495057 !important;
                font-size: 0.95rem;
            }
            
            /* Improved Visibility for Global Filters Section */
            /* We can't target specifically by ID easily in Streamlit, but we can style inputs */
            [data-testid="stSidebar"] .stSelectbox label, 
            [data-testid="stSidebar"] .stMultiSelect label,
            [data-testid="stSidebar"] .stTextInput label {
                color: #343A40 !important;
                font-weight: 600 !important;
            }
            
            /* Buttons */
            .stButton button { 
                background-color: #228BE6 !important; 
                color: #fff !important; 
                border: none;
                border-radius: 6px;
                font-weight: 500;
                transition: all 0.2s;
            }
            .stButton button:hover {
                background-color: #1C7ED6 !important;
                box-shadow: 0 4px 12px rgba(34, 139, 230, 0.3);
                transform: translateY(-1px);
            }
            
            /* Metric Cards */
            div[data-testid="metric-container"] { 
                background-color: #FFFFFF; 
                border: 1px solid #E9ECEF; 
                color: #495057; 
                padding: 16px; 
                border-radius: 12px; 
                box-shadow: 0 4px 20px rgba(0,0,0,0.04); 
                transition: transform 0.2s;
            }
            div[data-testid="metric-container"]:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 24px rgba(0,0,0,0.08);
            }
            
            /* Expander */
            .streamlit-expanderHeader {
                background-color: #FFFFFF;
                border-radius: 8px;
                border: 1px solid #E9ECEF;
                color: #343A40;
                font-weight: 600;
            }
            
            /* Dataframe */
            .stDataFrame {
                border: 1px solid #DEE2E6;
                border-radius: 8px;
            }
            
            /* Custom Highlight for Admin Section if it has a specific wrapper (Simulated) */
            hr { margin: 2rem 0; border-color: #DEE2E6; }
        </style>
        """
