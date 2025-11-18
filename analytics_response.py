# analytics_response.py

import streamlit as st
import pandas as pd
from app import ask_gpt

from formatting import format_ci_currency, format_int

def render_analytics_response(
    df: pd.DataFrame,
    question: str,
    gpt_client,
    summary_title: str = "AI Summary",
    chart_type: str = "auto",
) -> str:
    """
    Standard output contract:
    1) Data table (with basic formatting)
    2) Chart appropriate to the data
    3) Executive-level AI summary, strictly data-bound
    """

    if df.empty:
        st.info("No data available for this query.")
        return "No data available for this query."

    # 1) Data table
    st.subheader("Data")
    st.dataframe(df)  # we can add column-wise formatting later

    # 2) Chart
    st.subheader("Chart")

###############################
# PLOTLY AUTO-CHART (RELIABLE)
###############################
import plotly.express as px

if chart_type == "auto":
    # Pick x-axis
    if "year_month" in df.columns:
        x_col = "year_month"
    elif "posted_date" in df.columns:
        x_col = "posted_date"
    else:
        x_col = df.columns[0]

    # Pick y-axis
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    y_col = numeric_cols[0] if numeric_cols else None

    if y_col:
        fig = px.line(df, x=x_col, y=y_col, markers=True)
    else:
        # fallback — just show counts by x_col
        counts = df[x_col].value_counts().sort_index()
        fig = px.bar(x=counts.index, y=counts.values)

    fig.update_layout(xaxis_title=x_col, yaxis_title=y_col or "Count")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.write("Chart type not implemented yet.")

    else:
        # later we can add explicit chart types if needed
        st.write("Chart type not implemented yet.")

    # 3) Executive AI summary – data-bound
    st.subheader(summary_title)

    # Prepare a compact, data-safe sample to send to GPT
    sample = df.head(100).to_dict(orient="records")

    prompt = f"""
You are an executive-level labour market analyst supporting the Cayman Islands government.

The user question was:
{question}

You are given a subset of the data as a list of records (JSON-like).
Write a concise, professional summary that:

- Describes what the data shows.
- Highlights key trends, differences, or notable points.
- Uses ONLY the numbers and facts present in the data.
- Avoids speculation, frilly language, or external sources.
- Writes in a neutral, analytical tone, suitable for a briefing.

Data (first 100 records):
{sample}
"""

    # Use your existing GPT client wrapper here; this call is just illustrative
    try:
        response = ask_gpt(prompt) # adapt to your actual method
        summary_text = response.strip()
    except Exception as e:
        summary_text = f"Unable to generate AI summary: {e}"

    st.write(summary_text)

    return summary_text

