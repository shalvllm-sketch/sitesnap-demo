import streamlit as st
from bs4 import BeautifulSoup
from curl_cffi import requests
import urllib3
import json
import statistics

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="OneSearch Pro", page_icon="🛍️", layout="wide", initial_sidebar_state="expanded") 

# --- STATE MANAGEMENT ---
if "raw_results" not in st.session_state:
    st.session_state.raw_results = []
if "display_count" not in st.session_state:
    st.session_state.display_count = 12 
if "last_query" not in st.session_state:
    st.session_state.last_query = ""
if "diagnostics" not in st.session_state:
    st.session_state.diagnostics = ""

# --- REVOLUTIONARY CUSTOM CSS ---
st.markdown("""
<style>
    .stApp { background-color: #f8fafc; }
    
    /* FIX: Increased padding-top to prevent title cutoff */
    .block-container { padding-top: 4rem !important; max-width: 1200px; }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    .main-title {
        text-align: center;
        font-size: 3.5rem;
        font-weight: 900;
        background: -webkit-linear-gradient(45deg, #10b981, #3b82f6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 5px;
        line-height: 1.2;
    }
    
    .sub-title {
        text-align: center;
        color: #64748b;
        font-size: 1.1rem;
        margin-bottom: 40px;
        font-weight: 500;
    }

    .results-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 24px;
        margin-top: 10px;
        margin-bottom: 40px;
    }
    
    .product-card {
        background: #ffffff;
        border-radius: 20px;
        position: relative; 
        overflow: hidden;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        display: flex;
        flex-direction: column;
        border: 1px solid #e2e8f0;
        height: 100%;
        transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.2s ease;
    }
    .product-card:hover {
        transform: translateY(-6px);
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.05);
        border-color: #cbd5e1;
    }
    
    .score-badge {
        position: absolute;
        top: 16px;
        right: 16px;
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(4px);
        border: 2px solid;
        font-weight: 800;
        font-size: 0.85rem;
        padding: 6px 10px;
        border-radius: 12px;
        z-index: 10;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    
    .img-container {
        width: 100%;
        height: 220px;
        background-color: #ffffff;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 20px;
        border-bottom: 1px solid #f1f5f9;
    }
    .product-image { max-width: 100%; max-height: 100%; object-fit: contain; mix-blend-mode: multiply; }
    
    .card-content {
        padding: 20px;
        display: flex;
        flex-direction: column;
        flex-grow: 1;
        background: #ffffff;
    }
    
    .product-title {
        color: #1e293b; 
        font-size: 0.95rem; 
        font-weight: 600;
        line-height: 1.5;
        margin: 12px 0 16px 0;
        display: -webkit-box;
        -webkit-line-clamp: 3; 
        -webkit-box-orient: vertical;
        overflow: hidden;
        flex-grow: 1;
    }
    
    .price-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: auto;
        padding-top: 12px;
        border-top: 1px solid #f1f5f9;
    }
    .product-price { color: #0f172a; font-weight: 900; font-size: 1.35rem; margin: 0; letter-spacing: -0.5px; }
    
    .buy-btn {
        text-decoration: none; 
        background: linear-gradient(135deg, #0f172a, #1e293b); 
        color: #ffffff !important; 
        padding: 10px 18px; 
        border-radius: 10px; 
        font-size: 0.85rem; 
        font-weight: 700;
        transition: opacity 0.2s ease;
    }
    .buy-btn:hover { opacity: 0.9; }
</style>
""", unsafe_allow_html=True)

BROWSER_VERSION = "chrome120" 

def calculate_deal_scores(results, query):
    if not results: return results
    prices = [item['price_int'] for item in results if item['price_int'] > 0]
    median_price = statistics.median(prices) if prices else 1
    query_words = query.lower().split()
    
    for item in results:
        score = 70
        title_lower = item['title'].lower()
        match_count = sum(1 for word in query_words if word in title_lower)
        if match_count == len(query_words): score += 20
        elif match_count > 0: score += 10
        else: score -= 30
            
        if item['price_int'] > 0:
            ratio = item['price_int'] / median_price
            if ratio < 0.7: score += 15
            elif ratio < 0.9: score += 5
            elif ratio > 1.5: score -= 20
            
        item['score'] = max(10, min(99, int(score)))
        
        if item['score'] >= 85: item['score_color'] = "#10b981" 
        elif item['score'] >= 60: item['score_color'] = "#f59e0b" 
        else: item['score_color'] = "#ef4444" 
    return results

