import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import certifi

# ตั้งค่าหน้ากระดาษ
st.set_page_config(page_title="Airbnb Dashboard", layout="wide")

# --- CSS สำหรับตกแต่งหน้าเว็บ ---
st.markdown("""
<style>
    /* ปรับ Metric Cards */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 15px 20px;
        border-radius: 12px;
        color: white;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    div[data-testid="stMetric"] label {
        color: rgba(255, 255, 255, 0.85) !important;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: white !important;
        font-weight: 700 !important;
    }
    /* หัวข้อหลัก */
    .main-title {
        text-align: center;
        padding: 10px 0 5px 0;
    }
    .main-title h1 {
        background: linear-gradient(120deg, #FF5A5F, #FC642D, #FF5A5F);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        font-weight: 800;
    }
    .main-title p {
        color: #888;
        font-size: 1.1rem;
    }
    /* Section headers */
    .section-header {
        padding: 4px 12px;
        border-left: 3px solid #FF5A5F;
        margin: 15px 0 8px 0;
    }
    .section-header h4 {
        color: #FF5A5F;
        font-size: 1rem;
        font-weight: 600;
        margin: 0;
    }
</style>
""", unsafe_allow_html=True)

# --- หัวข้อหลัก ---
st.markdown("""
<div class="main-title">
    <h1>Airbnb Dashboard</h1>
    <p>วิเคราะห์ข้อมูลที่พัก Airbnb จาก MongoDB</p>
</div>
""", unsafe_allow_html=True)

# --- ส่วนการเชื่อมต่อ MongoDB ---

@st.cache_resource
def init_mongo_client():
    uri = st.secrets["mongo"]["uri"]
    client = MongoClient(
        uri,
        tlsCAFile=certifi.where(),
        tlsAllowInvalidCertificates=True
    )
    return client

def get_airbnb_collection():
    client = init_mongo_client()
    db = client["sample_airbnb"]
    return db["listingsAndReviews"]

# --- ดึงข้อมูลจาก MongoDB และแปลงเป็น DataFrame (ใช้ cache เพื่อไม่ต้องโหลดซ้ำ) ---

@st.cache_data(ttl=600)
def load_airbnb_data():
    """ดึงข้อมูลจาก MongoDB แล้วแปลงเป็น DataFrame ที่พร้อมใช้งาน"""
    collection = get_airbnb_collection()
    
    # ดึงเฉพาะ field ที่ต้องใช้ (เพื่อความเร็ว)
    projection = {
        'name': 1,
        'summary': 1,
        'property_type': 1,
        'room_type': 1,
        'bed_type': 1,
        'bedrooms': 1,
        'beds': 1,
        'bathrooms': 1,
        'price': 1,
        'amenities': 1,
        'accommodates': 1,
        'address.country': 1,
        'address.market': 1,
        'address.suburb': 1,
        'address.government_area': 1,
        'review_scores.review_scores_rating': 1,
        'number_of_reviews': 1,
        'host.host_name': 1,
        'images.picture_url': 1,
    }
    
    cursor = collection.find({}, projection)
    data = list(cursor)
    
    if not data:
        return pd.DataFrame()
    
    df = pd.DataFrame(data)
    
    # ลบ _id
    if '_id' in df.columns:
        df = df.drop(columns=['_id'])
    
    # แตก nested fields ออกมา
    # address
    if 'address' in df.columns:
        df['country'] = df['address'].apply(lambda x: x.get('country', '') if isinstance(x, dict) else '')
        df['market'] = df['address'].apply(lambda x: x.get('market', '') if isinstance(x, dict) else '')
        df['suburb'] = df['address'].apply(lambda x: x.get('suburb', '') if isinstance(x, dict) else '')
        df.drop(columns=['address'], inplace=True)
    
    # review_scores
    if 'review_scores' in df.columns:
        df['rating'] = df['review_scores'].apply(
            lambda x: x.get('review_scores_rating', None) if isinstance(x, dict) else None
        )
        df.drop(columns=['review_scores'], inplace=True)
    
    # host
    if 'host' in df.columns:
        df['host_name'] = df['host'].apply(lambda x: x.get('host_name', '') if isinstance(x, dict) else '')
        df.drop(columns=['host'], inplace=True)
    
    # images
    if 'images' in df.columns:
        df['picture_url'] = df['images'].apply(lambda x: x.get('picture_url', '') if isinstance(x, dict) else '')
        df.drop(columns=['images'], inplace=True)
    
    # แปลง price เป็นตัวเลข (อาจเป็น Decimal128)
    if 'price' in df.columns:
        df['price'] = pd.to_numeric(df['price'].apply(lambda x: float(str(x)) if x else None), errors='coerce')
    
    # แปลง bedrooms, beds, bathrooms เป็นตัวเลข
    for col in ['bedrooms', 'beds', 'bathrooms', 'accommodates', 'number_of_reviews', 'rating']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # นับจำนวน amenities
    if 'amenities' in df.columns:
        df['amenities_count'] = df['amenities'].apply(lambda x: len(x) if isinstance(x, list) else 0)
    
    return df


