import streamlit as st
import duckdb
from PIL import Image
import requests
from io import BytesIO
from chat_duckdb import route


############################################################
#              DATABASE LOADING FUNCTION
############################################################

def load_database():
    """
    Loads the DuckDB database from AWS S3 or local.
    Uses a custom User-Agent because S3 blocks default urllib requests.
    """
    DB_PATH = st.secrets["DB_URL"]

    try:
        # Remote S3 URL
        if DB_PATH.startswith("http"):
            import tempfile
            import urllib.request

            temp = tempfile.NamedTemporaryFile(delete=False)

            # Custom User-Agent to avoid AWS 403 errors
            req = urllib.request.Request(
                DB_PATH,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req) as response, open(temp.name, "wb") as out_file:
                out_file.write(response.read())

            return duckdb.connect(temp.name)

        # Local file fallback
        else:
            return duckdb.connect(DB_PATH)

    except Exception as e:
        st.error(f"Error loading database: {e}")
        raise e

############################################################
#                    SIDEBAR COMPONENTS
############################################################

def sidebar_content(con):
    """Builds the left navigation sidebar."""

    st.sidebar.title("Navigation")

    # -----------------------------
    # Dataset List
    # -----------------------------
    st.sidebar.subheader("📚 Available Datasets")

    try:
        tables = [row[0] for row in con.execute("SHOW TABLES").fetchall()]
        for t in tables:
            st.sidebar.write(f"• {t}")
    except:
        st.sidebar.write("Dataset list unavailable.")

    st.sidebar.markdown("---")

    # -----------------------------
    # Capabilities
    # -----------------------------
    st.sidebar.subheader("⚙️ Capabilities")
    st.sidebar.write("""
    - 📊 Interactive Plotly Charts  
    - 📈 Multi-year Trend Analysis  
    - 📋 Table Extraction  
    - 🧠 Executive Narrative Engine  
    - 📝 Multi-source Workforce Reporting  
    - 🔎 Cross-dataset Reasoning  
    """)

    st.sidebar.markdown("---")

    # -----------------------------
    # Recommended Prompts
    # -----------------------------
    st.sidebar.subheader("💡 Recommended Prompts")

    st.sidebar.write("""
    **Charts / Graphs**
    - “Plot job posting trends from 2019 to 2025.”
    - “Graph Caymanian unemployment from LFS datasets.”
    - “Visualize job postings by industry.”

    **Tables**
    - “Show a table of job postings by year.”
    - “Display Caymanian vs non-Caymanian labour force levels.”
    - “List top occupations with highest permit counts.”

    **Executive Narratives**
    - “Write an executive summary of current workforce conditions.”
    - “Explain labour market risks across SPS + LFS.”
    - “Analyze tech workforce supply vs job posting demand.”

    **Reports**
    - “Generate a workforce intelligence report combining all datasets.”
    """)


############################################################
#                    HEADER COMPONENT
############################################################

def render_header():
    """Renders the main title + Cayman crest."""
    st.markdown("<br>", unsafe_allow_html=True)

    # Cayman crest (upper right)
    try:
        crest_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/Coat_of_arms_of_the_Cayman_Islands.svg/1200px-Coat_of_arms_of_the_Cayman_Islands.svg.png"
        crest_data = requests.get(crest_url).content
        crest = Image.open(BytesIO(crest_data))
    except:
        crest = None

    col1, col2 = st.columns([4, 1])

    with col1:
        st.markdown(
            """
            <div style='text-align: left;'>
                <h1 style='margin-bottom: 0;'>
                    WORC / Cayman Workforce Intelligence Assistant
                </h1>
                <p style='font-size: 18px; margin-top: -6px; color:#444;'>
                    A unified labour market intelligence platform built on SPS, LFS, Wage Survey,
                    job postings, WORC datasets, and more.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col2:
        if crest:
            st.image(crest, width=110)

    st.markdown("---")


############################################################
#                       MAIN APP
############################################################

def main():
    st.set_page_config(
        page_title="Cayman Workforce Intelligence Assistant",
        layout="wide"
    )

    # Load the database
    con = load_database()

    # Sidebar
    sidebar_content(con)

    # Header
    render_header()

    # ---------------------------------------------------------
    # QUESTION INPUT
    # ---------------------------------------------------------
    st.markdown("## Ask a Workforce Question")

    question = st.text_area(
        "Type any question about trends, charts, job postings, SPS, LFS, wages, shortages, or insights:",
        height=120,
        placeholder="Example: Plot job posting trends by industry from 2019–2025..."
    )

    if st.button("Submit"):
        st.markdown("### Results")
        handler = route(question)

        try:
            answer = handler(con, question)
            if isinstance(answer, str):
                st.markdown(answer)
        except Exception as e:
            st.error(f"An error occurred while processing your request: {e}")


############################################################
#                      RUN APP
############################################################

if __name__ == "__main__":
    main()
