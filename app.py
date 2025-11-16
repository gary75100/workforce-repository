import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px

# FIXED IMPORT — handles all scenarios
import chat_duckdb

# ------------------------------------------------------------
# PAGE SETTINGS
# ------------------------------------------------------------
st.set_page_config(
    page_title="WORC / Cayman Workforce Intelligence Assistant",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------------------------------------------------
# SIDEBAR STYLE FIX (Cayman Blue)
# ------------------------------------------------------------
st.markdown("""
<style>
/* Sidebar background */
section[data-testid="stSidebar"] {
    background-color: #003C71 !important;
}

/* Sidebar text */
section[data-testid="stSidebar"] * {
    color: white !important;
    font-size: 16px !important;
}

/* Dark input box fix */
textarea, input, div[contenteditable="true"] {
    color: white !important;
}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# CAYMAN CREST (TOP RIGHT)
# ------------------------------------------------------------
crest_html = """
<div style="
     position: absolute;
     top: 15px;
     right: 35px;
     z-index: 9999;
">
    <img src="https://raw.githubusercontent.com/gary75100/workforce-repository/main/coat%20of%20Arms.gif"
         width="120">
</div>
"""
st.markdown(crest_html, unsafe_allow_html=True)

# ------------------------------------------------------------
# LOAD DATABASE
# ------------------------------------------------------------
def load_database():
    DB_PATH = st.secrets["DB_URL"]
    try:
        if DB_PATH.startswith("http"):
            import urllib.request, tempfile
            temp = tempfile.NamedTemporaryFile(delete=False)
            req = urllib.request.Request(
                DB_PATH,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req) as response, open(temp.name, "wb") as f:
                f.write(response.read())
            return duckdb.connect(temp.name)
        else:
            return duckdb.connect(DB_PATH)
    except Exception as e:
        st.error(f"Failed to load database: {e}")
        raise e

con = load_database()

# ------------------------------------------------------------
# SIDEBAR CONTENT
# ------------------------------------------------------------
st.sidebar.title("Capabilities")

st.sidebar.markdown("""
- 📊 **Charts & Trends**  
- 📉 **Labour Force Analytics**  
- 📋 **Table Generation**  
- 🧠 **AI SQL Insights**  
- 📝 **Executive Reports**  
- 🔍 **Cross-Dataset Intelligence**  
""")

st.sidebar.subheader("Suggested Questions")
st.sidebar.markdown("""
- Plot job posting trends  
- Compare Caymanian vs non-Caymanian unemployment  
- Top occupations by demand  
- Workforce summary for policymakers  
""")

st.sidebar.subheader("Data Sources")
st.sidebar.markdown("""
- **SPS — Strategic Policy Statements**  
- **Labour Force Survey (LFS)**  
- **Wage Survey**  
- **Job Posting History (WORC)**  
- **WORC Experimental Sheets**  
""")

# ------------------------------------------------------------
# MAIN HEADER
# ------------------------------------------------------------
st.markdown("""
# **WORC / Cayman Workforce Intelligence Assistant**
### Using SPS, LFS, Wage Surveys, job postings, and WORC data to produce real-time labour insights.
""")

# ------------------------------------------------------------
# USER QUESTION INPUT
# ------------------------------------------------------------
st.markdown("## Ask a Workforce Question")

user_question = st.text_area(
    "",
    placeholder="Example: Plot job posting trends from 2019–2025...",
    height=80
)

submit = st.button("Submit")

# ------------------------------------------------------------
# PROCESS QUESTION
# ------------------------------------------------------------
if submit and user_question.strip():
    with st.spinner("Analyzing workforce data…"):
        result = chat_duckdb.process_question(con, user_question)

    # Show text result
    if "text" in result and result["text"]:
        st.markdown("### **Answer**")
        st.write(result["text"])

    # Show table result
    if "table" in result and isinstance(result["table"], pd.DataFrame):
        st.markdown("### **Table Output**")
        st.dataframe(result["table"], use_container_width=True)

    # Show chart result
    if "chart" in result and result["chart"] is not None:
        st.markdown("### **Chart**")
        st.plotly_chart(result["chart"], use_container_width=True)
