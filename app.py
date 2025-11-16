import streamlit as st
import duckdb
from chat_duckdb import route

# ---------------------------------------------------------
# Cayman Branding
# ---------------------------------------------------------
CAYMAN_BLUE = "#003C71"
CAYMAN_BLUE_DARK = "#002B52"
SIDEBAR_BG = "#003C71"   # darker blue for readability
WHITE = "#FFFFFF"

# FIXED CREST URL (PERMANENT)
CREST_URL = "https://raw.githubusercontent.com/gary75100/workforce-repository/main/cayman_crest.png"

# ---------------------------------------------------------
# Streamlit Page Config
# ---------------------------------------------------------
st.set_page_config(
    page_title="WORC / Cayman Workforce Intelligence Assistant",
    layout="wide",
    page_icon=CREST_URL
)

# ---------------------------------------------------------
# GLOBAL CAYMAN STYLE FIXES
# ---------------------------------------------------------
st.markdown("""
<style>
/* FULL SIDEBAR STYLE BLOCK */

section[data-testid="stSidebar"] {
    background-color: #003C71 !important;   /* Cayman Blue */
    color: white !important;
}

section[data-testid="stSidebar"] * {
    color: white !important;                /* Make all sidebar text white */
    font-weight: 600 !important;
}

/* Fix sidebar headers */
.sidebar-title, .sidebar-section {
    color: white !important;
}

/* Fix list bullets */
ul, li, p {
    color: white !important;
}
</style>
""", unsafe_allow_html=True)


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

    import base64

    # Load crest from local encoded string
    crest_b64 = """
    iVBORw0KGgoAAAANSUhEUgAAAOEAAADhCAMAAAAJbSJIAAAAflBMVEX///8AAAD39/eZmZn8
    /Pzx8fHx8fHv7+/q6uqVlZW3t7fT09OUlJSmppudnZ2jo6OwsLD4+PjCwsLq6uq/v7/v7+/h
    4eH+/v7l5eXY2Njh4eHn5+ff39+srKy2traioqKqqqqurq6mpqa9vb3p6emOjo6SkpLc3NxN
    TU0gICBOTk6qqqrj4+M3NzczMzPExMRPT0/o0t9bAAAFRklEQVR4nO2c61biMBCFJ0IFQwKu
    gQqLFpZ7/79bQUBtBtTyt5zcfv3TJS3BM4tiTcb9P6AQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
    AAAgHGtYwbn1PKXW0fvk/sdz9wH14r2raXI5QunlslqY5T2r8j04YfGLmRoTSesFiNUFDXL
    BYnwK6JqqPiR+jYwIV/pY5Pja/qvpDMAYA9YgAXgCBFAHhBQGjBjjcgzvEihQ/HUkNzxaz2
    gEiBjjcg5vE8hQZHUkdzzaz2gEiBjjcg5vE8hQZHUkdzzaz2gEiBjjcg5vE8hQZHUkdzzaz
    2gEiBjjcg5vE8hQZHUkdzzaz2gEiBjjcg5vE8hQZHUkdzzaz2gEiBjjcg5vE8hQZHUkdzzaz
    2gEiBjjcg5vE8hQZHUkdzzaz2gEiBjjcg5vE8hQZHUkdzzaz2gEiBjjcg5vE8hQZHUkdzzaz
    2gEiBjic4n8QPHQ0YzUKGwEuITdSb9VjA36TObgATJE0E7E5Wdl66iRS0LlwM651c01qmPvQ
    A+roWAt4EvsC0Bp4E3kI9wKHGDoPpIl4E7wKxGDoPpIl4E7wKxGDoPpIl4E7wKxGDoPpIl4E
    7wKxGDoPpIl4E7wKxGDoPpIl4E7wKxGDoPpIl4E7wKxGDoPpIl4E7wKxGDoPpIl4E7wKxGDo
    PpIl4E7wKxGDoPpIl4E7wKxGDoPpIl4E7wKxGDoPpIl4E7wKxGDoPpIl4E7wKxGDoPpIl4E7
    wKxGDqf/91IBqD0oVapBWn76wH8NWDDDeWGPAHDqBYcBB+xr3aMcMBXNIN1qQEbfXDnpa9e
    dgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMCP+AXo5jBqFaUG2AAAAABJRU5ErkJggg==
    """

    # Render crest
    st.sidebar.markdown(
        f"""
        <div style="text-align:center; margin-bottom: 20px;">
            <img src="data:image/png;base64,{crest_b64}" width="110">
        </div>
        """,
        unsafe_allow_html=True
    )

    # Capabilities
    st.sidebar.markdown('<div class="sidebar-title">Capabilities</div>', unsafe_allow_html=True)
    st.sidebar.write("""
- 📊 Charts & Trends  
- 📈 Labour Force Analytics  
- 📋 Table Generation  
- 🧠 AI SQL Insights  
- 📝 Executive Reports  
- 🔎 Cross-Dataset Intelligence  
""")

    # Suggested Questions
    st.sidebar.markdown('<div class="sidebar-title">Suggested Questions</div>', unsafe_allow_html=True)
    st.sidebar.write("""
- Plot job posting trends  
- Compare Caymanian vs non-Caymanian unemployment  
- Top occupations by demand  
- Workforce summary for policymakers  
""")

    # Data Sources
    st.sidebar.markdown('<div class="sidebar-title">Data Sources</div>', unsafe_allow_html=True)

    tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]

    lfs = sorted([t for t in tables if t.startswith("lfs")])
    sps = sorted([t for t in tables if t.startswith("sps")])
    wage = sorted([t for t in tables if "wage" in t.lower()])
    worc_v3 = sorted([t for t in tables if t.startswith("worc_data_v3")])
    postings = sorted([t for t in tables if t.startswith("worc_job_postings")])
    other = sorted(set(tables) - set(lfs + sps + wage + worc_v3 + postings))

    if sps: st.sidebar.markdown("**• SPS — Strategic Policy Statements**")
    if lfs: st.sidebar.markdown("**• Labour Force Survey (LFS)**")
    if wage: st.sidebar.markdown("**• Wage Survey**")
    if worc_v3: st.sidebar.markdown("**• WORC Workforce Data (v3)**")
    if postings: st.sidebar.markdown("**• WORC Job Postings**")
    if other: st.sidebar.markdown("**• Other / Experimental**")


# ---------------------------------------------------------
# Cayman Header Bar
# ---------------------------------------------------------
def render_header():
    st.markdown(
        f"""
        <div class="header">
            <h1>WORC / Cayman Workforce Intelligence Assistant</h1>
            <div class="header-sub">
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

    st.markdown(f"## Ask a Workforce Question", unsafe_allow_html=True)

    question = st.text_area(
        "",
        height=120,
        placeholder="Example: Plot job posting trends from 2019–2025…"
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
