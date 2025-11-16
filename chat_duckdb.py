import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st
from openai import OpenAI

# OpenAI client – uses OPENAI_API_KEY from environment/Streamlit secrets
client = OpenAI()


# ============================================================
#  Helpers
# ============================================================

def list_tables(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Return list of table names in the connected DuckDB database."""
    try:
        return [row[0] for row in con.execute("SHOW TABLES").fetchall()]
    except Exception:
        return []


def clean_sql(raw_sql: str) -> str:
    """
    Strip markdown fences and boilerplate from LLM-generated SQL.
    Handles ```sql, ``` and 'Generated SQL:' etc.
    """
    if not raw_sql:
        return ""

    sql = raw_sql

    # Remove common markdown fences
    sql = sql.replace("```sql", "")
    sql = sql.replace("```", "")

    # If the model prepends labels like 'Generated SQL:' or 'SQL:'
    lower = sql.lower()
    if "generated sql:" in lower:
        sql = sql.split("Generated SQL:", 1)[-1]
    elif "sql:" in lower:
        # avoid cutting valid 'select' etc., only if it's clearly a label
        parts = sql.split("SQL:", 1)
        if len(parts) == 2 and "select" in parts[1].lower():
            sql = parts[1]

    return sql.strip()


def llm_generate_sql(con: duckdb.DuckDBPyConnection, question: str, purpose: str = "generic") -> str:
    """
    Generate SQL for DuckDB using the LLM **with schema awareness**.
    The model is given the table names AND column names so it stops hallucinating.
    """

    tables = list_tables(con)

    # Build schema dictionary
    schema_info = []
    for t in tables:
        try:
            cols = con.execute(f"PRAGMA table_info('{t}')").fetchdf()
            col_list = ", ".join([col for col in cols["name"]])
            schema_info.append(f"- {t}: {col_list}")
        except:
            pass

    schema_text = "\n".join(schema_info) if schema_info else "(no schema available)"

    instructions = (
        "Return ONLY SQL. No markdown. No fences.\n"
        "Use EXACT column names shown in the schema.\n"
        "If a date column exists, detect it from the schema.\n"
        "Do NOT invent column names.\n"
        "Do NOT guess — use ONLY columns given below.\n"
    )

    if purpose == "chart":
        instructions += (
            "SQL MUST return a date/time column and a numeric column.\n"
            "If multiple date columns exist, prefer 'Posting Date' or 'Start Date'.\n"
        )
    elif purpose == "table":
        instructions += "SQL MUST return a useful table.\n"

    prompt = f"""
You are a DuckDB SQL generator.

User question:
\"\"\"{question}\"\"\"

Available tables and columns:
{schema_text}

{instructions}
    """

    resp = client.chat.completions.create(
        model="gpt-4o",
        temperature=0,
        messages=[
            {"role": "system", "content": "Output only valid SQL for DuckDB."},
            {"role": "user", "content": prompt}
        ],
    )

    raw_sql = resp.choices[0].message.content
    return clean_sql(raw_sql)



# ============================================================
#  Executive Narrative Engine
# ============================================================

def handle_executive_narrative(con: duckdb.DuckDBPyConnection, question: str) -> str:
    """
    Generate a C-suite style narrative using the data lake as context.
    For now we pass the table list and user question to the model.
    You can extend this later to include actual aggregates.
    """
    tables = list_tables(con)
    table_list = ", ".join(tables) if tables else "(no tables found)"

    prompt = f"""
You are a senior Workforce Economist writing for Cayman Islands leadership.

User has asked for an executive narrative:
\"\"\"{question}\"\"\"

You have access to many datasets in DuckDB with the following table names:
{table_list}

Write a concise, executive-level narrative (3–6 paragraphs) that:
- references the types of data available (e.g., LFS, SPS, job postings, wage surveys, WORC data)
- draws high-level insights and risks
- uses clear, non-technical language
- is appropriate for Cabinet-level briefing.

Do NOT output SQL. Do NOT mention table names or internal schema details.
    """

    resp = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.3,
        messages=[
            {"role": "system", "content": "Write clear executive-level workforce analysis."},
            {"role": "user", "content": prompt},
        ],
    )

    return resp.choices[0].message.content


# ============================================================
#  Chart Engine (Plotly)
# ============================================================

def handle_chart(con: duckdb.DuckDBPyConnection, question: str) -> str:
    """
    Generate a Plotly chart based on LLM-generated SQL.
    The first column is treated as x; numeric columns as y.
    """
    sql = llm_generate_sql(con, question, purpose="chart")

    try:
        df = con.execute(sql).fetchdf()
    except Exception as e:
        return f"SQL Error when trying to build chart:\n{e}\n\nGenerated SQL:\n{sql}"

    if df.empty:
        return f"No data returned for chart.\nGenerated SQL:\n{sql}"

    # choose x and y columns
    x_col = df.columns[0]
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()

    if not numeric_cols:
        return f"SQL returned no numeric columns to plot.\nGenerated SQL:\n{sql}"

    # If first column is numeric too, we still treat it as x if there is at least one other numeric
    y_cols = numeric_cols if x_col not in numeric_cols or len(numeric_cols) == 1 else [c for c in numeric_cols if c != x_col]

    try:
        fig = px.line(df, x=x_col, y=y_cols, markers=True)
        st.plotly_chart(fig, use_container_width=True)
        return f"Chart generated.\nSQL used:\n{sql}"
    except Exception as e:
        return f"Plotting error: {e}\nGenerated SQL:\n{sql}"


# ============================================================
#  Table Engine
# ============================================================

def handle_table(con: duckdb.DuckDBPyConnection, question: str) -> str:
    """
    Generate a table (dataframe) based on LLM-generated SQL.
    """
    sql = llm_generate_sql(con, question, purpose="table")

    try:
        df = con.execute(sql).fetchdf()
    except Exception as e:
        return f"SQL Error when generating table:\n{e}\n\nSQL:\n{sql}"

    if df.empty:
        return f"No data returned.\nSQL:\n{sql}"

    st.dataframe(df, use_container_width=True)
    return f"Table generated.\nSQL used:\n{sql}"


# ============================================================
#  Generic SQL → Dataframe → Text Summary
# ============================================================

def handle_sql(con: duckdb.DuckDBPyConnection, question: str) -> str:
    """
    Default handler: run SQL generated from the question and show the dataframe.
    Also return the SQL as text for transparency.
    """
    sql = llm_generate_sql(con, question, purpose="generic")

    try:
        df = con.execute(sql).fetchdf()
    except Exception as e:
        return f"SQL Error:\n{e}\n\nSQL:\n{sql}"

    if df.empty:
        return f"No data returned.\nSQL:\n{sql}"

    st.dataframe(df, use_container_width=True)
    return f"SQL used:\n{sql}"


# ============================================================
#  Router
# ============================================================

def route(question: str):
    """
    Decide which handler to use based on keywords in the user's question.
    Returns a function that accepts (con, question).
    """
    q = (question or "").lower()

    # Chart intent
    if any(word in q for word in ["chart", "plot", "graph", "visualize", "trend", "time series"]):
        return handle_chart

    # Table intent
    if any(word in q for word in ["table", "list", "rows", "show me", "display"]):
        return handle_table

    # Executive narrative / report
    if any(word in q for word in ["executive", "summary", "brief", "narrative", "report", "analysis"]):
        # wrap in a lambda to match (con, question) signature
        return lambda con, q: handle_executive_narrative(con, q)

    # Fallback: generic SQL
    return handle_sql
