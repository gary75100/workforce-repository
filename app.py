import streamlit as st
import duckdb
import requests
from PIL import Image
from io import BytesIO
from chat_duckdb import route


# ============================================================
# LOAD DUCKDB FROM AWS S3
# ============================================================

def load_database():
    DB_URL = st.secrets["DB_URL"]
    try:
        import tempfile
        import urllib.request

        temp = tempfile.NamedTemporaryFile(delete=False)

        req = urllib.request.Request(
            DB_URL,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        with urllib.request.urlopen(req) as response:
            temp.write(response.read())
            temp.flush()

        return duckdb.connect(temp.name)

    except Exception as e:
        st.error(f"Database Load Error: {e}")
        raise e


# ============================================================
# STYLE
# ============================================================

CAYMAN_BLUE = "#003C71"
LIGHT_BLUE = "#E6EFF7"
WHITE = "#FFFFFF"

CUSTOM_CSS = f"""
<style>

    /* Global background */
    .stApp {{
        background-color: white !important;
    }}

    /* Main text */
    body, p, label {{
        color: {CAYMAN_BLUE} !important;
    }}

    /* Question text area FIX: white text */
    textarea {{
        color: white !important;
        background-color: #1E1E1E !important;
        border-radius: 6px !important;
        font-size: 1.1rem !important;
    }}

    /* Placeholder text white */
    textarea::placeholder {{
        color: #DDDDDD !important;
        opacity: 1;
    }}

    /* Header */
    h1 {{
        color: {CAYMAN_BLUE};
        font-weight: 800 !important;
    }}

    h2, h3 {{
        color: {CAYMAN_BLUE};
    }}

    /* Sidebar */
    section[data-testid="stSidebar"] {{
        background-color: {LIGHT_BLUE} !important;
        padding-top: 20px;
    }}

    /* Sidebar text */
    .css-1lcbmhc, .css-1jkxaji, .css-16idsys, .css-1offfwp, .css-1d391kg {{
        color: {CAYMAN_BLUE} !important;
        font-weight: 600 !important;
    }}

    /* Submit button */
    .stButton>button {{
        background-color: {CAYMAN_BLUE} !important;
        color: white !important;
        border-radius: 8px !important;
        padding: 0.6rem 1.2rem !important;
        font-size: 1rem !important;
    }}

    .stButton>button:hover {{
        background-color: #002B50 !important;
        color: white !important;
    }}

    /* Dataframes FIX: white background + blue text */
    .stDataFrame, .dataframe {{
        background-color: white !important;
        color: {CAYMAN_BLUE} !important;
    }}

    .stDataFrame td, .stDataFrame th {{
        background-color: white !important;
        color: {CAYMAN_BLUE} !important;
    }}

</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ============================================================
# SIDEBAR
# ============================================================

def render_sidebar(con):

    # Cayman crest — FIXED URL
    CREST_URL = (
        "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/"
        "Coat_of_arms_of_the_Cayman_Islands.svg/400px-"
        "Coat_of_arms_of_the_Cayman_Islands.svg.png"
    )

    try:
        st.sidebar.image(CREST_URL, width=110)
    except:
        st.sidebar.write("")

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"<h2 style='color:{CAYMAN_BLUE};'>Datasets</h2>", unsafe_allow_html=True)

    try:
        tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
        for t in tables:
            st.sidebar.markdown(f"<div style='padding-left:10px;'>• {t}</div>", unsafe_allow_html=True)
    except:
        st.sidebar.write("Unavailable")

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"<h2 style='color:{CAYMAN_BLUE};'>Capabilities</h2>", unsafe_allow_html=True)
    st.sidebar.write("""
- 📊 Charts & Trends  
- 📈 Labour Force Analysis  
- 📋 Tables  
- 🧠 Executive Summaries  
- 🔎 Cross-Dataset Querying  
""")

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"<h2 style='color:{CAYMAN_BLUE};'>Examples</h2>", unsafe_allow_html=True)
    st.sidebar.write("""
- Plot job posting trends from 2019–2025  
- Show Caymanian vs non-Caymanian unemployment  
- List top industries by job postings  
- Executive summary of workforce trends  
""")


# ============================================================
# HEADER
# ============================================================

def render_header():
    CREST_URL = (
        "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/"
        "Coat_of_arms_of_the_Cayman_Islands.svg/400px-"
        "Coat_of_arms_of_the_Cayman_Islands.svg.png"
    )

    col1, col2 = st.columns([4, 1])

    with col1:
        st.markdown(
            f"""
            <h1>WORC / Cayman Workforce Intelligence Assistant</h1>
            <p style='color:{CAYMAN_BLUE}; font-size:18px; margin-top:-10px;'>
            Using SPS, LFS, Wage Surveys, job postings, and WORC data to produce real-time labour insights.
            </p>
            """,
            unsafe_allow_html=True
        )

    with col2:
        st.image(CREST_URL, width=100)

    st.markdown("<hr>", unsafe_allow_html=True)


# ============================================================
# MAIN
# ============================================================

def main():
    st.set_page_config(page_title="Cayman Workforce Intelligence", layout="wide")

    con = load_database()

    render_sidebar(con)
    render_header()

    st.markdown(f"<h2 style='color:{CAYMAN_BLUE};'>Ask a Workforce Question</h2>", unsafe_allow_html=True)

    question = st.text_area(
        "",
        height=110,
        placeholder="Example: Plot job posting trends from 2019–2025..."
    )

    if st.button("Submit"):
        handler = route(question)
        try:
            result = handler(con, question)
            if isinstance(result, str):
                st.markdown(result)
        except Exception as e:
            st.error(f"Error: {e}")


if __name__ == "__main__":
    main()
