# analytics_response.py

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

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

    fig, ax = plt.subplots()

    if chart_type == "auto":
        # Very simple heuristic for now; we can refine later
        if "year_month" in df.columns:
            x_col = "year_month"
        elif "posted_date" in df.columns:
            x_col = "posted_date"
        else:
            x_col = df.columns[0]

        # pick a numeric y
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        y_col = numeric_cols[0] if numeric_cols else None

        if y_col:
            ax.plot(df[x_col], df[y_col], marker="o")
            ax.set_xlabel(x_col)
            ax.set_ylabel(y_col)
        else:
            # fallback to simple bar of counts
            counts = df[x_col].value_counts().sort_index()
            ax.bar(counts.index, counts.values)
            ax.set_xlabel(x_col)
            ax.set_ylabel("Count")

        plt.xticks(rotation=45)
        plt.tight_layout()
        st.pyplot(fig)
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
        response = gpt_client.generate_text(prompt)  # adapt to your actual method
        summary_text = response.strip()
    except Exception as e:
        summary_text = f"Unable to generate AI summary: {e}"

    st.write(summary_text)

    return summary_text

