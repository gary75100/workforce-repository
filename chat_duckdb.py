import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st
from openai import OpenAI

client = OpenAI()  # uses OPENAI_API_KEY from environment / Streamlit secrets


# ============================================================
#  Utility
# ============================================================

def safe_tables(con: duckdb.DuckDBPyConnection) -> list[str]:
    try:
        return [r[0] for r in con.execute("SHOW TABLES").fetchall()]
    except Exception:
        return []


def df_to_text(df: pd.DataFrame, max_rows: int = 20) -> str:
    if df.empty:
        return "No rows."
    head = df.head(max_rows)
    return head.to_markdown(index=False)


# ============================================================
#  1. Job-posting trend chart (WORC job postings tables)
# ============================================================

def job_posting_trend_chart(con: duckdb.DuckDBPyConnection) -> str:
    """
    Robust, hand-written SQL to show job postings per month across WORC job posting tables.
    Assumes these tables have a "Posting Date" column:
      - worc_job_postings_nov_19___may_24
      - worc_job_postings_aug_24___oct_25
      - worc_job_postings_historical (if present)
    """

    tables = safe_tables(con)
    source_tables = [
        t for t in tables
        if t.startswith("worc_job_postings_nov_19")
        or t.startswith("worc_job_postings_aug_24")
        or t.startswith("worc_job_postings_historical")
    ]

    if not source_tables:
        return "No WORC job posting tables are available for a trend chart."

    union_parts = []
    for t in source_tables:
        # Guard for missing column names – we inspect schema first
        info = con.execute(f"PRAGMA table_info('{t}')").fetchdf()
        cols = [c.lower() for c in info["name"]]
        if "posting date" in cols:
            col_name = info["name"][cols.index("posting date")]
            union_parts.append(f'SELECT "{col_name}" AS posting_date FROM {t}')
        elif "posting_date" in cols:
            col_name = info["name"][cols.index("posting_date")]
            union_parts.append(f'SELECT "{col_name}" AS posting_date FROM {t}')
        else:
            continue  # skip tables without a recognizable date column

    if not union_parts:
        return "I could not find a usable 'Posting Date' column in the WORC job posting tables."

    union_sql = " UNION ALL ".join(union_parts)

    sql = f"""
    WITH all_postings AS (
        {union_sql}
    )
    SELECT
        DATE_TRUNC('month', posting_date) AS month,
        COUNT(*) AS num_postings
    FROM all_postings
    WHERE posting_date IS NOT NULL
    GROUP BY month
    ORDER BY month;
    """

    try:
        df = con.execute(sql).fetchdf()
    except Exception as e:
        return f"Error running job posting trend query:\n{e}\n\nSQL:\n{sql}"

    if df.empty:
        return "No job postings found to chart."

    fig = px.line(df, x="month", y="num_postings", markers=True,
                  title="Job postings by month (WORC)")
    st.plotly_chart(fig, use_container_width=True)

    return "Job posting trend chart generated."


# ============================================================
#  2. Latest total postings table (worc_data_v3_total_postings)
# ============================================================

def latest_total_postings_table(con: duckdb.DuckDBPyConnection) -> str:
    """
    Stable table output from worc_data_v3_total_postings.
    We do not guess column names for ORDER BY; we just show the latest rows by whatever
    column looks like a year or time dimension, if present.
    """

    tables = safe_tables(con)
    if "worc_data_v3_total_postings" not in tables:
        return "The table worc_data_v3_total_postings is not available in the database."

    info = con.execute("PRAGMA table_info('worc_data_v3_total_postings')").fetchdf()
    cols = [c.lower() for c in info["name"]]

    # Try to find a year or time column to sort by
    order_col = None
    for candidate in ["year", "period", "time", "date"]:
        if candidate in cols:
            order_col = info["name"][cols.index(candidate)]
            break

    if order_col:
        sql = f"SELECT * FROM worc_data_v3_total_postings ORDER BY \"{order_col}\" DESC LIMIT 20;"
    else:
        sql = "SELECT * FROM worc_data_v3_total_postings LIMIT 20;"

    try:
        df = con.execute(sql).fetchdf()
    except Exception as e:
        return f"Error reading worc_data_v3_total_postings:\n{e}\n\nSQL:\n{sql}"

    if df.empty:
        return "worc_data_v3_total_postings is present but returned no rows."

    st.dataframe(df, use_container_width=True)
    return "Latest rows from worc_data_v3_total_postings shown above."


