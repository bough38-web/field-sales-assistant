import pandas as pd
import numpy as np
from datetime import datetime
import streamlit as st

@st.cache_data(show_spinner=False)
def calculate_ai_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate AI Opportunity Scores (0-100) using high-speed Vectorized Pandas operations.
    Optimal for datasets up to 200k+ rows.
    """
    if df.empty:
        return df

    df = df.copy()
    now = pd.Timestamp.now()
    
    # 1. Precalculate Days Diff (Vectorized)
    # Coerce errors to NaT, then fillna with distant future
    permit_dates = pd.to_datetime(df['인허가일자'], errors='coerce')
    mod_dates = pd.to_datetime(df['최종수정시점'], errors='coerce')
    
    d_permit = (now - permit_dates).dt.days.fillna(9999)
    d_mod = (now - mod_dates).dt.days.fillna(9999)
    
    # Factor 1: Recency (40 pts)
    # Conditions prioritized by severity
    recency_conditions = [
        (d_permit <= 7),
        (d_permit <= 30),
        (d_mod <= 7)
    ]
    recency_values = [40, 30, 25]
    recency_comments = ["🔥신규(7일내)", "✨신규(1달내)", "🔄최근변동"]
    
    df['recency_pts'] = np.select(recency_conditions, recency_values, default=10)
    df['recency_comment'] = np.select(recency_conditions, recency_comments, default="")
    
    # Factor 2: Status (30 pts)
    status_str = df['영업상태명'].fillna('').astype(str)
    is_open = status_str.str.contains('영업|정상')
    is_closed = status_str.str.contains('폐업')
    
    df['status_pts'] = np.where(is_open, 30, np.where(is_closed, 20, 0))
    df['status_comment'] = np.where(is_closed, "⚠️폐업관리", "")
    
    # Factor 3: Scale/Area (20 pts)
    area_val = pd.to_numeric(df['소재지면적'], errors='coerce').fillna(0)
    df['area_pts'] = np.where(area_val >= 330, 20, np.where(area_val >= 100, 10, 5))
    df['area_comment'] = np.where(area_val >= 330, "🏢대형", "")
    
    # Factor 4: Type (10 pts)
    type_str = df['업태구분명'].fillna('').astype(str)
    is_medical = type_str.str.contains('병원|의원')
    df['type_pts'] = np.where(is_medical, 10, 5)
    df['type_comment'] = np.where(is_medical, "🏥병원", "")
    
    # Combine Scores
    df['AI_Score'] = (df['recency_pts'] + df['status_pts'] + df['area_pts'] + df['type_pts']).clip(0, 100)
    
    # [FIX] Fully Vectorized Comment Joining - 100x faster than .apply(axis=1)
    # Join non-empty comments by concatenating with a space
    df['AI_Comment'] = (
        df['recency_comment'].fillna('') + ' ' + 
        df['status_comment'].fillna('') + ' ' + 
        df['area_comment'].fillna('') + ' ' + 
        df['type_comment'].fillna('')
    ).str.strip().str.replace(r'\s+', ' ', regex=True)
    
    # Clean up temporary columns
    df = df.drop(columns=['recency_pts', 'recency_comment', 'status_pts', 'status_comment', 'area_pts', 'area_comment', 'type_pts', 'type_comment'])
    
    return df
