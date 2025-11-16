import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st
from openai import OpenAI

client = OpenAI()  # uses OPENAI_API_KEY from environment / Streamlit secrets


# ============================================================
# Helpers
# ============================================================

def list_tables(con):
    try:
        return [r[0] for r in con.execute("SHOW TABLES").fetchall()]
    except Exception:
        return []


def safe_sample(con, table_name, limit=20):
    try:
        return con.execute(f"SELECT * FROM {table_name} LIMIT {limit}").fetchdf()
    except Exception:
        return pd.DataFrame()


# ============================================================
# Charts: Unified Job Posting Trend (2019–2025)
# ============================================================

def plot_job_posting_trend(con, question: str) -> str:
    tables = list_tables(con)

    # Identify posting tables
    posting_tables = [
        t for t in tables
        if t.startswith("worc_job_postings_historical")
        or t.startswith("worc_job_postings_nov_19___may_24")
        or t.startswith("worc_job_postings_aug_24___oct_25")
    ]

    if not posting_tables:
        return "No WORC job posting tables are available for a trend chart."

    union_parts = []

    # historical + nov_19 use TIMESTAMP_NS Posting Date
    for t in posting_tables:
        if t == "worc_job_postings_aug_24___oct_25":
            # Posting Date is VARCHAR here; cast to DATE
            union_parts.append(
                f"""
                SELECT TRY_CAST("Posting Date" AS DATE) AS posting_date
                FROM {t}
                """
            )
        else:
            # TIMESTAMP_NS → DATE
            union_parts.append(
                f"""
                SELECT CAST("Posting Date" AS DATE) AS posting_date
                FROM {t}
                """
            )

    union_sql = " UNION ALL ".join(union_parts)

    sql = f"""
    WITH all_postings AS (
        {union_sql}
    )
    SELECT
        DATE_TRUNC('month', posting_date) AS month,
        COUNT(*)::BIGINT AS postings
    FROM all_postings
    WHERE posting_date IS NOT NULL
      AND posting_date BETWEEN DATE '2019-01-01' AND DATE '2025-12-31'
    GROUP BY month
    ORDER BY month;
    """

    try:
        df = con.execute(sql).fetchdf()
    except Exception as e:
        return f"Error generating job posting trend chart:\n{e}\n\nSQL:\n{sql}"

    if df.empty:
        return "No job postings found in the specified period."

    fig = px.line(df, x="month", y="postings", markers=True,
                  title="Job Posting Trend (2019–2025, WORC Job Postings)")
    st.plotly_chart(fig, use_container_width=True)

    return "Job posting trend chart generated."


# ============================================================
# Tables: Safe Table Viewer
# ============================================================

def show_table(con, question: str) -> str:
    q = (question or "").lower()
    tables = list_tables(con)
    if not tables:
        return "No tables available in the database."

    # If user references a specific table name, use that
    target = None
    for t in tables:
        if t.lower() in q:
            target = t
            break

    # Otherwise default priority: WORC v3 totals → job postings → first table
    if not target:
        if "worc_data_v3_total_postings" in tables:
            target = "worc_data_v3_total_postings"
        elif any(t.startswith("worc_job_postings") for t in tables):
            target = [t for t in tables if t.startswith("worc_job_postings")][0]
        else:
            target = tables[0]

    try:
        df = con.execute(f"SELECT * FROM {target} LIMIT 200").fetchdf()
    except Exception as e:
        return f"Error reading table {target}:\n{e}"

    if df.empty:
        return f"Table {target} is present but returned no rows."

    st.dataframe(df, use_container_width=True)
    return f"Showing first 200 rows from `{target}`."


# ============================================================
# Narratives: Executive-Level Summaries
# ============================================================

def generate_executive_narrative(con, question: str) -> str:
    tables = list_tables(con)

    context_chunks = []

    # SPS
    sps_tables = [t for t in tables if t.startswith("sps")]
    for t in sps_tables:
        df = safe_sample(con, t, 10)
        if not df.empty:
            context_chunks.append(f"SPS ({t}) sample:\n" + df.to_string(index=False))

    # LFS
    lfs_tables = [t for t in tables if t.startswith("lfs")]
    for t in lfs_tables:
        df = safe_sample(con, t, 10)
        if not df.empty:
            context_chunks.append(f"LFS ({t}) sample:\n" + df.to_string(index=False))

    # Wage survey
    wage_tables = [t for t in tables if "wage" in t.lower()]
    for t in wage_tables:
        df = safe_sample(con, t, 10)
        if not df.empty:
            context_chunks.append(f"Wage survey ({t}) sample:\n" + df.to_string(index=False))

    # WORC v3 totals
    if "worc_data_v3_total_postings" in tables:
        df = safe_sample(con, "worc_data_v3_total_postings", 20)
        if not df.empty:
            context_chunks.append(
                "WORC Data v3 Total Postings sample:\n" + df.to_string(index=False)
            )

    # WORC job postings
    posting_tables = [t for t in tables if t.startswith("worc_job_postings")]
    for t in posting_tables:
        df = safe_sample(con, t, 10)
        if not df.empty:
            context_chunks.append(f"Job postings ({t}) sample:\n" + df.to_string(index=False))

    context = "\n\n".join(context_chunks)[:9000]

    prompt = f"""
You are a senior strategist for the Cayman Islands Government,
writing for Ministers and Cabinet-level leadership.

User question:
\"\"\"{question}\"\"\"

Below is structured sample data from the Cayman Workforce Data Lake:
{context}

Write a clear, executive-level narrative (3–6 paragraphs) that:
- Uses the sample data conceptually (no made-up precise figures)
- Discusses labour demand, supply, и job posting trends
- Mentions relationships between SPS, LFS, wage data, and WORC postings
- Clearly outlines key risks and opportunities for Caymanians
- Avoids jargon and is suitable for non-technical decision-makers

Do NOT include SQL.
Do NOT mention table names explicitly.
Focus on insights and implications.
"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.35,
        messages=[
            {"role": "system", "content": "You write clear, concise executive-level labour market analysis."},
            {"role": "user", "content": prompt},
        ],
    )

    return resp.choices[0].message.content


# ============================================================
# Fallback: Conceptual Answer (No SQL)
# ============================================================

def fallback_answer(con, question: str) -> str:
    tables = list_tables(con)

    prompt = f"""
You are an AI assistant for the Cayman Islands Workforce Intelligence platform.

User question:
\"\"\"{question}\"\"\"

You have access to a DuckDB workforce data lake with tables:
{', '.join(tables)}

Without running SQL, answer the question conceptually.
Draw on typical Cayman labour dynamics:
- labour force (Caymanian vs non-Caymanian),
- WORC job postings trends,
- SPS strategic concerns,
- wage and industry structure.

Write 1–3 paragraphs, using plain business language.
"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.4,
        messages=[
            {"role": "system", "content": "You are a pragmatic, honest workforce strategist."},
            {"role": "user", "content": prompt},
        ],
    )

    return resp.choices[0].message.content


# ============================================================
# ROUTER
# ============================================================

def route(question: str):
    q = (question or "").lower()

    # Chart / Trend requests
    if any(w in q for w in ["chart", "plot", "graph", "trend", "time series", "visualize"]):
        return plot_job_posting_trend

    # Table requests
    if any(w in q for w in ["table", "rows", "show me", "list", "view data"]):
        return show_table

    # Executive narrative / reports
    if any(w in q for w in ["executive", "summary", "brief", "narrative", "report", "analysis"]):
        return generate_executive_narrative

    # Default: conceptual narrative
    return fallback_answer