def clean_price(price_str):
    try: return int(float(price_str.replace('₹', '').replace(',', '').replace('Rs.', '').strip()))
    except: return 0

def scrape_amazon(query):
    search_term = query.replace(" ", "+")
    url = f"https://www.amazon.in/s?k={search_term}"
    products = []
    log = "Amazon: "
    try:
        response = requests.get(url, impersonate=BROWSER_VERSION, timeout=10, verify=False)
        log += f"Code {response.status_code} | "
        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.find_all('div', {'data-component-type': 's-search-result'})
        for card in cards[:12]:
            try:
                title_elem = card.find('h2')
                title = title_elem.text.strip() if title_elem else "Unknown"
                price_elem = card.find('span', class_='a-price-whole')
                price_str = f"₹{price_elem.text.strip()}" if price_elem else "N/A"
                price_int = clean_price(price_elem.text.strip()) if price_elem else 0
                link_elem = card.find('a', class_='a-link-normal')
                link = "https://www.amazon.in" + link_elem['href'] if link_elem else "#"
                img_elem = card.find('img', class_='s-image')
                image_url = img_elem['src'] if img_elem else "https://via.placeholder.com/200"
                if price_int > 0:
                    products.append({"platform": "Amazon", "title": title, "price": price_str, "price_int": price_int, "link": link, "image": image_url})
            except Exception: continue
    except Exception as e: log += f"Error: {str(e)[:30]}"
    return products, log

def scrape_nykaa(query):
    search_term = query.replace(" ", "%20")
    url = f"https://www.nykaa.com/search/result/?q={search_term}"
    products = []
    log = "Nykaa: "
    try:
        response = requests.get(url, impersonate=BROWSER_VERSION, timeout=10, verify=False)
        log += f"Code {response.status_code} | "
        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.find_all('div', class_='product-wrapper')
        if not cards: cards = soup.find_all('div', class_='css-1rd7vky')
        for card in cards[:12]:
            try:
                title_elem = card.find('div', class_='css-x3m308') or card.find('div', class_='product-title')
                title = title_elem.text.strip() if title_elem else "Unknown"
                price_elem = card.find('span', class_='css-111z9ua') or card.find('span', class_='product-price')
                price_str = price_elem.text.strip() if price_elem else "N/A"
                price_int = clean_price(price_str)
                link_elem = card.find('a')
                link = "https://www.nykaa.com" + link_elem['href'] if link_elem and 'href' in link_elem.attrs else "#"
                img_elem = card.find('img')
                image_url = img_elem['src'] if img_elem and 'src' in img_elem.attrs else "https://via.placeholder.com/200"
                if price_int > 0 and title != "Unknown":
                    products.append({"platform": "Nykaa", "title": title, "price": price_str, "price_int": price_int, "link": link, "image": image_url})
            except Exception: continue
    except Exception as e: log += f"Error: {str(e)[:30]}"
    return products, log

def scrape_myntra(query):
    search_term = query.replace(" ", "-")
    url = f"https://www.myntra.com/{search_term}"
    products = []
    log = "Myntra: "
    try:
        response = requests.get(url, impersonate=BROWSER_VERSION, timeout=10, verify=False)
        log += f"Code {response.status_code} | "
        soup = BeautifulSoup(response.text, "html.parser")
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string and 'searchData' in script.string:
                try:
                    json_text = script.string.split('window.__myx = ')[1].split(';</script>')[0]
                    items = json.loads(json_text).get('searchData', {}).get('results', {}).get('products', [])
                    for item in items[:12]:
                        title = f"{item.get('brand', '')} {item.get('productName', '')}"
                        price_int = item.get('price', 0)
                        price_str = f"₹{price_int}"
                        link = f"https://www.myntra.com/{item.get('landingPageUrl', '')}"
                        image_url = item.get('searchImage', "https://via.placeholder.com/200")
                        if price_int > 0:
                            products.append({"platform": "Myntra", "title": title.strip(), "price": price_str, "price_int": price_int, "link": link, "image": image_url})
                    break 
                except Exception: pass
    except Exception as e: log += f"Error: {str(e)[:30]}"
    return products, log

