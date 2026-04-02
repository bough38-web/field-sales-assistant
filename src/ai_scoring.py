import pandas as pd
import numpy as np
from datetime import datetime
import streamlit as st

@st.cache_data(show_spinner=False)
def calculate_ai_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate AI Opportunity Scores (0-100) for each row.
    
    Factors:
    1. Recency (New Open/Change): 40 pts
    2. Status (Open > Closed): 30 pts
    3. Scale (Area): 20 pts
    4. Strategic Priority (Hospital > Others): 10 pts
    """
    if df.empty:
        return df

    now = pd.Timestamp.now()
    df = df.copy()
    
    # Initialize Score
    df['AI_Score'] = 0
    df['AI_Comment'] = ""

    # 1. Recency Score (40 pts)
    # Define columns to check
    # 인허가일자, 최종수정시점
    
    # Helper for days diff
    def get_days_diff(pipeline_date):
        try:
            val = pd.to_datetime(pipeline_date)
            if pd.isna(val): return 9999
            return (now - val).days
        except:
            return 9999

    # Vectorized calculation usually better, but robust loop for mixed types
    scores = []
    comments = []
    
    for idx, row in df.iterrows():
        s = 0
        c = []
        
        # Factor 1: Recency
        # Prioritize New Openings (Permit Date)
        d_permit = get_days_diff(row.get('인허가일자'))
        d_mod = get_days_diff(row.get('최종수정시점'))
        
        recency_pts = 0
        if d_permit <= 7:
            recency_pts = 40
            c.append("🔥신규(7일내)")
        elif d_permit <= 30:
            recency_pts = 30
            c.append("✨신규(1달내)")
        elif d_mod <= 7:
            recency_pts = 25
            c.append("🔄최근변동")
        else:
            recency_pts = 10
        
        s += recency_pts
        
        # Factor 2: Status (30 pts)
        status = str(row.get('영업상태명', ''))
        if '영업' in status or '정상' in status:
            s += 30
        elif '폐업' in status:
            # Closed is still an opportunity for asset recovery, but maybe lower score than active sales?
            # Or higher? Let's say opportunity "to sell new" => Open is better.
            # Opportunity "to retrieve" => Closed is better.
            # Let's assume Sales context: Open is 30, Closed is 20 (still important).
            s += 20
            c.append("⚠️폐업관리")
        
        # Factor 3: Scale/Area (20 pts)
        try:
            area = float(row.get('소재지면적', 0))
            if area >= 330: # 100py
                s += 20
                c.append("🏢대형")
            elif area >= 100: # 30py
                s += 10
            else:
                s += 5
        except:
            s += 5
            
        # Factor 4: Type (10 pts)
        btype = str(row.get('업태구분명', ''))
        if '병원' in btype or '의원' in btype:
            s += 10
            c.append("🏥병원")
        else:
            s += 5
            
        # Bonus: Random jitter to differentiate equal scores (0-5)
        # Using hash of name to be deterministic but varied
        # name_seed = int(hash(str(row.get('사업장명',''))) % 5)
        # s += name_seed 
        
        scores.append(min(s, 100))
        comments.append(" ".join(c))
        
    df['AI_Score'] = scores
    df['AI_Comment'] = comments
    
    return df
