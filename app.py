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
    """
    Downloads the DuckDB file from AWS S3 into a temporary file
    using a browser-style User-Agent to avoid 403 errors.
    """
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
        st.error(f"Error loading database: {e}")
        raise e


# ============================================================
#  SIDEBAR CONTENTS
# ============================================================

def render_sidebar(con):
    st.sidebar.title("Navigation")

    # -------------------------
    # Dataset List
    # -------------------------
    st.sidebar.subheader("📚 Available Datasets")

    try:
        tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
        for t in tables:
            st.sidebar.write(f"- {t}")
    except:
        st.sidebar.write("Unable to load table list.")

    st.sidebar.markdown("---")

    # -------------------------
    # Capabilities
    # -------------------------
    st.sidebar.subheader("⚙️ System Capabilities")
    st.sidebar.write(
        """
        - 📊 Interactive charts  
        - 📈 Trend analysis  
        - 📋 Table generation  
        - 🧠 Executive narrative  
        - 🔎 Cross-dataset insights  
        - 📝 Report-style responses  
        """
    )

    st.sidebar.markdown("---")

    # -------------------------
    # Recommended Prompts
    # -------------------------
    st.sidebar.subheader("💡 Example Questions")
    st.sidebar.write(
        """
**Charts & Trends**
- Plot job posting trends from 2019–2025.  
- Graph Caymanian unemployment across LFS datasets.  
- Visualize job postings by industry.  

**Tables**
- Show a table of job postings by industry.  
- Display Caymanian vs non-Caymanian labour participation.  
- List top occupations with growing demand.  

**Executive**
- Executive summary of Cayman workforce conditions.  
- Explain labour market risks across SPS & LFS.  
- Generate a workforce intelligence brief.  
        """
    )


# ============================================================
#  HEADER AREA
# ============================================================

def render_header():
    # Cayman Crest
    CREST_URL = (
        "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/"
        "Coat_of_arms_of_the_Cayman_Islands.svg/800px-"
        "Coat_of_arms_of_the_Cayman_Islands.svg.png"
    )

    crest = None
    try:
        crest_data = requests.get(CREST_URL).content
        crest = Image.open(BytesIO(crest_data))
    except:
        pass

    # Title + Crest
    col1, col2 = st.columns([4, 1])

    with col1:
        st.markdown(
            """
            <h1 style='margin-bottom:0;'>
                WORC / Cayman Workforce Intelligence Assistant
            </h1>
            <p style='font-size:18px; margin-top:-8px; color:#003c71;'>
                A unified labour market intelligence platform using SPS, LFS, Wage Surveys,
                job postings, WORC data, and more.
            </p>
            """,
            unsafe_allow_html=True
        )

    with col2:
        if crest:
            st.markdown("<div style='text-align:right;'>", unsafe_allow_html=True)
            st.image(crest, width=110)
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")


# ============================================================
#  MAIN APP
# ============================================================

def main():
    # Set page config
    st.set_page_config(
        page_title="Cayman Workforce Intelligence Assistant",
        layout="wide"
    )

    # Custom CSS — Cayman branding
    st.markdown(
        """
        <style>
        .stApp {
            background-color: white !important;
        }
        .block-container {
            padding-top: 1rem !important;
        }
        h1 {
            color: #003c71;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # Load DB
    con = load_database()

    # Sidebar
    render_sidebar(con)

    # Header
    render_header()

    # Input box
    st.markdown("## Ask a Workforce Question")
    question = st.text_area(
        "Type your question:",
        height=100,
        placeholder="Example: Plot job posting trends from 2019–2025..."
    )

    if st.button("Submit"):
        handler = route(question)

        try:
            result = handler(con, question)
            if isinstance(result, str):
                st.markdown(result)
        except Exception as e:
            st.error(f"An error occurred: {e}")


# ============================================================
#  ENTRYPOINT
# ============================================================

if __name__ == "__main__":
    main()