# --- SIDEBAR FILTERS ---
with st.sidebar:
    st.markdown("### ⚙️ Engine Controls")
    if st.session_state.raw_results:
        max_possible_price = max([item['price_int'] for item in st.session_state.raw_results]) if st.session_state.raw_results else 10000
        selected_platforms = st.multiselect("Target Platforms", ["Amazon", "Nykaa", "Myntra"], default=["Amazon", "Nykaa", "Myntra"])
        max_price = st.slider("Max Price (₹)", min_value=0, max_value=max_possible_price, value=max_possible_price, step=50)
        sort_by = st.selectbox("Sort Results By", ["Smart Deal Score 🔥", "Lowest Price ⬇️", "Highest Price ⬆️"])
    else:
        st.info("Run a search to unlock filters.")
        selected_platforms = ["Amazon", "Nykaa", "Myntra"]
        max_price = 999999
        sort_by = "Smart Deal Score 🔥"

# --- MAIN UI ---
st.markdown('<p class="main-title">OneSearch Pro</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Intelligent E-Commerce Aggregation</p>', unsafe_allow_html=True)

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    query = st.text_input("Search", placeholder="e.g., Maybelline Eyeliner, Running Shoes...", label_visibility="collapsed")

if query and query != st.session_state.last_query:
    st.session_state.last_query = query
    st.session_state.display_count = 12
    with st.spinner(f"⚡ Interrogating platforms for '{query}'..."):
        all_results = []
        amz_res, amz_log = scrape_amazon(query)
        nyk_res, nyk_log = scrape_nykaa(query)
        myn_res, myn_log = scrape_myntra(query)
        all_results.extend(amz_res)
        all_results.extend(nyk_res)
        all_results.extend(myn_res)
        
        all_results = calculate_deal_scores(all_results, query)
        st.session_state.raw_results = all_results
        st.session_state.diagnostics = f"{amz_log} <br> {nyk_log} <br> {myn_log}"
        st.rerun()

if st.session_state.raw_results:
    filtered_results = [item for item in st.session_state.raw_results if item['platform'] in selected_platforms and item['price_int'] <= max_price]
    
    if sort_by == "Lowest Price ⬇️": filtered_results.sort(key=lambda x: x['price_int'])
    elif sort_by == "Highest Price ⬆️": filtered_results.sort(key=lambda x: x['price_int'], reverse=True)
    elif sort_by == "Smart Deal Score 🔥": filtered_results.sort(key=lambda x: x['score'], reverse=True)

    items_to_show = filtered_results[:st.session_state.display_count]
    
    # CSS-Native Logo Generation
    html_parts = ['<div class="results-grid">']
    for item in items_to_show:
        # Generate crisp SVG-like typography logos natively
        if item['platform'] == 'Amazon':
            logo = '<span style="font-family: Arial, sans-serif; font-weight: 900; font-size: 1.2rem; color: #000; letter-spacing: -1px;">amazon<span style="color: #FF9900;">.in</span></span>'
        elif item['platform'] == 'Nykaa':
            logo = '<span style="font-family: Arial, sans-serif; font-weight: 900; font-size: 1.2rem; color: #FC2779; letter-spacing: 1px; text-transform: uppercase;">NYKAA</span>'
        elif item['platform'] == 'Myntra':
            logo = '<span style="font-family: Arial, sans-serif; font-weight: 900; font-size: 1.2rem; color: #FF3E6C; letter-spacing: 0px;">Myntra</span>'

        html_parts.append(
f'''<div class="product-card">
<div class="score-badge" style="border-color: {item['score_color']}; color: {item['score_color']};">🔥 {item['score']}</div>
<div class="img-container">
<img src="{item['image']}" class="product-image" loading="lazy">
</div>
<div class="card-content">
<div style="margin-bottom: 8px;">{logo}</div>
<h4 class="product-title">{item['title']}</h4>
<div class="price-row">
<p class="product-price">{item['price']}</p>
<a href="{item['link']}" target="_blank" class="buy-btn">Get Deal</a>
</div>
</div>
</div>'''
        )
    html_parts.append('</div>')
    
    st.markdown("".join(html_parts), unsafe_allow_html=True)
    
    if st.session_state.display_count < len(filtered_results):
        btn_col1, btn_col2, btn_col3 = st.columns([1, 2, 1])
        with btn_col2:
            if st.button("⬇️ Load More Deals", use_container_width=True):
                st.session_state.display_count += 12
                st.rerun()
