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
if "current_scraped_page" not in st.session_state:
    st.session_state.current_scraped_page = 1

# --- CUSTOM CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    * { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #f8fafc; }
    .block-container { padding-top: 4rem !important; max-width: 1200px; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    .main-title {
        text-align: center;
        font-size: 3.8rem;
        font-weight: 800;
        background: linear-gradient(135deg, #0f172a 0%, #2563eb 50%, #3b82f6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 5px;
        letter-spacing: -1.5px;
        line-height: 1.1;
    }
    .sub-title {
        text-align: center;
        color: #64748b;
        font-size: 1.15rem;
        margin-bottom: 45px;
        font-weight: 400;
    }
    .results-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 28px;
        margin-top: 15px;
        margin-bottom: 40px;
    }
    .product-card {
        background: #ffffff;
        border-radius: 24px;
        position: relative; 
        overflow: hidden;
        box-shadow: 0 4px 20px -2px rgba(15, 23, 42, 0.04);
        display: flex;
        flex-direction: column;
        border: 1px solid rgba(226, 232, 240, 0.7);
        height: 100%;
        transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .product-card:hover {
        transform: translateY(-6px);
        box-shadow: 0 20px 30px -10px rgba(15, 23, 42, 0.12);
        border-color: #cbd5e1;
    }
    .score-badge {
        position: absolute;
        top: 16px;
        right: 16px;
        background: rgba(255, 255, 255, 0.9);
        backdrop-filter: blur(8px);
        border: 1px solid;
        font-weight: 700;
        font-size: 0.8rem;
        padding: 5px 10px;
        border-radius: 99px;
        z-index: 10;
    }
    .img-container {
        width: 100%;
        height: 240px;
        background-color: #ffffff;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 24px;
        border-bottom: 1px solid #f1f5f9;
    }
    .product-image { max-width: 100%; max-height: 100%; object-fit: contain; mix-blend-mode: multiply; }
    .card-content { padding: 24px; display: flex; flex-direction: column; flex-grow: 1; }
    .product-title {
        color: #1e293b; font-size: 0.95rem; font-weight: 600; line-height: 1.5;
        margin: 14px 0 20px 0; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;
        overflow: hidden; flex-grow: 1;
    }
    .price-row { display: flex; justify-content: space-between; align-items: center; margin-top: auto; padding-top: 14px; border-top: 1px solid #f1f5f9; }
    .product-price { color: #0f172a; font-weight: 800; font-size: 1.4rem; margin: 0; }
    .buy-btn { text-decoration: none; background: #0f172a; color: #ffffff !important; padding: 10px 20px; border-radius: 12px; font-size: 0.85rem; font-weight: 600; }
    .debug-box { background-color: #f1f5f9; border-left: 4px solid #94a3b8; padding: 12px 16px; border-radius: 8px; font-size: 0.75rem; color: #64748b; font-family: monospace; }
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
    try: return int(float(str(price_str).replace('₹', '').replace(',', '').replace('Rs.', '').replace('Rs', '').strip()))
    except: return 0

# --- PAGINATED SCRAPERS ---
def scrape_amazon(query, page=1):
    search_term = query.replace(" ", "+")
    url = f"https://www.amazon.in/s?k={search_term}&page={page}"
    products = []
    log = f"Amazon (Pg {page}): "
    try:
        response = requests.get(url, impersonate=BROWSER_VERSION, timeout=10, verify=False)
        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.find_all('div', {'data-component-type': 's-search-result'})
        for card in cards[:16]:
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
        log += f"Found {len(products)} items."
    except Exception as e: log += f"Error: {str(e)[:20]}"
    return products, log

def scrape_nykaa(query, page=1):
    search_term = query.replace(" ", "%20")
    url = f"https://www.nykaa.com/search/result/?q={search_term}&page_no={page}"
    products = []
    log = f"Nykaa (Pg {page}): "
    try:
        response = requests.get(url, impersonate=BROWSER_VERSION, timeout=10, verify=False)
        soup = BeautifulSoup(response.text, "html.parser")
        scripts = soup.find_all('script')
        found_data = False
        
        for script in scripts:
            if script.string and ('products' in script.string or 'finalPrice' in script.string):
                try:
                    text = script.string.strip()
                    if '=' in text: text = text.split('=', 1)[1].strip().rstrip(';')
                    data = json.loads(text)
                    
                    def search_dict_for_products(d):
                        if isinstance(d, dict):
                            if 'products' in d and isinstance(d['products'], list): return d['products']
                            for v in d.values():
                                res = search_dict_for_products(v)
                                if res: return res
                        elif isinstance(d, list):
                            for item in d:
                                res = search_dict_for_products(item)
                                if res: return res
                        return None
                    
                    items = search_dict_for_products(data)
                    if items:
                        for item in items[:16]:
                            title = item.get('name', item.get('title', 'Unknown Product'))
                            price_int = item.get('finalPrice', item.get('price', 0))
                            slug = item.get('slug', '')
                            link = f"https://www.nykaa.com/{slug}/p/{item.get('id', '')}" if slug else "https://www.nykaa.com"
                            image_url = item.get('imageUrl', "https://via.placeholder.com/200")
                            if price_int > 0:
                                products.append({"platform": "Nykaa", "title": title, "price": f"₹{price_int}", "price_int": price_int, "link": link, "image": image_url})
                        found_data = True
                        break
                except: continue
                
        if not found_data or len(products) == 0:
            cards = soup.select('[class*="product-wrapper"]') or soup.select('[class*="css-1rd7vky"]') or soup.select('[class*="productCard"]')
            for card in cards[:16]:
                try:
                    title_elem = card.find(['h1', 'h2', 'h3', 'h4', 'div'])
                    title = title_elem.text.strip() if title_elem else "Unknown"
                    price_str = "N/A"
                    for text_node in card.find_all(text=True):
                        if '₹' in text_node: price_str = text_node.strip(); break
                    price_int = clean_price(price_str)
                    link_elem = card.find('a')
                    link = "https://www.nykaa.com" + link_elem['href'] if link_elem else "#"
                    img_elem = card.find('img')
                    image_url = img_elem['src'] if img_elem else "https://via.placeholder.com/200"
                    if price_int > 0:
                        products.append({"platform": "Nykaa", "title": title, "price": f"₹{price_int}", "price_int": price_int, "link": link, "image": image_url})
                except Exception: continue
        log += f"Found {len(products)} items."
    except Exception as e: log += f"Error: {str(e)[:20]}"
    return products, log

def scrape_myntra(query, page=1):
    search_term = query.replace(" ", "-").lower()
    url = f"https://www.myntra.com/{search_term}?p={page}"
    products = []
    log = f"Myntra (Pg {page}): "
    try:
        response = requests.get(url, impersonate=BROWSER_VERSION, timeout=10, verify=False)
        soup = BeautifulSoup(response.text, "html.parser")
        scripts = soup.find_all('script')
        found_data = False
        
        # 1. Try Structured JSON extraction first
        for script in scripts:
            if script.string and ('searchData' in script.string or 'products' in script.string):
                try:
                    content = script.string.strip()
                    if 'window.__myx =' in content:
                        json_text = content.split('window.__myx =', 1)[1].strip().rstrip(';')
                    else: json_text = content
                    data = json.loads(json_text)
                    
                    def find_products_recursive(node):
                        if isinstance(node, dict):
                            if 'products' in node and isinstance(node['products'], list): return node['products']
                            for v in node.values():
                                r = find_products_recursive(v)
                                if r: return r
                        elif isinstance(node, list):
                            for i in node:
                                r = find_products_recursive(i)
                                if r: return r
                        return None
                    
                    items = find_products_recursive(data)
                    if items:
                        for item in items[:16]:
                            title = f"{item.get('brand', '')} {item.get('productName', '')}".strip()
                            price_int = item.get('price', 0)
                            link = f"https://www.myntra.com/{item.get('landingPageUrl', '')}"
                            image_url = item.get('searchImage', "https://via.placeholder.com/200")
                            if price_int > 0:
                                products.append({"platform": "Myntra", "title": title, "price": f"₹{price_int}", "price_int": price_int, "link": link, "image": image_url})
                        found_data = True
                        break
                except: continue
                    
        # 2. BULLETPROOF DOM FALLBACK: Executed instantly if Myntra serves alternative layout to Cloud servers
        if not found_data or len(products) == 0:
            cards = soup.find_all('li', class_='product-base') or soup.select('div[class*="product-base"]') or soup.select('.productCard')
            for card in cards[:16]:
                try:
                    brand_elem = card.find(['h3', 'div'], class_='product-brand')
                    title_elem = card.find(['h4', 'p'], class_='product-product')
                    brand = brand_elem.text.strip() if brand_elem else ""
                    product_name = title_elem.text.strip() if title_elem else "Product"
                    title = f"{brand} {product_name}".strip()
                    
                    price_elem = card.find('span', class_='product-discountedPrice') or card.find('div', class_='product-price')
                    price_str = price_elem.text.strip() if price_elem else "0"
                    if "Rs." in price_str: price_str = price_str.split("Rs.")[-1]
                    price_int = clean_price(price_str)
                    
                    link_elem = card.find('a')
                    link = "https://www.myntra.com/" + link_elem['href'].lstrip('/') if link_elem else "#"
                    
                    img_elem = card.find('img')
                    image_url = img_elem['src'] if img_elem and 'src' in img_elem.attrs else "https://via.placeholder.com/200"
                    
                    if price_int > 0:
                        products.append({"platform": "Myntra", "title": title, "price": f"₹{price_int}", "price_int": price_int, "link": link, "image": image_url})
                except Exception: continue
        log += f"Found {len(products)} items."
    except Exception as e: log += f"Error: {str(e)[:20]}"
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
st.markdown('<p class="sub-title">Intelligent E-Commerce Aggregation Engine</p>', unsafe_allow_html=True)

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    query = st.text_input("Search", placeholder="e.g., Maybelline Eyeliner, Running Shoes...", label_visibility="collapsed")

# Complete Reset on a Brand New Search
if query and query != st.session_state.last_query:
    st.session_state.last_query = query
    st.session_state.display_count = 12
    st.session_state.current_scraped_page = 1
    
    with st.spinner(f"⚡ Interrogating platforms for '{query}'..."):
        all_results = []
        amz_res, amz_log = scrape_amazon(query, page=1)
        nyk_res, nyk_log = scrape_nykaa(query, page=1)
        myn_res, myn_log = scrape_myntra(query, page=1)
        
        all_results.extend(amz_res)
        all_results.extend(nyk_res)
        all_results.extend(myn_res)
        
        all_results = calculate_deal_scores(all_results, query)
        st.session_state.raw_results = all_results
        st.session_state.diagnostics = f"{amz_log} <br> {nyk_log} <br> {myn_log}"
        st.rerun()

# --- THE FEATURE: DEEP LIVE PAGINATION SCRAPE ---
def trigger_deep_scrape():
    next_page = st.session_state.current_scraped_page + 1
    with st.spinner(f"🚀 Digging deeper! Extracting Page {next_page} from live networks..."):
        amz_res, amz_log = scrape_amazon(st.session_state.last_query, page=next_page)
        nyk_res, nyk_log = scrape_nykaa(st.session_state.last_query, page=next_page)
        myn_res, myn_log = scrape_myntra(st.session_state.last_query, page=next_page)
        
        # Append new findings to existing records instead of wiping them out
        combined = st.session_state.raw_results + amz_res + nyk_res + myn_res
        st.session_state.raw_results = calculate_deal_scores(combined, st.session_state.last_query)
        st.session_state.diagnostics += f"<br>{amz_log} <br> {nyk_log} <br> {myn_log}"
        st.session_state.current_scraped_page = next_page
        st.session_state.display_count += 12

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
            logo = '<span style="font-family: Arial, sans-serif; font-weight: 900; font-size: 1.15rem; color: #000; letter-spacing: -1px;">amazon<span style="color: #FF9900;">.in</span></span>'
        elif item['platform'] == 'Nykaa':
            logo = '<span style="font-family: Arial, sans-serif; font-weight: 900; font-size: 1.15rem; color: #FC2779; letter-spacing: 0.5px; text-transform: uppercase;">NYKAA</span>'
        elif item['platform'] == 'Myntra':
            logo = '<span style="font-family: Arial, sans-serif; font-weight: 900; font-size: 1.15rem; color: #FF3E6C; letter-spacing: -0.2px;">Myntra</span>'

        html_parts.append(
f'''<div class="product-card">
<div class="score-badge" style="border-color: {item['score_color']}; color: {item['score_color']};">🔥 {item['score']}</div>
<div class="img-container">
<img src="{item['image']}" class="product-image" loading="lazy">
</div>
<div class="card-content">
<div style="margin-bottom: 4px;">{logo}</div>
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
    
    # Dual-Action Pagination Interface
    btn_col1, btn_col2, btn_col3 = st.columns([1, 2, 1])
    with btn_col2:
        if st.session_state.display_count < len(filtered_results):
            if st.button("⬇️ View More Cached Local Results", use_container_width=True):
                st.session_state.display_count += 12
                st.rerun()
        
        # The user option to trigger an outright network expansion scrape
        if st.button("🚀 Live Deep Scrape Next Page", use_container_width=True, type="primary"):
            trigger_deep_scrape()
            st.rerun()
            
elif query and not st.session_state.raw_results:
    st.error("No active deals found. Try refining your search.")
