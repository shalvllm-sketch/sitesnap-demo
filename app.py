import streamlit as st
from bs4 import BeautifulSoup
from curl_cffi import requests
import urllib3
import json
import re
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
    
    .debug-box {
        background-color: #f1f5f9;
        border-left: 4px solid #94a3b8;
        padding: 12px 16px;
        border-radius: 4px;
        font-size: 0.75rem;
        color: #64748b;
        font-family: monospace;
    }
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
        log += f"Parsed {len(products)} products."
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
        
        # FIXED: Nykaa injects all product data into a centralized script tag inside window.__PRELOADED_STATE__
        soup = BeautifulSoup(response.text, "html.parser")
        scripts = soup.find_all('script')
        found_data = False
        
        for script in scripts:
            if script.string and "window.__PRELOADED_STATE__" in script.string:
                try:
                    # Isolate the clean JSON payload cleanly via regex bounds
                    json_match = re.search(r'window\.__PRELOADED_STATE__\s*=\s*({.*?});', script.string)
                    if json_match:
                        data = json.loads(json_match.group(1))
                        # Dig straight into their structured product engine response
                        items = data.get('search', {}).get('products', [])
                        if not items:
                            # Secondary structural path if query maps straight to a store category layout
                            items = data.get('productListing', {}).get('products', [])
                        
                        log += f"Found {len(items)} items inside state payload. "
                        found_data = True
                        
                        for item in items[:12]:
                            title = item.get('name', 'Unknown Product')
                            price_int = item.get('finalPrice', item.get('price', 0))
                            price_str = f"₹{price_int}"
                            link = "https://www.nykaa.com" + item.get('imageUrl', '#') # Native deep route path placeholder
                            if 'slug' in item:
                                link = f"https://www.nykaa.com/{item['slug']}/p/{item.get('id', '')}"
                            image_url = item.get('imageUrl', "https://via.placeholder.com/200")
                            
                            if price_int > 0:
                                products.append({"platform": "Nykaa", "title": title, "price": price_str, "price_int": price_int, "link": link, "image": image_url})
                        break
                except Exception as e:
                    log += f"JSON Parsing Error: {str(e)[:30]} | "
        
        if not found_data:
            # Fallback to general HTML structures if page pattern changes back
            cards = soup.find_all('div', class_='product-wrapper') or soup.find_all('div', class_='css-1rd7vky')
            log += f"Fallback to HTML, found {len(cards)} cards. "
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
                    if price_int > 0:
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
        found_data = False
        
        for script in scripts:
            if script.string and 'window.__myx =' in script.string:
                try:
                    # Robust split using a clean regex target or standard substring boundaries to preserve trailing spaces safely
                    raw_text = script.string.strip()
                    json_text = raw_text.split('window.__myx =')[1].strip()
                    if json_text.endswith(';'):
                        json_text = json_text[:-1]
                    
                    data = json.loads(json_text)
                    items = data.get('searchData', {}).get('results', {}).get('products', [])
                    log += f"Found {len(items)} items in payload. "
                    found_data = True
                    
                    for item in items[:12]:
                        title = f"{item.get('brand', '')} {item.get('productName', '')}"
                        price_int = item.get('price', 0)
                        price_str = f"₹{price_int}"
                        link = f"https://www.myntra.com/{item.get('landingPageUrl', '')}"
                        image_url = item.get('searchImage', "https://via.placeholder.com/200")
                        if price_int > 0:
                            products.append({"platform": "Myntra", "title": title.strip(), "price": price_str, "price_int": price_int, "link": link, "image": image_url})
                    break 
                except Exception as json_err:
                    log += f"JSON Error: {str(json_err)[:20]} | "
                    
        if not found_data: log += "Failed to find window.__myx container."
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

if st.session_state.diagnostics:
    with st.expander("🛠️ View Engine Diagnostics"):
        st.markdown(f'<div class="debug-box">{st.session_state.diagnostics}</div>', unsafe_allow_html=True)

if st.session_state.raw_results:
    filtered_results = [item for item in st.session_state.raw_results if item['platform'] in selected_platforms and item['price_int'] <= max_price]
    
    if sort_by == "Lowest Price ⬇️": filtered_results.sort(key=lambda x: x['price_int'])
    elif sort_by == "Highest Price ⬆️": filtered_results.sort(key=lambda x: x['price_int'], reverse=True)
    elif sort_by == "Smart Deal Score 🔥": filtered_results.sort(key=lambda x: x['score'], reverse=True)

    items_to_show = filtered_results[:st.session_state.display_count]
    
    html_parts = ['<div class="results-grid">']
    for item in items_to_show:
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
