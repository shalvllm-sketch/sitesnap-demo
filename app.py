import streamlit as st

st.title("Internal File Transfer Portal")
st.write("Click the button below to download the authorized tool.")

# Path to the file in your GitHub repository
file_path = "your_program.exe" 

try:
    with open(file_path, "rb") as file:
        btn = st.download_button(
            label="📥 Download Executable",
            data=file,
            file_name="your_program.exe",
            mime="application/octet-stream"
        )
except FileNotFoundError:
    st.error("File not found. Make sure the file name matches exactly in your GitHub repo.")
