import streamlit as st
import pandas as pd
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import certifi

# ตั้งค่าหน้ากระดาษ
st.set_page_config(page_title="Starbucks Analysis", layout="wide")
st.title("Starbucks Locations in Thailand")

# --- ส่วนการเชื่อมต่อ MongoDB (ห้ามลบ) ---

@st.cache_resource
def init_mongo_client():
    if "db_client" not in st.session_state:
        # ดึง URI จาก secrets.toml
        uri = st.secrets["mongo"]["uri"]
        # ใช้ certifi เพื่อแก้ปัญหา SSL Handshake บน macOS
        st.session_state.db_client = MongoClient(
            uri, 
            tlsCAFile=certifi.where(),
            tlsAllowInvalidCertificates=True
        )
    return st.session_state.db_client

def get_db():
    client = init_mongo_client()
    # ชื่อ Database ที่คุณสร้างใน MongoDB Compass
    return client["test_db"]

def get_collection():
    db = get_db()
    # ชื่อ Collection ที่คุณ Import ไฟล์ CSV เข้าไป
    return db["Starbucks"]

# --- ส่วนการแสดงผลบนหน้าเว็บ ---

try:
    starbuck_coll = get_collection()
    
    # ดึงข้อมูลเฉพาะสาขาในประเทศไทย (Country: TH)
    with st.spinner("กำลังโหลดข้อมูลจาก MongoDB..."):
        cursor = starbuck_coll.find({'Country': 'TH'})
        list_data = list(cursor)

    if list_data:
        # แปลงเป็น DataFrame เพื่อจัดการข้อมูลง่ายขึ้น
        df = pd.DataFrame(list_data)
        
        # ลบคอลัมน์ _id ของ MongoDB ออกเพื่อให้ตารางดูสวย
        if '_id' in df.columns:
            df = df.drop(columns=['_id'])

        # ส่วนที่ 1: แสดงสถิติเบื้องต้น
        st.metric("จำนวนสาขาทั้งหมดในไทย", f"{len(df)} แห่ง")

        # ส่วนที่ 2: แสดงแผนที่ (ข้อมูลต้องมี Latitude และ Longitude)
        st.subheader("📍 แผนที่สาขา Starbucks")
        # Streamlit ต้องการคอลัมน์ชื่อ lat และ lon
        map_df = df[['Latitude', 'Longitude']].rename(
            columns={'Latitude': 'lat', 'Longitude': 'lon'}
        )
        # แปลงข้อมูลเป็น float เพื่อป้องกันกรณีที่ข้อมูลจาก MongoDB เป็น String
        map_df['lat'] = pd.to_numeric(map_df['lat'], errors='coerce')
        map_df['lon'] = pd.to_numeric(map_df['lon'], errors='coerce')
        map_df = map_df.dropna(subset=['lat', 'lon'])
        
        st.map(map_df)

        # ส่วนที่ 3: แสดงตารางข้อมูล
        st.subheader("📋 ตารางข้อมูลสาขา")
        st.dataframe(df, use_container_width=True)
        
    else:
        st.warning("เชื่อมต่อสำเร็จ แต่ไม่พบข้อมูลใน Collection 'Starbucks'")

except PyMongoError as e:
    st.error(f"เกิดข้อผิดพลาดในการเชื่อมต่อ MongoDB: {e}")
except Exception as e:
    st.error(f"เกิดข้อผิดพลาด: {e}")