import streamlit as st
from pathlib import Path
import duckdb
import urllib.request
import os

import chat_duckdb  # your existing routing + LFS + WORC + permits logic

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------

DB_URL = "https://drive.google.com/uc?export=download&id=1t2h-XhLibkOZfn6RANOKVVXxfdPFBxSk"
DB_PATH = Path("cayman_workforce.duckdb")

# ------------------------------------------------------------
# Download DB (cached)
# ------------------------------------------------------------
@st.cache_resource
def load_database():
    if not DB_PATH.exists():
        with st.spinner("Downloading workforce dataset…"):
            urllib.request.urlretrieve(DB_URL, DB_PATH)
    con = duckdb.connect(str(DB_PATH))
    return con

# ------------------------------------------------------------
# Streamlit App
# ------------------------------------------------------------
def main():
    st.set_page_config(
        page_title="Cayman Workforce Data Assistant",
        page_icon="📊",
        layout="wide"
    )

    st.title("Cayman Workforce Data Assistant")
    st.caption("Internal • Workforce Development Team")

    con = load_database()

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    # Display history
    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Chat input
    prompt = st.chat_input("Ask something…")
    if prompt:
        # Display user msg
        st.session_state["messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        # Route and answer
        handler = chat_duckdb.route(prompt)
        answer = handler(con, prompt)

        # Display assistant msg
        st.session_state["messages"].append({"role": "assistant", "content": answer})
        with st.chat_message("assistant"):
            st.write(answer)

if __name__ == "__main__":
    main()