elif query and not st.session_state.raw_results:
    st.error("No active deals found. Try refining your search.")
    


# import streamlit as st
# import pandas as pd
# import cv2
# import numpy as np
# from PIL import Image
# from fpdf import FPDF
# import os
# import csv
# from datetime import datetime

# # --- 1. CONFIGURATION ---
# st.set_page_config(
#     page_title="SiteSnap Compliance v5",
#     page_icon="🛡️",
#     layout="wide",
#     initial_sidebar_state="expanded"
# )

# # --- 2. THEME & CSS ---
# st.markdown("""
#     <style>
#     /* COMPLIANCE THEME */
#     h1, h2, h3 { color: #2c3e50; font-family: 'Segoe UI', sans-serif; }
#     .stApp { background-color: #f8f9fa; }
    
#     /* STATUS BADGES */
#     .status-ok { color: green; font-weight: bold; }
#     .status-alert { color: red; font-weight: bold; }
    
#     /* AUDIT LOG TABLE STYLE */
#     .audit-table { font-family: 'Courier New', monospace; font-size: 12px; }
#     </style>
# """, unsafe_allow_html=True)

# # --- 3. PERSISTENT STORAGE SETUP ---
# DATA_FILE = "compliance_reports.csv"
# LOG_FILE = "access_logs.csv"
# IMG_DIR = "evidence_photos"

# # Ensure directories exist
# if not os.path.exists(IMG_DIR):
#     os.makedirs(IMG_DIR)

# # Initialize Report Database
# if not os.path.exists(DATA_FILE):
#     pd.DataFrame(columns=[
#         "ID", "Timestamp", "Site", "User", "Role", "Risk", 
#         "Category", "Observation", "Status", "Image_Path"
#     ]).to_csv(DATA_FILE, index=False)

# # Initialize Audit Log (GENUINE LOGGING)
# if not os.path.exists(LOG_FILE):
#     pd.DataFrame(columns=[
#         "Timestamp", "User", "Role", "Event", "Session_ID"
#     ]).to_csv(LOG_FILE, index=False)

# # --- 4. AUTH & LOGGING FUNCTIONS ---

# def log_event(user, role, event):
#     """Writes a genuine event to the CSV log file."""
#     timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#     # Simulate a Session ID / IP signature for authenticity
#     session_sig = f"SESSION-{os.urandom(2).hex().upper()}"
    
#     with open(LOG_FILE, "a", newline="") as f:
#         writer = csv.writer(f)
#         writer.writerow([timestamp, user, role, event, session_sig])

# def check_login(username, password):
#     # HARDCODED USERS FOR DEMO
#     users = {
#         "worker": {"pwd": "123", "role": "Worker", "name": "John (Site A)"},
#         "manager": {"pwd": "456", "role": "Supervisor", "name": "Sarah (HQ)"},
#         "admin": {"pwd": "789", "role": "Admin", "name": "System Admin"}
#     }
    
#     if username in users and users[username]['pwd'] == password:
#         return users[username]
#     return None

# def save_report(site, user, role, risk, category, observation, image_file):
#     report_id = f"INC-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
#     timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
#     # IMAGE HANDLING FIX
#     img_path = "No Image"
#     if image_file is not None:
#         img_path = os.path.join(IMG_DIR, f"{report_id}.jpg")
#         with open(img_path, "wb") as f:
#             f.write(image_file.getbuffer())
    