# --- เริ่มแสดงผล Dashboard ---

try:
    with st.spinner("กำลังโหลดข้อมูลจาก MongoDB Atlas..."):
        df = load_airbnb_data()
    
    if df.empty:
        st.warning("เชื่อมต่อสำเร็จ แต่ไม่พบข้อมูลใน Collection 'listingsAndReviews'")
        st.stop()
    
    # ============================================================
    # SIDEBAR: ตัวกรอง (Filters)
    # ============================================================
    with st.sidebar:
        st.header("ตัวกรองข้อมูล")
        st.markdown("---")
        
        # กรองตามประเทศ
        countries = sorted(df['country'].dropna().unique())
        selected_country = st.selectbox("เลือกประเทศ", options=["ทั้งหมด"] + countries)
        
        # กรองตามประเภทที่พัก
        property_types = sorted(df['property_type'].dropna().unique())
        selected_property = st.selectbox("ประเภทที่พัก", options=["ทั้งหมด"] + list(property_types))
        
        # กรองตามประเภทห้อง
        room_types = sorted(df['room_type'].dropna().unique())
        selected_room = st.selectbox("ประเภทห้อง", options=["ทั้งหมด"] + list(room_types))
        
        # กรองตามราคา
        st.markdown("---")
        min_price = int(df['price'].min()) if df['price'].notna().any() else 0
        max_price = int(df['price'].max()) if df['price'].notna().any() else 10000
        # จำกัด max ที่ 1000 เพื่อไม่ให้ slider ยาวเกินไป
        slider_max = min(max_price, 1000)
        price_range = st.slider(
            "ช่วงราคา ($/คืน)",
            min_value=min_price,
            max_value=slider_max,
            value=(min_price, slider_max),
        )
    
    # ============================================================
    # กรองข้อมูลตาม Filter
    # ============================================================
    filtered_df = df.copy()
    
    if selected_country != "ทั้งหมด":
        filtered_df = filtered_df[filtered_df['country'] == selected_country]
    
    if selected_property != "ทั้งหมด":
        filtered_df = filtered_df[filtered_df['property_type'] == selected_property]
    
    if selected_room != "ทั้งหมด":
        filtered_df = filtered_df[filtered_df['room_type'] == selected_room]
    
    filtered_df = filtered_df[
        (filtered_df['price'] >= price_range[0]) & 
        (filtered_df['price'] <= price_range[1])
    ]
    
    # ============================================================
    # ส่วนที่ 1: Metric Cards (ตัวเลขสถิติ)
    # ============================================================
    st.markdown('<div class="section-header"><h4>สถิติภาพรวม</h4></div>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("จำนวนที่พัก", f"{len(filtered_df):,}")
    with col2:
        avg_price = filtered_df['price'].mean()
        st.metric("ราคาเฉลี่ย", f"${avg_price:,.0f}/คืน" if pd.notna(avg_price) else "N/A")
    with col3:
        avg_rating = filtered_df['rating'].mean()
        st.metric("คะแนนเฉลี่ย", f"{avg_rating:.1f}/100" if pd.notna(avg_rating) else "N/A")
    with col4:
        total_reviews = filtered_df['number_of_reviews'].sum()
        st.metric("รีวิวทั้งหมด", f"{int(total_reviews):,}" if pd.notna(total_reviews) else "N/A")

    st.markdown("---")
    
    # ============================================================
    # ส่วนที่ 2: กราฟ 2 คอลัมน์
    # ============================================================
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        st.markdown('<div class="section-header"><h4>ประเภทห้องพัก</h4></div>', unsafe_allow_html=True)
        room_counts = filtered_df['room_type'].value_counts()
        fig_pie = go.Figure(go.Pie(
            values=room_counts.values,
            labels=room_counts.index,
            hole=0.4,
            marker=dict(colors=['#FF5A5F', '#2196F3', '#4CAF50', '#FF9800']),
            textposition='outside',
            textinfo='percent+label',
            textfont_size=13,
        ))
        fig_pie.update_layout(
            showlegend=True,
            legend=dict(orientation='h', yanchor='bottom', y=-0.15, xanchor='center', x=0.5),
            margin=dict(t=10, b=40, l=10, r=10),
            height=380,
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with chart_col2:
        st.markdown('<div class="section-header"><h4>การกระจายราคา</h4></div>', unsafe_allow_html=True)
        price_data = filtered_df['price'].dropna()
        if not price_data.empty:
            price_data = price_data[price_data <= 500]
            import numpy as np
            counts, bin_edges = np.histogram(price_data, bins=30)
            bin_centers = [(bin_edges[i] + bin_edges[i+1]) / 2 for i in range(len(counts))]
            fig_price = go.Figure(go.Bar(
                x=[f'{int(b)}' for b in bin_centers],
                y=counts,
                marker=dict(color='#FC642D'),
            ))
            fig_price.update_layout(
                xaxis_title='ราคา ($/คืน)',
                yaxis_title='จำนวนที่พัก',
                margin=dict(t=10, b=10, l=10, r=10),
                height=380,
                showlegend=False,
            )
            st.plotly_chart(fig_price, use_container_width=True)
        else:
            st.info("ไม่มีข้อมูลราคา")
    
    # ============================================================
    # ส่วนที่ 3: กราฟ 2 คอลัมน์ (ประเภทที่พัก + คะแนนรีวิว)
    # ============================================================
    chart_col3, chart_col4 = st.columns(2)
    
    with chart_col3:
        st.markdown('<div class="section-header"><h4>ประเภทที่พักยอดนิยม (Top 10)</h4></div>', unsafe_allow_html=True)
        property_counts = filtered_df['property_type'].value_counts().head(10)
        st.bar_chart(property_counts, color="#764ba2", horizontal=True)
    
    with chart_col4:
        st.markdown('<div class="section-header"><h4>การกระจายคะแนนรีวิว</h4></div>', unsafe_allow_html=True)
        rating_data = filtered_df['rating'].dropna()
        if not rating_data.empty:
            bins = [0, 20, 40, 60, 80, 90, 95, 100]
            labels = ['0-20', '21-40', '41-60', '61-80', '81-90', '91-95', '96-100']
            rating_binned = pd.cut(rating_data, bins=bins, labels=labels, right=True)
            rating_dist = rating_binned.value_counts().sort_index()
            fig_rating = go.Figure(go.Bar(
                x=rating_dist.index.astype(str),
                y=rating_dist.values,
                marker_color='#667eea',
            ))
            fig_rating.update_layout(
                xaxis_title='ช่วงคะแนนรีวิว',
                yaxis_title='จำนวนที่พัก',
                margin=dict(t=10, b=10, l=10, r=10),
                height=350,
            )
            st.plotly_chart(fig_rating, use_container_width=True)
        else:
            st.info("ไม่มีข้อมูลคะแนนรีวิว")
    
    st.markdown("---")
    
    # ============================================================
    # ส่วนที่ 4: ราคาเฉลี่ยตามประเทศ
    # ============================================================
    st.markdown('<div class="section-header"><h4>ราคาเฉลี่ยตามประเทศ</h4></div>', unsafe_allow_html=True)
    
    country_stats = filtered_df.groupby('country').agg(
        avg_price=('price', 'mean'),
        count=('name', 'count'),
        avg_rating=('rating', 'mean')
    ).round(1).sort_values('avg_price', ascending=False)
    
    country_stats.columns = ['ราคาเฉลี่ย ($)', 'จำนวนที่พัก', 'คะแนนเฉลี่ย']
    st.dataframe(country_stats, use_container_width=True)
    
    st.markdown("---")
    
    # ============================================================
    # ส่วนที่ 5: ตารางข้อมูลรายละเอียด
    # ============================================================
    st.markdown('<div class="section-header"><h4>ข้อมูลที่พักทั้งหมด</h4></div>', unsafe_allow_html=True)
    
    # เลือกคอลัมน์ที่จะแสดง
    display_cols = ['name', 'property_type', 'room_type', 'price', 'bedrooms', 'beds',
                    'bathrooms', 'accommodates', 'rating', 'number_of_reviews', 
                    'host_name', 'country', 'market']
    available_cols = [c for c in display_cols if c in filtered_df.columns]
    
    display_df = filtered_df[available_cols].copy()
    display_df.columns = ['ชื่อที่พัก', 'ประเภทที่พัก', 'ประเภทห้อง', 'ราคา ($)', 
                          'ห้องนอน', 'เตียง', 'ห้องน้ำ', 'รองรับ (คน)', 
                          'คะแนน', 'จำนวนรีวิว', 'ชื่อ Host', 'ประเทศ', 'พื้นที่'][:len(available_cols)]
    
    st.dataframe(
        display_df,
        use_container_width=True,
        height=400,
    )
    
    # แสดงจำนวนผลลัพธ์
    st.caption(f"แสดงผล {len(filtered_df):,} รายการ จากทั้งหมด {len(df):,} รายการ")

except PyMongoError as e:
    st.error(f"เกิดข้อผิดพลาดในการเชื่อมต่อ MongoDB: {e}")
    st.info("ลองตรวจสอบ: 1) IP Address ใน MongoDB Atlas  2) URI ใน secrets.toml  3) อินเทอร์เน็ต")
except Exception as e:
    st.error(f"เกิดข้อผิดพลาด: {e}")
    import traceback
    st.code(traceback.format_exc())
