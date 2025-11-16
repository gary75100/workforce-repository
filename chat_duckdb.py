import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st
from openai import OpenAI


client = OpenAI()


# ============================================================
#  CORE UTILITIES
# ============================================================

def list_tables(con):
    try:
        return [r[0] for r in con.execute("SHOW TABLES").fetchall()]
    except:
        return []


def get_schema(con):
    """Return {table: [cols]} for all tables."""
    tables = list_tables(con)
    schema = {}
    for t in tables:
        try:
            df = con.execute(f"PRAGMA table_info('{t}')").fetchdf()
            schema[t] = list(df["name"])
        except:
            schema[t] = []
    return schema


def clean_sql(sql):
    if not sql:
        return ""
    sql = (
        sql.replace("```sql", "")
        .replace("```", "")
        .replace("`", "")
        .strip()
    )
    lower = sql.lower()
    if "generated sql:" in lower:
        sql = sql.split("generated sql:", 1)[-1]
    if sql.lower().startswith("sql:"):
        sql = sql.split(":", 1)[-1]
    return sql.strip()


# ============================================================
#  DATASET CLASSIFICATION
# ============================================================

def classify_tables(con):
    tables = list_tables(con)
    groups = {"lfs": [], "sps": [], "job": [], "worc": [], "other": []}
    for t in tables:
        name = t.lower()
        if "lfs" in name:
            groups["lfs"].append(t)
        elif "sps" in name:
            groups["sps"].append(t)
        elif "job_postings" in name:
            groups["job"].append(t)
        elif "worc_data_v3" in name:
            groups["worc"].append(t)
        else:
            groups["other"].append(t)
    return groups


# ============================================================
#  SCHEMA-AWARE + DATASET-AWARE SQL GENERATION
# ============================================================

def generate_sql(con, question, purpose):
    question_lower = question.lower()

    schema = get_schema(con)
    groups = classify_tables(con)
    all_tables = list(schema.keys())

    # PICK TABLES BY TOPIC
    relevant = []

    if any(w in question_lower for w in ["unemployment", "labour force", "caymanian", "jobless"]):
        relevant += groups["lfs"]

    if any(w in question_lower for w in ["job posting", "vacancy", "postings", "industry demand"]):
        relevant += groups["job"]

    if "sps" in question_lower:
        relevant += groups["sps"]

    if "worc" in question_lower or "v3" in question_lower:
        relevant += groups["worc"]

    if not relevant:
        relevant = all_tables

    # BUILD SCHEMA TEXT FOR PROMPT
    schema_lines = []
    for t in relevant:
        cols = schema[t]
        schema_lines.append(f"- {t}: {', '.join(cols)}")
    schema_text = "\n".join(schema_lines)

    # BUILD PROMPT
    instructions = (
        "Return ONLY SQL. No markdown. "
        "Use EXACT column names from schema. "
        "Do NOT invent or guess columns. "
        "If question needs a time trend, pick the most date-like column."
    )

    if purpose == "chart":
        instructions += " SQL must return a date/time column + a numeric column suitable for plotting."
    if purpose == "table":
        instructions += " SQL must return a meaningful table."
    if purpose == "generic":
        instructions += " SQL must answer the question directly."

    prompt = f"""
You are a DuckDB SQL generator.

User question:
\"\"\"{question}\"\"\"

Relevant tables and columns:
{schema_text}

{instructions}
"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        temperature=0,
        messages=[
            {"role": "system", "content": "Output ONLY valid DuckDB SQL."},
            {"role": "user", "content": prompt}
        ]
    )

    raw_sql = resp.choices[0].message.content
    return clean_sql(raw_sql)


# ============================================================
#  CHART ENGINE
# ============================================================

def handle_chart(con, question):
    sql = generate_sql(con, question, "chart")

    try:
        df = con.execute(sql).fetchdf()
    except Exception as e:
        return f"SQL Error:\n{e}\n\nSQL:\n{sql}"

    if df.empty:
        return f"No data returned.\nSQL:\n{sql}"

    x = df.columns[0]
    numeric = df.select_dtypes(include="number").columns.tolist()
    if not numeric:
        return f"No numeric fields to chart.\nSQL:\n{sql}"

    y = numeric

    fig = px.line(df, x=x, y=y, markers=True)
    st.plotly_chart(fig, use_container_width=True)
    return f"Chart generated.\nSQL:\n{sql}"


# ============================================================
#  TABLE ENGINE
# ============================================================

def handle_table(con, question):
    sql = generate_sql(con, question, "table")

    try:
        df = con.execute(sql).fetchdf()
    except Exception as e:
        return f"SQL Error:\n{e}\n\nSQL:\n{sql}"

    if df.empty:
        return f"No data returned.\nSQL:\n{sql}"

    st.dataframe(df, use_container_width=True)
    return f"Table generated.\nSQL:\n{sql}"


# ============================================================
#  EXECUTIVE NARRATIVE ENGINE
# ============================================================

def handle_narrative(con, question):
    tables = list_tables(con)

    # sample from tables
    samples = []
    for t in tables:
        try:
            df = con.execute(f"SELECT * FROM {t} LIMIT 5").fetchdf()
            samples.append(f"TABLE {t} SAMPLE:\n{df.to_string(index=False)}")
        except:
            pass

    context = "\n\n".join(samples)[:7000]

    prompt = f"""
You are an expert Cayman Islands workforce strategist.

User asked:
\"\"\"{question}\"\"\"

Here is sample data from the workforce data lake:
{context}

Write a clear executive-level narrative with:
- labour force trends
- Caymanian vs non-Caymanian dynamics
- unemployment themes
- industry demand signals
- SPS + WORC implications

Do NOT mention table names or SQL.
Write naturally, as if for Cabinet-level briefing.
"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.4,
        messages=[
            {"role": "system", "content": "Provide executive workforce analysis."},
            {"role": "user", "content": prompt}
        ]
    )

    return resp.choices[0].message.content


# ============================================================
#  GENERIC SQL
# ============================================================

def handle_sql(con, question):
    sql = generate_sql(con, question, "generic")

    try:
        df = con.execute(sql).fetchdf()
    except Exception as e:
        return f"SQL Error:\n{e}\n\nSQL:\n{sql}"

    if df.empty:
        return f"No data returned.\nSQL:\n{sql}"

    st.dataframe(df, use_container_width=True)
    return f"SQL:\n{sql}"


# ============================================================
#  ROUTER
# ============================================================

def route(question: str):
    q = question.lower()

    if any(w in q for w in ["chart", "plot", "graph", "trend", "visualize"]):
        return handle_chart

    if any(w in q for w in ["table", "list", "rows", "show"]):
        return handle_table

    if any(w in q for w in ["executive", "summary", "brief", "narrative", "report"]):
        return handle_narrative

    return handle_sql
