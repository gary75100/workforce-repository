import streamlit as st
import duckdb
import requests
from PIL import Image
from io import BytesIO
from chat_duckdb import route


# ============================================================
#  LOAD DUCKDB FROM AWS S3
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
#  CAYMAN STYLE
# ============================================================

CAYMAN_BLUE = "#003C71"
LIGHT_BLUE = "#E6EFF7"

CUSTOM_CSS = f"""
<style>

    /* Global background */
    .stApp {{
        background-color: white !important;
    }}

    /* Header title */
    h1 {{
        color: {CAYMAN_BLUE} !important;
        font-weight: 700 !important;
    }}

    /* Subheadline */
    h2, h3 {{
        color: {CAYMAN_BLUE} !important;
        font-weight: 600 !important;
    }}

    /* Sidebar background */
    section[data-testid="stSidebar"] {{
        background-color: {LIGHT_BLUE} !important;
        padding-top: 30px;
    }}

    /* Sidebar text */
    .css-1lcbmhc, .css-1jkxaji, .css-16idsys, .css-1offfwp {{
        color: {CAYMAN_BLUE} !important;
    }}

    /* Input box readability */
    textarea {{
        font-size: 1rem !important;
        color: #111 !important;
    }}

    /* Submit button */
    .stButton>button {{
        background-color: {CAYMAN_BLUE};
        color: white;
        border-radius: 6px;
        padding: 0.6rem 1.2rem;
        font-size: 1rem;
    }}

    .stButton>button:hover {{
        background-color: #002b50;
        color: white;
    }}

</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ============================================================
#  SIDEBAR
# ============================================================

def render_sidebar(con):
    st.sidebar.image(
        "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/Coat_of_arms_of_the_Cayman_Islands.svg/800px-Coat_of_arms_of_the_Cayman_Islands.svg.png",
        width=120)

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f"<h2 style='color:{CAYMAN_BLUE};'>Datasets</h2>",
        unsafe_allow_html=True)

    try:
        tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
        for t in tables:
            st.sidebar.markdown(f"• **{t}**")
    except:
        st.sidebar.write("Dataset list unavailable.")

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f"<h2 style='color:{CAYMAN_BLUE};'>Capabilities</h2>",
        unsafe_allow_html=True)

    st.sidebar.write("""
- 📊 Charting & trend analysis  
- 📈 Industry demand  
- 📋 Table generation  
- 🧠 SQL-based data insights  
- 📘 Executive reporting  
""")

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f"<h2 style='color:{CAYMAN_BLUE};'>Examples</h2>",
        unsafe_allow_html=True)

    st.sidebar.write("""
- Plot job posting trends from 2019–2025  
- Show Caymanian vs non-Caymanian unemployment  
- Generate an executive summary of labour trends  
- List the top jobs with rising demand  
""")


# ============================================================
#  HEADER
# ============================================================

def render_header():
    col1, col2 = st.columns([4, 1])

    with col1:
        st.markdown(
            f"""
            <h1>WORC / Cayman Workforce Intelligence Assistant</h1>
            <p style='color:{CAYMAN_BLUE}; font-size:18px; margin-top:-10px;'>
            Using SPS, LFS, Wage Surveys, job postings, WORC data, and more to provide real-time labour insights.
            </p>
            """,
            unsafe_allow_html=True
        )

    with col2:
        st.image(
            "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/Coat_of_arms_of_the_Cayman_Islands.svg/800px-Coat_of_arms_of_the_Cayman_Islands.svg.png",
            width=110
        )

    st.markdown("<hr>", unsafe_allow_html=True)


# ============================================================
#  MAIN APP
# ============================================================

def main():
    st.set_page_config(
        page_title="Cayman Workforce Intelligence",
        layout="wide"
    )

    # connect to DB
    con = load_database()

    # sidebar
    render_sidebar(con)

    # header
    render_header()

    # input section
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


# ============================================================
#  RUN
# ============================================================

if __name__ == "__main__":
    main()
