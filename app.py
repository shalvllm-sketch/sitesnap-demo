import streamlit as st
import pandas as pd
import os
from datetime import datetime
from PIL import Image

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="SiteSnap Pro 🏗️",
    page_icon="👷",
    layout="wide"
)

# --- 2. CSS: INDUSTRIAL THEME ---
st.markdown("""
    <style>
    /* Global Font */
    html, body, [class*="css"] {
        font-family: 'Helvetica', 'Arial', sans-serif;
    }
    
    /* Headers */
    h1, h2, h3 {
        color: #0f2942; /* Navy Blue */
        font-weight: 700;
    }
    
    /* Buttons */
    .stButton > button {
        background-color: #ff6f00; /* Safety Orange */
        color: white;
        border-radius: 5px;
        border: none;
        font-weight: bold;
        padding: 10px 20px;
    }
    .stButton > button:hover {
        background-color: #e65100;
        color: white;
    }
    
    /* Metrics */
    div[data-testid="stMetricValue"] {
        color: #0f2942;
    }
    
    /* Custom Card for Reports */
    .report-card {
        background-color: #f8f9fa;
        border-left: 5px solid #0f2942;
        padding: 15px;
        border-radius: 5px;
        margin-bottom: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. BACKEND: FILE SYSTEM ---
DATA_FILE = "site_reports.csv"
IMG_FOLDER = "site_images"

# Ensure storage exists
if not os.path.exists(IMG_FOLDER):
    os.makedirs(IMG_FOLDER)

if not os.path.exists(DATA_FILE):
    # Create CSV with headers if it doesn't exist
    df = pd.DataFrame(columns=["Date", "Project", "Inspector", "Category", "Severity", "Notes", "Image_Path"])
    df.to_csv(DATA_FILE, index=False)

# --- 4. FUNCTIONS ---
def save_report(project, inspector, category, severity, notes, image_file):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    img_path = "No Image"
    
    # Save Image if exists
    if image_file:
        # Create unique filename: project_timestamp.jpg
        safe_project = project.replace(" ", "_")
        safe_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_project}_{safe_time}.jpg"
        img_path = os.path.join(IMG_FOLDER, filename)
        
        # Save to folder
        with open(img_path, "wb") as f:
            f.write(image_file.getbuffer())
    
    # Save Data to CSV
    new_data = {
        "Date": timestamp,
        "Project": project,
        "Inspector": inspector,
        "Category": category,
        "Severity": severity,
        "Notes": notes,
        "Image_Path": img_path
    }
    
    df = pd.read_csv(DATA_FILE)
    df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
    df.to_csv(DATA_FILE, index=False)
    return True

def load_data():
    return pd.read_csv(DATA_FILE)

# --- 5. SIDEBAR ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3028/3028573.png", width=80)
    st.markdown("## SiteSnap Pro")
    st.markdown("---")
    menu = st.radio("Navigation", ["📱 New Inspection", "📊 Dashboard", "📁 Gallery"])
    st.markdown("---")
    st.info("Logged in as: **Supervisor**")

# --- 6. PAGE: NEW INSPECTION ---
if menu == "📱 New Inspection":
    st.title("👷 New Site Inspection")
    st.markdown("Log a defect, safety issue, or progress update.")
    
    with st.form("inspection_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            project = st.selectbox("Project Site", ["Downtown Plaza", "Riverside Apts", "Central Mall", "HQ Renovation"])
            inspector = st.text_input("Inspector Name", value="John Doe")
            severity = st.select_slider("Severity Level", options=["Low", "Medium", "High", "CRITICAL"], value="Low")
            
        with col2:
            category = st.selectbox("Category", ["Safety Hazard", "Structural Crack", "Plumbing Leak", "Electrical", "Finish/Paint", "General Progress"])
            # CAMERA INPUT (Works on mobile!)
            photo = st.camera_input("Take Photo")
            # Fallback upload if camera not needed
            uploaded_file = st.file_uploader("Or Upload Image", type=['jpg','png','jpeg'])
            
        notes = st.text_area("Description / Notes", placeholder="Describe the issue in detail...")
        
        image_to_save = photo if photo else uploaded_file
        
        submitted = st.form_submit_button("💾 Submit Report")
        
        if submitted:
            if project and notes:
                save_report(project, inspector, category, severity, notes, image_to_save)
                st.success(f"Report logged for **{project}** successfully!")
            else:
                st.error("Please fill in Project and Notes.")

# --- 7. PAGE: DASHBOARD ---
elif menu == "📊 Dashboard":
    st.title("📊 Project Overview")
    
    df = load_data()
    
    # Top Level Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Reports", len(df))
    m2.metric("Critical Issues", len(df[df['Severity']=="CRITICAL"]))
    m3.metric("Safety Hazards", len(df[df['Category']=="Safety Hazard"]))
    m4.metric("Active Sites", df['Project'].nunique())
    
    st.markdown("---")
    
    # Filters
    col1, col2 = st.columns(2)
    with col1:
        filter_proj = st.multiselect("Filter by Project", df['Project'].unique())
    with col2:
        filter_sev = st.multiselect("Filter by Severity", df['Severity'].unique())
        
    # Apply Filters
    if filter_proj:
        df = df[df['Project'].isin(filter_proj)]
    if filter_sev:
        df = df[df['Severity'].isin(filter_sev)]
        
    # Display Table
    st.dataframe(df, use_container_width=True)
    
    # Export Button (Upsell Feature!)
    @st.cache_data
    def convert_df(df):
        return df.to_csv(index=False).encode('utf-8')

    csv = convert_df(df)
    st.download_button(
        label="📥 Download Report (CSV)",
        data=csv,
        file_name='site_report.csv',
        mime='text/csv',
    )

# --- 8. PAGE: GALLERY ---
elif menu == "📁 Gallery":
    st.title("📁 Site Photos")
    
    df = load_data()
    
    if df.empty:
        st.info("No photos logged yet.")
    else:
        # Filter out rows with no image
        df_imgs = df[df['Image_Path'] != "No Image"]
        
        # Grid Layout
        cols = st.columns(3)
        for index, row in df_imgs.iterrows():
            if os.path.exists(row['Image_Path']):
                with cols[index % 3]:
                    # Dynamic Border Color based on Severity
                    border_color = "red" if row['Severity'] == "CRITICAL" else "#ddd"
                    
                    st.image(row['Image_Path'], use_container_width=True)
                    st.markdown(f"""
                        <div class="report-card" style="border-left: 5px solid {border_color}">
                            <b>{row['Project']}</b><br>
                            <span style="color:grey; font-size:12px">{row['Date']}</span><br>
                            <span style="font-weight:bold; color:{border_color}">{row['Severity']}</span>: {row['Category']}<br>
                            <small>{row['Notes']}</small>
                        </div>
                    """, unsafe_allow_html=True)
