import streamlit as st
from pymongo import MongoClient

@st.cache_resource
def get_mongo_client():
    if "client" not in st.session_state:
        # ดึง URI จาก secrets.toml (ที่ทำไว้ในหน้าหลัก)
        uri = st.secrets["mongo"]["uri"]
        st.session_state.client = MongoClient(uri)
    return st.session_state.client

def get_db(db_name="sample_mflix"):
    client = get_mongo_client()
    return client[db_name]