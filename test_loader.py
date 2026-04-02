import sys
sys.path.append('.')
from src import data_loader
import pandas as pd
import streamlit as st

st.cache_data.clear()
zip_paths = ["data/LOCALDATA_NOWMON_CSV_3월.zip"]

mock_dist = pd.DataFrame({'관리지사': [], '영업구역 수정': [], 'SP담당': [], '소재지전체주소': []})
df, _, _, stats = data_loader.load_and_process_data(zip_paths, mock_dist)

if df is not None:
    if '최종수정시점' in df.columns:
        print("Successfully created '최종수정시점'")
        print(df[['사업장명', '인허가일자', '폐업일자', '최종수정시점']].head(10))
    else:
        print("'최종수정시점' is missing!")