#     new_record = {
#         "ID": report_id,
#         "Timestamp": timestamp,
#         "Site": site,
#         "User": user,
#         "Role": role,
#         "Risk": risk,
#         "Category": category,
#         "Observation": observation,
#         "Status": "Pending Review",
#         "Image_Path": img_path
#     }
    
#     # Append to CSV
#     df = pd.read_csv(DATA_FILE)
#     df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
#     df.to_csv(DATA_FILE, index=False)
    
#     # Log the action
#     log_event(user, role, f"Submitted Report {report_id}")
#     return report_id

# # --- 5. PDF GENERATOR ---
# class PDF(FPDF):
#     def header(self):
#         self.set_font('Arial', 'B', 14)
#         self.cell(0, 10, 'OFFICIAL SITE INSPECTION REPORT', 0, 1, 'C')
#         self.ln(5)
#     def footer(self):
#         self.set_y(-15)
#         self.set_font('Arial', 'I', 8)
#         self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

# def generate_pdf(record):
#     pdf = PDF()
#     pdf.add_page()
#     pdf.set_font("Arial", size=11)
    
#     # Content
#     fields = ["ID", "Timestamp", "Site", "User", "Risk", "Category", "Observation"]
#     for field in fields:
#         pdf.set_font("Arial", 'B', 11)
#         pdf.cell(40, 10, f"{field}:", 1)
#         pdf.set_font("Arial", '', 11)
#         pdf.cell(0, 10, str(record[field]), 1, 1)
        
#     # Image
#     if record['Image_Path'] != "No Image" and os.path.exists(record['Image_Path']):
#         pdf.ln(10)
#         pdf.cell(0, 10, "Attached Evidence:", 0, 1)
#         pdf.image(record['Image_Path'], w=100)
        
#     return pdf.output(dest='S').encode('latin-1')

# # --- 6. MAIN APP ---

# # A. LOGIN SCREEN
# if 'user' not in st.session_state:
#     c1, c2, c3 = st.columns([1,1,1])
#     with c2:
#         st.markdown("<br><br>", unsafe_allow_html=True)
#         st.title("🛡️ SiteSnap Login")
#         st.markdown("### Enterprise Access Portal")
        
#         with st.form("login"):
#             u = st.text_input("Username", placeholder="e.g. worker, manager, admin")
#             p = st.text_input("Password", type="password")
#             submitted = st.form_submit_button("Authenticate")
            
#             if submitted:
#                 valid_user = check_login(u, p)
#                 if valid_user:
#                     st.session_state.user = valid_user
#                     log_event(valid_user['name'], valid_user['role'], "Login Success")
#                     st.success("Access Granted.")
#                     st.rerun()
#                 else:
#                     st.error("Invalid Credentials.")
#     st.stop()

# # B. DASHBOARD (LOGGED IN)
# user = st.session_state.user
# role = user['role']

# # SIDEBAR
# with st.sidebar:
#     st.markdown(f"👤 **{user['name']}**")
#     st.markdown(f"🔑 **{role.upper()}**")
#     st.markdown("---")
    
#     # ROLE BASED NAVIGATION
#     menu = ["Logout"]
#     if role == "Worker":
#         menu = ["Submit Report", "Logout"]
#     elif role == "Supervisor":
#         menu = ["Dashboard", "Pending Reviews", "Logout"]
#     elif role == "Admin":
#         menu = ["Master Dashboard", "Audit Logs", "Data Export", "Logout"]
        
#     choice = st.radio("Navigation", menu)
    
#     if choice == "Logout":
#         log_event(user['name'], role, "Logout")
#         del st.session_state.user
#         st.rerun()

# # --- PAGES ---

# # 1. SUBMIT REPORT (FIXED UPLOAD)
# if choice == "Submit Report":
#     st.title("📝 New Incident Report")
    
