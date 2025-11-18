
import os
import requests
import streamlit as st
from pathlib import Path

def ensure_database() -> str:
    """
    Ensures the DuckDB file (workforce.db) exists locally.
    If not, downloads it from GitHub Releases via DB_URL.
    """

    db_path = Path("database") / "workforce.db"

    # If DB already exists, use it
    if db_path.exists():
        return str(db_path)

    # Must have DB_URL in Streamlit secrets
    if "DB_URL" not in st.secrets:
        st.error("DB_URL missing from Streamlit secrets.")
        raise ValueError("DB_URL missing from Streamlit secrets.")

    url = st.secrets["DB_URL"]
    st.info(f"Downloading workforce.db from GitHub Release…")

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/octet-stream",
    }

    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)

        with requests.get(url, stream=True, headers=headers, allow_redirects=True) as r:
            r.raise_for_status()
            with open(db_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

    except Exception as e:
        st.error(f"Failed to download workforce.db: {e}")
        raise

    st.success("Database downloaded successfully.")
    return str(db_path)
