import os
import requests
import streamlit as st

def ensure_database(db_path: str = "cayman_workforce.duckdb") -> str:
    """
    Ensures the DuckDB file exists locally.
    Downloads from the GitHub Release DB_URL in Streamlit secrets if not present.
    """

    # If DB already exists locally, use it
    if os.path.exists(db_path):
        return db_path

    # DB_URL must exist in secrets
    if "DB_URL" not in st.secrets:
        raise ValueError("DB_URL not found in Streamlit secrets.")

    url = st.secrets["DB_URL"]

    st.write(f"Downloading workforce database from GitHub...")

    # Required headers for GitHub Release assets
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/octet-stream",
    }

    try:
        with requests.get(url, stream=True, headers=headers, allow_redirects=True) as r:
            r.raise_for_status()
            with open(db_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

    except Exception as e:
        st.error(f"Database download failed: {e}")
        raise

    st.success("Database downloaded successfully.")
    return db_path



