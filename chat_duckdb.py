import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st
from openai import OpenAI

# Load API key
client = OpenAI()

############################################################
# 1. SQL GENERATION ENGINE (LLM)
############################################################

def llm_generate_sql(question: str, tables: list[str]) -> str:
    """
    Asks the LLM to generate a SQL query based on the question.
    Ensures the LLM ONLY outputs SQL with no explanation.
    """
    table_list = ", ".join(tables)

    prompt = f"""
    You are a SQL generator for DuckDB.
    The user asked: "{question}"
    
    Available tables in the database are: {table_list}.
    
    Write ONLY a valid DuckDB SQL query.
    No commentary.
    No explanation.
    No markdown formatting.
    Just SQL.
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0,
        messages=[
            {"role": "system", "content": "Output only SQL queries."},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message["content"].strip()


############################################################
# 2. EXECUTIVE NARRATIVE ENGINE
############################################################

def generate_executive_narrative(question: str, con):
    """
    Produces a C-suite style executive analysis that can reference multiple tables.
    Combines SQL retrieval with LLM reasoning.
    """

    # Pull table list
    tables = [row[0] for row in con.execute("SHOW TABLES").fetchall()]

    sql_prompt = f"""
    The user asked for an executive-level analysis:

    "{question}"

    You have access to the following dataset tables:
    {tables}

    First, identify the 3–5 most relevant tables.
    Then write a **C-suite, strategic narrative** using trends, data interpretation,
    workforce risk framing, SPS themes, LFS insights, and job market signals.
    
    Do NOT output SQL.
    Do NOT reference table names directly.
    Write like a Senior Workforce Economist briefing Cabinet leadership.
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.25,
        messages=[
            {"role": "system", "content": "Write executive-level workforce analysis."},
            {"role": "user", "content": sql_prompt}
        ]
    )

    return response.choices[0].message["content"]


############################################################
# 3. CHART ENGINE (PLOTLY)
############################################################

def generate_chart(con, question: str):
    """
    Detects chart intent, generates SQL, executes it, and renders Plotly charts.
    """

    # Get table list
    tables = [row[0] for row in con.execute("SHOW TABLES").fetchall()]

    # Get SQL from LLM
    sql = llm_generate_sql(question, tables)

    # Run SQL
    try:
        df = con.execute(sql).fetchdf()
    except Exception as e:
        return f"SQL Error: {e}\nGenerated SQL:\n{sql}"

    if df.empty:
        return f"No data returned.\nSQL:\n{sql}"

    # Require at least one numeric column
    numeric_cols = df.select_dtypes(include=["float", "int"]).columns
    if len(numeric_cols) == 0:
        return f"SQL returned no numeric fields to plot.\nSQL:\n{sql}"

    # If dataframe contains date-like strings, convert them
    for col in df.columns:
        if df[col].dtype == object:
            try:
                df[col] = pd.to_datetime(df[col])
            except:
                pass

    # Plot with Plotly
    fig = px.line(df, x=df.columns[0], y=df.columns[1:], markers=True)
    st.plotly_chart(fig, use_container_width=True)

    return f"Chart generated.\nSQL used:\n{sql}"


############################################################
# 4. TABLE OUTPUT ENGINE
############################################################

def generate_table(con, question: str):
    """
    Returns a table (dataframe) based on LLM-generated SQL.
    """

    tables = [row[0] for row in con.execute("SHOW TABLES").fetchall()]
    sql = llm_generate_sql(question, tables)

    try:
        df = con.execute(sql).fetchdf()
    except Exception as e:
        return f"SQL Error: {e}\nSQL:\n{sql}"

    if df.empty:
        return f"No data returned.\nSQL:\n{sql}"

    st.dataframe(df, use_container_width=True)
    return f"Table generated.\nSQL used:\n{sql}"


############################################################
# 5. GENERAL SQL QUERY ENGINE
############################################################

def handle_sql(con, question: str):
    """
    Handles normal queries that should return text answers or summaries.
    """
    tables = [row[0] for row in con.execute("SHOW TABLES").fetchall()]
    sql = llm_generate_sql(question, tables)

    try:
        df = con.execute(sql).fetchdf()
    except Exception as e:
        return f"SQL Error: {e}\n{sql}"

    # Show the dataframe
    st.dataframe(df)
    return f"SQL used:\n{sql}"


############################################################
# 6. ROUTER — DECIDES WHICH ENGINE TO USE
############################################################

def route(question: str):
    q = question.lower()

    # Chart / plot detection
    if any(word in q for word in ["chart", "plot", "graph", "visualize", "trend", "line chart", "bar chart"]):
        return generate_chart

    # Table request
    if any(word in q for word in ["table", "list", "show me rows", "display rows"]):
        return generate_table

    # Executive / C-suite analysis
    if any(word in q for word in ["executive", "summary", "brief", "narrative", "analysis", "report", "insights"]):
        return generate_executive_narrative

    # Default: general SQL-based retrieval
    return handle_sql
