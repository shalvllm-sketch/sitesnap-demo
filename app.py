import streamlit as st
import pandas as pd
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from fpdf import FPDF
import os
from datetime import datetime
import base64

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="SiteSnap Pro v3",
    page_icon="🏗️",
    layout="wide"
)

# --- 2. ADVANCED FREE IMAGE PROCESSING ---

def process_image(upload_file, project_name):
    """
    1. Checks for Blur
    2. Checks for Brightness
    3. Adds Watermark
    """
    # Convert to PIL Image
    image = Image.open(upload_file)
    img_array = np.array(image)
    
    warnings = []
    
    # A. BLUR DETECTION (Laplacian Variance)
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    variance = cv2.Laplacian(gray, cv2.CV_64F).var()
    if variance < 100: # Threshold for blur
        warnings.append("⚠️ Image is Blurry (Hold camera steady)")

    # B. BRIGHTNESS CHECK
    brightness = np.mean(gray)
    if brightness < 50:
        warnings.append("⚠️ Image is Too Dark (Turn on flash)")
    
    # C. WATERMARKING (Evidence Grade)
    draw = ImageDraw.Draw(image)
    
    # Dynamic font size based on image width
    font_size = int(image.width / 25) 
    
    # Text Content
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    watermark_text = f"{project_name} | {timestamp} | SiteSnap Pro"
    
    # Draw Text (White with Black Outline for visibility)
    x, y = 20, image.height - font_size - 20
    
    # Outline
    outline_range = 2
    for dx in range(-outline_range, outline_range+1):
        for dy in range(-outline_range, outline_range+1):
            draw.text((x+dx, y+dy), watermark_text, fill="black")
            
    # Main Text
    draw.text((x, y), watermark_text, fill="yellow")
    
    return image, warnings

# --- 3. PDF GENERATION ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Site Inspection Report', 0, 1, 'C')
        self.ln(10)

def generate_pdf(data_row, image_path):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Details
    pdf.cell(200, 10, txt=f"Project: {data_row['Project']}", ln=True)
    pdf.cell(200, 10, txt=f"Inspector: {data_row['Inspector']}", ln=True)
    pdf.cell(200, 10, txt=f"Date: {data_row['Date']}", ln=True)
    pdf.set_text_color(255, 0, 0) if data_row['Severity'] == 'CRITICAL' else pdf.set_text_color(0, 0, 0)
    pdf.cell(200, 10, txt=f"Severity: {data_row['Severity']}", ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(0, 10, txt=f"Notes: {data_row['Notes']}")
    
    # Image
    if os.path.exists(image_path):
        pdf.image(image_path, x=10, y=80, w=100)
    
    return pdf.output(dest='S').encode('latin-1')

# --- 4. UI & LOGIC ---

# Temporary Local Storage for Demo
if 'reports' not in st.session_state:
    st.session_state.reports = []

st.title("🏗️ SiteSnap Pro: AI Vision Edition")

# Tabs for better UI organization
tab1, tab2 = st.tabs(["📸 Capture & Analyze", "📄 Reports & PDF"])

with tab1:
    c1, c2 = st.columns([1, 1])
    
    with c1:
        st.subheader("Inspection Details")
        project = st.selectbox("Project", ["Downtown Site", "Warehouse B", "Highway 9"])
        inspector = st.text_input("Inspector", "Supervisor")
        category = st.selectbox("Category", ["Structural", "Safety", "Electrical", "Finish"])
        severity = st.select_slider("Severity", ["Low", "Medium", "High", "CRITICAL"])
        notes = st.text_area("Notes")

    with c2:
        st.subheader("Image Analysis")
        img_file = st.camera_input("Snap Photo")
        
        processed_img = None
        if img_file:
            # RUN ANALYSIS
            processed_img, warnings = process_image(img_file, project)
            
            # Show Analysis Results
            if warnings:
                for w in warnings:
                    st.warning(w)
            else:
                st.success("✅ Image Quality: Perfect")
            
            # Show Watermarked Preview
            st.image(processed_img, caption="Watermarked Evidence Preview", use_container_width=True)
            
            if st.button("💾 Submit Inspection"):
                # Save locally for this session
                # 1. Save Image
                if not os.path.exists("temp_images"): os.makedirs("temp_images")
                filename = f"temp_images/{datetime.now().strftime('%H%M%S')}.jpg"
                processed_img.save(filename)
                
                # 2. Save Data
                report_data = {
                    "Date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Project": project,
                    "Inspector": inspector,
                    "Severity": severity,
                    "Notes": notes,
                    "Image": filename
                }
                st.session_state.reports.append(report_data)
                st.success("Report Saved!")

with tab2:
    st.subheader("Generated Reports")
    
    if len(st.session_state.reports) > 0:
        for i, report in enumerate(st.session_state.reports):
            with st.expander(f"{report['Date']} - {report['Project']} ({report['Severity']})"):
                col_a, col_b = st.columns([1, 2])
                with col_a:
                    st.image(report['Image'])
                with col_b:
                    st.write(f"**Notes:** {report['Notes']}")
                    
                    # PDF BUTTON
                    pdf_bytes = generate_pdf(report, report['Image'])
                    st.download_button(
                        label="📄 Download Official PDF",
                        data=pdf_bytes,
                        file_name=f"Report_{i}.pdf",
                        mime='application/pdf'
                    )
    else:
        st.info("No reports submitted yet.")
