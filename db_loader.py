import os
import requests
import streamlit as st

def ensure_database(db_path: str = "cayman_workforce.duckdb") -> str:
    """
    Ensures the DuckDB file exists locally.
    If not, downloads it from the GitHub Release URL stored in Streamlit secrets.
    """

    # If DB exists locally → use it
    if os.path.exists(db_path):
        return db_path

    # Get DB download URL from Streamlit secrets
    if "DB_URL" not in st.secrets:
        raise ValueError("DB_URL not found in Streamlit secrets.")

    url = st.secrets["DB_URL"]

    st.write(f"Downloading workforce database from GitHub Releases...")

    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(db_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

    st.write("Database downloaded successfully.")
    return db_path


