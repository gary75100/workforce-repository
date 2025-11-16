import streamlit as st
import duckdb
from chat_duckdb import route

# ---------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------
st.set_page_config(
    page_title="WORC / Cayman Workforce Intelligence Assistant",
    layout="wide"
)

CAYMAN_BLUE = "#003C71"
CREST_URL = (
    "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/"
    "Coat_of_arms_of_the_Cayman_Islands.svg/400px-"
    "Coat_of_arms_of_the_Cayman_Islands.svg.png"
)

# Minimal CSS for white/blue UI
st.markdown(
    f"""
    <style>
        .stApp {{
            background-color: white !important;
        }}
        h1 {{
            color: {CAYMAN_BLUE} !important;
            font-weight: 800 !important;
        }}
        h2, h3 {{
            color: {CAYMAN_BLUE} !important;
            font-weight: 700 !important;
        }}
        .stButton>button {{
            background-color: {CAYMAN_BLUE} !important;
            color: white !important;
            border-radius: 6px;
            padding: 0.6rem 1.2rem;
            font-size: 1rem;
        }}
        .stButton>button:hover {{
            background-color: #002B50 !important;
        }}
    </style>
    """,
    unsafe_allow_html=True
)


# ---------------------------------------------------------
# LOAD DB FROM S3
# ---------------------------------------------------------
def load_database():
    DB_URL = st.secrets["DB_URL"]
    import tempfile, urllib.request

    tmp = tempfile.NamedTemporaryFile(delete=False)
    req = urllib.request.Request(
        DB_URL,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req) as r:
        tmp.write(r.read())
        tmp.flush()

    return duckdb.connect(tmp.name)


# ---------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------
def render_sidebar(con):
    st.sidebar.image(CREST_URL, width=110)

    st.sidebar.markdown("---")
    st.sidebar.markdown("## Datasets")

    try:
        tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
        for t in tables:
            st.sidebar.markdown(f"- `{t}`")
    except Exception:
        st.sidebar.write("Unable to load dataset list.")

    st.sidebar.markdown("---")
    st.sidebar.markdown("## Capabilities")
    st.sidebar.write(
        """
- Charts & trends  
- Table generation  
- SQL-driven insights  
- Executive summaries  
- Cross-dataset analysis  
        """
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("## Example Questions")
    st.sidebar.write(
        """
- Plot job posting trends from 2019–2025  
- Show Caymanian vs non-Caymanian unemployment  
- List top industries by job postings  
- Executive summary of workforce conditions  
        """
    )


# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------
def render_header():
    col1, col2 = st.columns([4, 1])

    with col1:
        st.markdown(
            f"""
            <h1>WORC / Cayman Workforce Intelligence Assistant</h1>
            <p style="color:{CAYMAN_BLUE}; font-size:18px; margin-top:-8px;">
                Using SPS, LFS, Wage Surveys, job postings, and WORC data to provide real-time labour insights.
            </p>
            """,
            unsafe_allow_html=True
        )

    with col2:
        st.image(CREST_URL, width=100)

    st.markdown("---")


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
def main():
    con = load_database()

    render_sidebar(con)
    render_header()

    st.markdown("## Ask a Workforce Question")

    question = st.text_area(
        "Type your question:",
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