#     with st.form("report_form", clear_on_submit=True):
#         c1, c2 = st.columns(2)
#         with c1:
#             site = st.selectbox("Site Location", ["Site A (Construction)", "Site B (Warehouse)", "Site C (Office)"])
#             risk = st.select_slider("Risk Level", ["Low", "Medium", "High", "CRITICAL"])
#         with c2:
#             cat = st.selectbox("Category", ["Safety", "Electrical", "Structural", "Personnel"])
            
#             # FIXED UPLOAD LOGIC
#             st.markdown("---")
#             st.markdown("**Attach Evidence:**")
#             upload_mode = st.radio("Input Mode", ["Use Camera", "Upload File"], horizontal=True)
            
#             img_file = None
#             if upload_mode == "Use Camera":
#                 img_file = st.camera_input("Take Photo")
#             else:
#                 img_file = st.file_uploader("Choose Image", type=['jpg', 'png', 'jpeg'])

#         obs = st.text_area("Observations / Notes")
#         submit = st.form_submit_button("🚀 Submit Report")
        
#         if submit:
#             if obs:
#                 # Save
#                 rid = save_report(site, user['name'], role, risk, cat, obs, img_file)
#                 st.success(f"✅ Report {rid} Submitted Successfully!")
#             else:
#                 st.error("Please add observation notes.")

# # 2. DASHBOARD (SUPERVISOR/ADMIN)
# elif choice in ["Dashboard", "Master Dashboard"]:
#     st.title("📊 Compliance Overview")
    
#     if os.path.exists(DATA_FILE):
#         df = pd.read_csv(DATA_FILE)
#         if not df.empty:
#             m1, m2, m3 = st.columns(3)
#             m1.metric("Total Reports", len(df))
#             m2.metric("Critical Risks", len(df[df['Risk'] == "CRITICAL"]))
#             m3.metric("Pending Review", len(df[df['Status'] == "Pending Review"]))
            
#             st.markdown("### Recent Activity")
#             st.dataframe(df.tail(10), use_container_width=True)
#         else:
#             st.info("No data available.")

# # 3. PENDING REVIEWS (SUPERVISOR)
# elif choice == "Pending Reviews":
#     st.title("📋 Pending Approvals")
#     df = pd.read_csv(DATA_FILE)
#     pending = df[df['Status'] == "Pending Review"]
    
#     if pending.empty:
#         st.success("All caught up! No pending reports.")
#     else:
#         for idx, row in pending.iterrows():
#             with st.expander(f"{row['ID']} - {row['Risk']} ({row['Site']})"):
#                 c1, c2 = st.columns([1, 2])
#                 with c1:
#                     if row['Image_Path'] != "No Image" and os.path.exists(row['Image_Path']):
#                         st.image(row['Image_Path'])
#                     else:
#                         st.write("No Image")
#                 with c2:
#                     st.write(f"**User:** {row['User']}")
#                     st.write(f"**Note:** {row['Observation']}")
                    
#                     if st.button("Download PDF", key=f"pdf_{idx}"):
#                         pdf = generate_pdf(row)
#                         st.download_button("Click to Download", pdf, file_name=f"{row['ID']}.pdf")

# # 4. AUDIT LOGS (ADMIN ONLY - GENUINE)
# elif choice == "Audit Logs":
#     st.title("🕵️ Security Audit Logs")
#     st.markdown("Tracking all login events and data submissions.")
    
#     if os.path.exists(LOG_FILE):
#         log_df = pd.read_csv(LOG_FILE)
#         # Show latest first
#         log_df = log_df.iloc[::-1]
#         st.dataframe(log_df, use_container_width=True)
#     else:
#         st.info("No logs generated yet.")

# # 5. DATA EXPORT (ADMIN ONLY)
# elif choice == "Data Export":
#     st.title("💾 Data Management")
#     st.write("Download the full compliance database for external auditing.")
    
#     if os.path.exists(DATA_FILE):
#         with open(DATA_FILE, "rb") as f:
#             st.download_button(
#                 label="📥 Download Full Database (CSV)",
#                 data=f,
#                 file_name="site_snap_full_dump.csv",
#                 mime="text/csv"
#             )
