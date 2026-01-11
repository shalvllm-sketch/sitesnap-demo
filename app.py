import streamlit as st
import pandas as pd
import cv2
import numpy as np
from PIL import Image
from fpdf import FPDF
import os
import csv
from datetime import datetime

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="SiteSnap Compliance v5",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. THEME & CSS ---
st.markdown("""
    <style>
    /* COMPLIANCE THEME */
    h1, h2, h3 { color: #2c3e50; font-family: 'Segoe UI', sans-serif; }
    .stApp { background-color: #f8f9fa; }
    
    /* STATUS BADGES */
    .status-ok { color: green; font-weight: bold; }
    .status-alert { color: red; font-weight: bold; }
    
    /* AUDIT LOG TABLE STYLE */
    .audit-table { font-family: 'Courier New', monospace; font-size: 12px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. PERSISTENT STORAGE SETUP ---
DATA_FILE = "compliance_reports.csv"
LOG_FILE = "access_logs.csv"
IMG_DIR = "evidence_photos"

# Ensure directories exist
if not os.path.exists(IMG_DIR):
    os.makedirs(IMG_DIR)

# Initialize Report Database
if not os.path.exists(DATA_FILE):
    pd.DataFrame(columns=[
        "ID", "Timestamp", "Site", "User", "Role", "Risk", 
        "Category", "Observation", "Status", "Image_Path"
    ]).to_csv(DATA_FILE, index=False)

# Initialize Audit Log (GENUINE LOGGING)
if not os.path.exists(LOG_FILE):
    pd.DataFrame(columns=[
        "Timestamp", "User", "Role", "Event", "Session_ID"
    ]).to_csv(LOG_FILE, index=False)

# --- 4. AUTH & LOGGING FUNCTIONS ---

def log_event(user, role, event):
    """Writes a genuine event to the CSV log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Simulate a Session ID / IP signature for authenticity
    session_sig = f"SESSION-{os.urandom(2).hex().upper()}"
    
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, user, role, event, session_sig])

def check_login(username, password):
    # HARDCODED USERS FOR DEMO
    users = {
        "worker": {"pwd": "123", "role": "Worker", "name": "John (Site A)"},
        "manager": {"pwd": "456", "role": "Supervisor", "name": "Sarah (HQ)"},
        "admin": {"pwd": "789", "role": "Admin", "name": "System Admin"}
    }
    
    if username in users and users[username]['pwd'] == password:
        return users[username]
    return None

def save_report(site, user, role, risk, category, observation, image_file):
    report_id = f"INC-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # IMAGE HANDLING FIX
    img_path = "No Image"
    if image_file is not None:
        img_path = os.path.join(IMG_DIR, f"{report_id}.jpg")
        with open(img_path, "wb") as f:
            f.write(image_file.getbuffer())
    
    new_record = {
        "ID": report_id,
        "Timestamp": timestamp,
        "Site": site,
        "User": user,
        "Role": role,
        "Risk": risk,
        "Category": category,
        "Observation": observation,
        "Status": "Pending Review",
        "Image_Path": img_path
    }
    
    # Append to CSV
    df = pd.read_csv(DATA_FILE)
    df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
    df.to_csv(DATA_FILE, index=False)
    
    # Log the action
    log_event(user, role, f"Submitted Report {report_id}")
    return report_id

# --- 5. PDF GENERATOR ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'OFFICIAL SITE INSPECTION REPORT', 0, 1, 'C')
        self.ln(5)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def generate_pdf(record):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=11)
    
    # Content
    fields = ["ID", "Timestamp", "Site", "User", "Risk", "Category", "Observation"]
    for field in fields:
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(40, 10, f"{field}:", 1)
        pdf.set_font("Arial", '', 11)
        pdf.cell(0, 10, str(record[field]), 1, 1)
        
    # Image
    if record['Image_Path'] != "No Image" and os.path.exists(record['Image_Path']):
        pdf.ln(10)
        pdf.cell(0, 10, "Attached Evidence:", 0, 1)
        pdf.image(record['Image_Path'], w=100)
        
    return pdf.output(dest='S').encode('latin-1')

# --- 6. MAIN APP ---

# A. LOGIN SCREEN
if 'user' not in st.session_state:
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.title("🛡️ SiteSnap Login")
        st.markdown("### Enterprise Access Portal")
        
        with st.form("login"):
            u = st.text_input("Username", placeholder="e.g. worker, manager, admin")
            p = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Authenticate")
            
            if submitted:
                valid_user = check_login(u, p)
                if valid_user:
                    st.session_state.user = valid_user
                    log_event(valid_user['name'], valid_user['role'], "Login Success")
                    st.success("Access Granted.")
                    st.rerun()
                else:
                    st.error("Invalid Credentials.")
    st.stop()

