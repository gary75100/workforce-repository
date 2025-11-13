import streamlit as st
from pathlib import Path
import duckdb
import urllib.request
import os

# Import your logic file
import chat_duckdb

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------
DB_URL = "https://www.dropbox.com/scl/fi/qjc8k6aol1nmirbs8u4wi/cayman_workforce.duckdb?rlkey=gm7rdiu3xzqrs9c1be0fnxqya&st=6lmvhxh9&dl=1"
DB_PATH = Path("cayman_workforce.duckdb")

# ------------------------------------------------------------
# DOWNLOAD DATABASE (CACHED)
# ------------------------------------------------------------
@st.cache_resource
def load_database():
    if not DB_PATH.exists():
        with st.spinner("Downloading Cayman workforce dataset…"):
            urllib.request.urlretrieve(DB_URL, DB_PATH)
    con = duckdb.connect(str(DB_PATH))
    return con

# ------------------------------------------------------------
# MAIN APP
# ------------------------------------------------------------
def main():
    # Page setup
    st.set_page_config(
        page_title="Cayman Workforce Data Assistant",
        page_icon="📊",
        layout="wide"
    )

    # Header + Title
    st.markdown("""
        <div style="padding: 10px 0 0 0;">
            <h1 style="margin-bottom:0;">Cayman Workforce Data Assistant</h1>
            <p style="color: gray; margin-top:0;">Internal • Workforce Development Team • Cayman Islands Government</p>
        </div>
    """, unsafe_allow_html=True)

    con = load_database()

    # ------------------------------------------------------------
    # GUIDANCE PANEL (Expanded on load)
    # ------------------------------------------------------------
    with st.expander("📘 How to use this assistant (click to expand)", expanded=True):
        st.markdown("""
### Welcome

This assistant helps you explore Cayman’s workforce landscape using the latest consolidated datasets from:

- **ESO Labour Force Survey (Fall 2024)**
- **WORC Job Postings**
- **Work Permit Occupations**
- **Scholarships & Training Programs**
- **Local + Overseas Student Pathways & Completion Data**

You may ask questions such as:

- **“What is Caymanian unemployment in the latest Labour Force Survey?”**  
- **“Which occupations rely most on work permits?”**  
- **“Summarize job posting trends by industry over the last few years.”**  
- **“How many students are near graduation in the next 12–18 months?”**  
- **“What are the dominant scholarship fields of study?”**

### Tips for Best Results
- Ask **one specific question at a time**  
- The assistant will summarize large datasets for you  
- Data-heavy queries (like student completion data) may take a few seconds  
- Scroll up to review your conversation history  

If anything looks off, rephrase the question more specifically — you are helping shape the next version of this tool.
""")

    st.markdown("---")

    # ------------------------------------------------------------
    # CHAT SECTION
    # ------------------------------------------------------------
    st.subheader("💬 Ask a Workforce Question")

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    # Display history
    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Chat input
    query = st.chat_input("Ask a question about Cayman’s workforce…")

    if query:
        # Show user's message
        st.session_state["messages"].append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.write(query)

        # Pass to router
        handler = chat_duckdb.route(query)

        # Generate answer
        with st.chat_message("assistant"):
            try:
                answer = handler(con, query)
                st.write(answer)
                st.session_state["messages"].append({"role": "assistant", "content": answer})
            except Exception as e:
                st.error("An error occurred while processing your request. Please try again.")
                st.text(str(e))


# ------------------------------------------------------------
# LAUNCH APP
# ------------------------------------------------------------
if __name__ == "__main__":
    main()
