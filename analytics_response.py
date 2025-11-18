# analytics_response.py

import streamlit as st
import pandas as pd
from formatting import format_ci_currency, format_int
import plotly.express as px


def render_analytics_response(
    df: pd.DataFrame,
    question: str,
    gpt_client=None,
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

    # 1) DATA TABLE
    st.subheader("Data")

    df_display = df.copy()
    for col in df_display.columns:
        if "salary" in col.lower():
            df_display[col] = df_display[col].apply(format_ci_currency)

    st.dataframe(df_display)

    # 2) CHART
    st.subheader("Chart")

    if chart_type == "auto":
        # Ensure salary columns remain numeric for charting
        for col in df.columns:
            if "salary" in col.lower():
                df[col] = pd.to_numeric(df[col], errors="coerce")
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
            counts = df[x_col].value_counts().sort_index()
            fig = px.bar(x=counts.index, y=counts.values)

        fig.update_layout(
            xaxis_title=x_col,
            yaxis_title=y_col or "Count",
        )

        st.plotly_chart(fig, use_container_width=True)

    else:
        st.write("Chart type not implemented yet.")

    # 3) EXECUTIVE AI SUMMARY
    st.subheader(summary_title)

    sample = df.head(100).to_dict(orient="records")

    prompt = f"""
You are an executive-level labour market analyst supporting the Cayman Islands government.

User question:
{question}

Write a concise, professional summary using ONLY the data provided below.
Avoid speculation or external facts.

Data (first 100 records):
{sample}
"""

    try:
        from app import ask_gpt   # imported here to avoid circular import
        summary_text = ask_gpt(prompt).strip()
    except Exception as e:
        summary_text = f"Unable to generate AI summary: {e}"

    st.write(summary_text)
    return summary_text