# ============================================================
#  3. Executive / report narrative
# ============================================================

def executive_narrative(con: duckdb.DuckDBPyConnection, question: str) -> str:
    """
    Use LLM to write an executive-level narrative, with structured data passed in
    from a few key tables as context. No dynamic SQL.
    """

    tables = safe_tables(con)

    context_fragments = []

    # Sample from WORC totals
    if "worc_data_v3_total_postings" in tables:
        try:
            df_totals = con.execute("SELECT * FROM worc_data_v3_total_postings LIMIT 50;").fetchdf()
            context_fragments.append("WORC total postings (sample):\n" + df_to_text(df_totals, max_rows=15))
        except Exception:
            pass

    # Sample from job postings historical series
    for t in tables:
        if t.startswith("worc_job_postings"):
            try:
                df_sample = con.execute(f"SELECT * FROM {t} LIMIT 50;").fetchdf()
                context_fragments.append(f"{t} (sample):\n" + df_to_text(df_sample, max_rows=10))
            except Exception:
                pass

    # SPS / LFS text tables – they are mostly unstructured text, so we just label them
    text_tables = [t for t in tables if "sps" in t or "lfs" in t or "wage_survey" in t]
    if text_tables:
        context_fragments.append(f"Other text-heavy tables available: {', '.join(text_tables)}")

    context_text = "\n\n".join(context_fragments)[:8000]  # keep prompt size reasonable

    prompt = f"""
You are an expert Cayman Islands workforce analyst.

User question:
\"\"\"{question}\"\"\"

You have the following data context (samples):

{context_text}

Using ONLY the information implied by the data and what you know about labour markets, write a clear, C-suite level narrative addressing the user’s question. Integrate:
- job posting trends,
- any observable changes over time,
- possible implications for Caymanians vs work permits,
- and any obvious risks or opportunities.

Write in 3–6 paragraphs. Do NOT show raw tables or SQL. Do NOT invent precise numbers if they are not clearly implied; describe directional trends and relationships instead.
    """

    resp = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.35,
        messages=[
            {"role": "system", "content": "Write clear, executive-level workforce analysis for Cayman Islands."},
            {"role": "user", "content": prompt},
        ],
    )

    return resp.choices[0].message.content


# ============================================================
#  4. Fallback narrative (no SQL at all)
# ============================================================

def fallback_narrative(con: duckdb.DuckDBPyConnection, question: str) -> str:
    """
    If we don't have a dedicated handler for the question, just answer in narrative form
    without attempting SQL.
    """

    tables = safe_tables(con)
    prompt = f"""
You are an AI assistant for the Cayman Islands Workforce Intelligence platform.

User question:
\"\"\"{question}\"\"\"

You have access to a DuckDB data lake with these tables:
{', '.join(tables)}

You are not allowed to run ad-hoc SQL for this question.
Instead, answer conceptually based on:
- workforce structure (Caymanian vs non-Caymanian),
- job postings and demand,
- skills gaps,
- and typical labour market dynamics.

Write a concise, direct answer in 1–3 paragraphs.
    """

    resp = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.4,
        messages=[
            {"role": "system", "content": "Answer as a senior workforce strategist for Cayman Islands."},
            {"role": "user", "content": prompt},
        ],
    )

    return resp.choices[0].message.content


# ============================================================
#  Router
# ============================================================

def route(question: str):
    """
    Decide which capability to use based on the question.
    Returns a function that accepts (con, question).
    """

    q = (question or "").lower()

    # Job posting trend chart capability
    if ("job posting" in q or "postings" in q or "vacancy" in q) and (
        "chart" in q or "plot" in q or "graph" in q or "trend" in q
    ):
        return job_posting_trend_chart

    # Table of latest total postings
    if "total postings" in q or "worc_data_v3_total_postings" in q:
        return latest_total_postings_table

    # Executive summary / report-like questions
    if any(word in q for word in ["executive", "summary", "brief", "report", "analysis", "narrative"]):
        return lambda con, q: executive_narrative(con, q)

    # Fallback: narrative only, no SQL
    return fallback_narrative
