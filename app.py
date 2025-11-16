import streamlit as st
import duckdb
from chat_duckdb import route

# ---------------------------------------------------------
# Cayman Branding
# ---------------------------------------------------------
CAYMAN_BLUE = "#003C71"
CAYMAN_BLUE_DARK = "#002B52"
CAYMAN_LIGHT = "#E6EFF7"
CAYMAN_WHITE = "#FFFFFF"

CREST_URL = (
    "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/"
    "Coat_of_arms_of_the_Cayman_Islands.svg/400px-"
    "Coat_of_arms_of_the_Cayman_Islands.svg.png"
)

# ---------------------------------------------------------
# Streamlit Page Config
# ---------------------------------------------------------
st.set_page_config(
    page_title="WORC / Cayman Workforce Intelligence Assistant",
    layout="wide",
    page_icon=CREST_URL
)

# ---------------------------------------------------------
# Global Styling (Cayman UI Overhaul)
# ---------------------------------------------------------
st.markdown(
    f"""
    <style>
        /* GLOBAL */
        .stApp {{
            background-color: {CAYMAN_WHITE} !important;
            font-family: 'Segoe UI', sans-serif;
        }}

        /* Cayman Blue Header Bar */
        .header-container {{
            background-color: {CAYMAN_BLUE};
            padding: 25px;
            border-radius: 0px 0px 8px 8px;
            margin-bottom: 20px;
        }}

        h1 {{
            color: white !important;
            font-weight: 800 !important;
        }}

        .subtitle {{
            color: white !important;
            font-size: 18px !important;
            margin-top: -5px !important;
        }}

        /* Tabs */
        .stTabs [data-baseweb="tab"] {{
            font-size: 18px;
            color: {CAYMAN_BLUE};
            font-weight: 600;
        }}

        /* Sidebar */
        section[data-testid="stSidebar"] {{
            background-color: {CAYMAN_LIGHT} !important;
        }}

        /* Sidebar text */
        .sidebar-title {{
            color: {CAYMAN_BLUE};
            font-size: 20px;
            font-weight: 700;
            margin-top: 20px;
        }}

        .sidebar-section {{
            color: {CAYMAN_BLUE};
            font-size: 16px;
            font-weight: 600;
            margin-top: 15px;
        }}

        /* Question box */
        textarea {{
            background-color: #1E1E1E !important;
            color: white !important;
            border-radius: 8px !important;
            font-size: 1.1rem !important;
        }}
        textarea::placeholder {{
            color: #CCCCCC !important;
        }}

        /* Submit button */
        .stButton>button {{
            background-color: {CAYMAN_BLUE} !important;
            color: white !important;
            padding: 0.65rem 1.3rem;
            border-radius: 6px;
            font-size: 1.05rem;
        }}

        /* Dataframes */
        .stDataFrame td, .stDataFrame th {{
            background-color: {CAYMAN_WHITE} !important;
            color: {CAYMAN_BLUE} !important;
        }}

    </style>
    """,
    unsafe_allow_html=True
)

# ---------------------------------------------------------
# Load DB From S3
# ---------------------------------------------------------
def load_database():
    DB_URL = st.secrets["DB_URL"]
    import tempfile, urllib.request

    tmp = tempfile.NamedTemporaryFile(delete=False)
    req = urllib.request.Request(DB_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as r:
        tmp.write(r.read())
        tmp.flush()
    return duckdb.connect(tmp.name)


# ---------------------------------------------------------
# Sidebar (Capabilities → Examples → Datasets)
# ---------------------------------------------------------
def render_sidebar(con):

    st.sidebar.image(CREST_URL, width=110)

    st.sidebar.markdown('<div class="sidebar-title">Capabilities</div>', unsafe_allow_html=True)
    st.sidebar.write(
        """
- 📊 Charts & Trends  
- 📈 Labour Force Analytics  
- 📋 Table Generation  
- 🧠 AI-Generated SQL Insights  
- 📝 Executive Reports  
- 🔎 Cross-Dataset Intelligence  
"""
    )

    st.sidebar.markdown('<div class="sidebar-title">Suggested Questions</div>', unsafe_allow_html=True)
    st.sidebar.write(
        """
- Plot job posting trends (2019–2025)  
- Show Caymanian vs non-Caymanian unemployment  
- List top occupations by demand  
- Workforce summary for policymakers  
"""
    )

    st.sidebar.markdown('<div class="sidebar-title">Data Sources</div>', unsafe_allow_html=True)

    # Group datasets
    try:
        tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]

        lfs = sorted([t for t in tables if t.startswith("lfs")])
        sps = sorted([t for t in tables if t.startswith("sps")])
        wage = sorted([t for t in tables if "wage" in t.lower()])
        worc_v3 = sorted([t for t in tables if t.startswith("worc_data_v3")])
        postings = sorted([t for t in tables if t.startswith("worc_job_postings")])
        other = sorted(set(tables) - set(lfs + sps + wage + worc_v3 + postings))

    except:
        lfs = sps = wage = worc_v3 = postings = other = []

    if sps:
        st.sidebar.markdown('<div class="sidebar-section">• SPS – Strategic Policy Statements</div>', unsafe_allow_html=True)
    if lfs:
        st.sidebar.markdown('<div class="sidebar-section">• Labour Force Survey (LFS)</div>', unsafe_allow_html=True)
    if wage:
        st.sidebar.markdown('<div class="sidebar-section">• Wage Survey</div>', unsafe_allow_html=True)
    if worc_v3:
        st.sidebar.markdown('<div class="sidebar-section">• WORC Workforce Data (v3)</div>', unsafe_allow_html=True)
    if postings:
        st.sidebar.markdown('<div class="sidebar-section">• WORC Job Postings</div>', unsafe_allow_html=True)

    if other:
        st.sidebar.markdown('<div class="sidebar-section">• Other / Experimental</div>', unsafe_allow_html=True)


# ---------------------------------------------------------
# Cayman Header Bar
# ---------------------------------------------------------
def render_header():
    st.markdown(
        f"""
        <div class="header-container">
            <h1>WORC / Cayman Workforce Intelligence Assistant</h1>
            <div class="subtitle">
                Real-time insights from SPS, LFS, Wage Surveys, WORC data, and job postings.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
def main():
    con = load_database()

    render_sidebar(con)
    render_header()

    st.markdown("## Ask a Workforce Question")

    question = st.text_area(
        "",
        height=120,
        placeholder="Example: Plot job posting trends from 2019–2025…"
    )

    # Tabbed results interface
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