# B. DASHBOARD (LOGGED IN)
user = st.session_state.user
role = user['role']

# SIDEBAR
with st.sidebar:
    st.markdown(f"👤 **{user['name']}**")
    st.markdown(f"🔑 **{role.upper()}**")
    st.markdown("---")
    
    # ROLE BASED NAVIGATION
    menu = ["Logout"]
    if role == "Worker":
        menu = ["Submit Report", "Logout"]
    elif role == "Supervisor":
        menu = ["Dashboard", "Pending Reviews", "Logout"]
    elif role == "Admin":
        menu = ["Master Dashboard", "Audit Logs", "Data Export", "Logout"]
        
    choice = st.radio("Navigation", menu)
    
    if choice == "Logout":
        log_event(user['name'], role, "Logout")
        del st.session_state.user
        st.rerun()

# --- PAGES ---

# 1. SUBMIT REPORT (FIXED UPLOAD)
if choice == "Submit Report":
    st.title("📝 New Incident Report")
    
    with st.form("report_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            site = st.selectbox("Site Location", ["Site A (Construction)", "Site B (Warehouse)", "Site C (Office)"])
            risk = st.select_slider("Risk Level", ["Low", "Medium", "High", "CRITICAL"])
        with c2:
            cat = st.selectbox("Category", ["Safety", "Electrical", "Structural", "Personnel"])
            
            # FIXED UPLOAD LOGIC
            st.markdown("---")
            st.markdown("**Attach Evidence:**")
            upload_mode = st.radio("Input Mode", ["Use Camera", "Upload File"], horizontal=True)
            
            img_file = None
            if upload_mode == "Use Camera":
                img_file = st.camera_input("Take Photo")
            else:
                img_file = st.file_uploader("Choose Image", type=['jpg', 'png', 'jpeg'])

        obs = st.text_area("Observations / Notes")
        submit = st.form_submit_button("🚀 Submit Report")
        
        if submit:
            if obs:
                # Save
                rid = save_report(site, user['name'], role, risk, cat, obs, img_file)
                st.success(f"✅ Report {rid} Submitted Successfully!")
            else:
                st.error("Please add observation notes.")

# 2. DASHBOARD (SUPERVISOR/ADMIN)
elif choice in ["Dashboard", "Master Dashboard"]:
    st.title("📊 Compliance Overview")
    
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        if not df.empty:
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Reports", len(df))
            m2.metric("Critical Risks", len(df[df['Risk'] == "CRITICAL"]))
            m3.metric("Pending Review", len(df[df['Status'] == "Pending Review"]))
            
            st.markdown("### Recent Activity")
            st.dataframe(df.tail(10), use_container_width=True)
        else:
            st.info("No data available.")

# 3. PENDING REVIEWS (SUPERVISOR)
elif choice == "Pending Reviews":
    st.title("📋 Pending Approvals")
    df = pd.read_csv(DATA_FILE)
    pending = df[df['Status'] == "Pending Review"]
    
    if pending.empty:
        st.success("All caught up! No pending reports.")
    else:
        for idx, row in pending.iterrows():
            with st.expander(f"{row['ID']} - {row['Risk']} ({row['Site']})"):
                c1, c2 = st.columns([1, 2])
                with c1:
                    if row['Image_Path'] != "No Image" and os.path.exists(row['Image_Path']):
                        st.image(row['Image_Path'])
                    else:
                        st.write("No Image")
                with c2:
                    st.write(f"**User:** {row['User']}")
                    st.write(f"**Note:** {row['Observation']}")
                    
                    if st.button("Download PDF", key=f"pdf_{idx}"):
                        pdf = generate_pdf(row)
                        st.download_button("Click to Download", pdf, file_name=f"{row['ID']}.pdf")

# 4. AUDIT LOGS (ADMIN ONLY - GENUINE)
elif choice == "Audit Logs":
    st.title("🕵️ Security Audit Logs")
    st.markdown("Tracking all login events and data submissions.")
    
    if os.path.exists(LOG_FILE):
        log_df = pd.read_csv(LOG_FILE)
        # Show latest first
        log_df = log_df.iloc[::-1]
        st.dataframe(log_df, use_container_width=True)
    else:
        st.info("No logs generated yet.")

# 5. DATA EXPORT (ADMIN ONLY)
elif choice == "Data Export":
    st.title("💾 Data Management")
    st.write("Download the full compliance database for external auditing.")
    
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "rb") as f:
            st.download_button(
                label="📥 Download Full Database (CSV)",
                data=f,
                file_name="site_snap_full_dump.csv",
                mime="text/csv"
            )
