# ============================================================
#  CAYMAN WORKFORCE INTELLIGENCE ASSISTANT — CORE FRAMEWORK
#  STEP 1 OF 5 — DO NOT MODIFY
# ============================================================

import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from typing import Any, Optional
import time
import os
import requests
import json

from openai import OpenAI     # <-- NEW SDK

# ============================================================
# OPENAI CLIENT INITIALIZATION (REQUIRED FOR GPT)
# ============================================================
from openai import OpenAI

if "OPENAI_API_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("Missing OPENAI_API_KEY in Streamlit secrets.")
    st.stop()

# ------------------------------------------------------------
#  STREAMLIT CONFIG
# ------------------------------------------------------------
st.set_page_config(
    page_title="Cayman Workforce Intelligence Assistant",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.5rem;}
    </style>
    """,
    unsafe_allow_html=True,
)
# ============================================================
# GLOBAL UI POLISH
# ============================================================

st.markdown("""
<style>
/* KPI cards */
div[data-testid="metric-container"] {
    background-color: #F8F9FA;
    border: 1px solid #E0E0E0;
    padding: 15px;
    border-radius: 10px;
    margin-bottom: 10px;
}

/* Reduce table padding */
.dataframe th {
    font-size: 13px !important;
}
.dataframe td {
    font-size: 13px !important;
}

/* Section spacing */
.section-header {
    margin-top: 30px;
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
#  DATABASE LOADER (from db_loader.py)
# ------------------------------------------------------------
from db_loader import ensure_database

DB_PATH = ensure_database()
con = duckdb.connect(DB_PATH, read_only=True)

# ------------------------------------------------------------
#  SQL RUNNER
# ------------------------------------------------------------
def run_sql(sql: str) -> pd.DataFrame:
    try:
        return con.execute(sql).fetchdf()
    except Exception as e:
        st.error(f"SQL Error: {e}")
        return pd.DataFrame()

# ------------------------------------------------------------
#  FORMATTERS
# ------------------------------------------------------------
def fmt_ci(value: Any) -> str:
    try:
        v = float(value)
        return f"CI${v:,.0f}"
    except:
        return value

def fmt_ci_dec(value: Any) -> str:
    try:
        v = float(value)
        return f"CI${v:,.2f}"
    except:
        return value

def fmt_int(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except:
        return value

# ============================================================
# OPENAI CLIENT INITIALIZATION
# ============================================================
from openai import OpenAI

if "OPENAI_API_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("Missing OPENAI_API_KEY in Streamlit secrets.")
    st.stop()

MODEL = "gpt-4o-mini"

def ask_gpt(prompt, model="gpt-4o-mini"):
    """
    Safe, reliable GPT wrapper for the Workforce Intelligence Assistant.
    Works with all 'Ask AI' sections across the app.
    """

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert Cayman Islands labor market analyst. "
                        "Be concise, factual, and always base your answer strictly "
                        "on the data provided. Never hallucinate missing values."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.2  # stable, deterministic output
        )

        # FIXED: Extract the text safely
        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"GPT Error: {str(e)}"

# ============================================================
# SECTION-SPECIFIC AI ANALYSIS WRAPPER
# ============================================================
def ask_ai_section(prompt, data_sample, role_prompt):
    full_prompt = f"""
ROLE:
{role_prompt}

USER QUESTION:
{prompt}

DATA SAMPLE (USE ONLY THIS):
{data_sample.to_string(index=False)}

INSTRUCTIONS:
- Base your answer strictly on the dataset above.
- Do not use outside knowledge unless unavoidable.
- Be concise, factual, and Cayman-focused.
- Never hallucinate missing data.
- Identify patterns, trends, or anomalies only if visible.
""".strip()

    return ask_gpt(full_prompt)

# ------------------------------------------------------------
#  REUSABLE CHART BUILDERS
# ------------------------------------------------------------
def line_chart(df: pd.DataFrame, x: str, y: str, title: str):
    fig = px.line(df, x=x, y=y, markers=True)
    fig.update_layout(title=title, height=400)
    st.plotly_chart(fig, use_container_width=True)

def bar_chart(df: pd.DataFrame, x: str, y: str, title: str):
    fig = px.bar(df, x=x, y=y)
    fig.update_layout(title=title, height=400)
    st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------
#  PAGE NAVIGATION
# ------------------------------------------------------------
TABS = ["Ask Anything", "Labour Force Survey", "Wages (OWS)", "SPS", "Job Postings Explorer"]

selected_tab = st.sidebar.radio("Navigation", TABS)

# ------------------------------------------------------------
#  SHARED DATA REFERENCES
#  These are the NEW tables loaded from your ETL pipeline.
# ------------------------------------------------------------
TABLE_JOB_POSTINGS = "fact_job_postings_cleaned"
TABLE_LFS_OVERVIEW = "fact_lfs_overview"
TABLE_LFS_INDUSTRY = "fact_lfs_industry"
TABLE_LFS_OCC = "fact_lfs_occupation"  # may not exist
TABLE_WAGES = "fact_wages_2023"
TABLE_SPS = "fact_sps_text"

# Placeholder — next steps will define a function for each tab.
# ============================================================
# FIXED — ASK ANYTHING (Postings + Analyst Queries)
# ============================================================

if selected_tab == "Ask Anything":

    st.title("Ask Anything")

    user_q = st.text_input(
        "Ask a workforce or labour market question:",
        placeholder="e.g., Which employers posted the most tech jobs recently?"
    )

    if not user_q:
        st.stop()

    # ------------------------
    # INTENT DETECTION
    # ------------------------
    def classify(q):
        ql = q.lower()
        if "most tech" in ql: return "top_tech"
        if "least tech" in ql: return "bottom_tech"
        if "entry" in ql and "tech" in ql: return "entry_tech"
        if "highest" in ql and "salary" in ql: return "high_salary"
        if "lowest" in ql and "salary" in ql: return "low_salary"
        if "average" in ql and "salary" in ql: return "avg_salary"
        if "trend" in ql and "salary" in ql: return "salary_trend"
        return "general"

    intent = classify(user_q)

    # ------------------------
    # QUERY HELPERS
    # ------------------------
    def show_results(df, chart_type=None, x=None, y=None, title=None):
        st.dataframe(df)
        if chart_type == "bar":
            bar_chart(df, x, y, title)
        if chart_type == "line":
            line_chart(df, x, y, title)
        summary = ask_gpt(f"User question: {user_q}\nData:\n{df.to_string()}\nProvide an executive summary.")
        st.markdown("### AI Summary")
        st.write(summary)

    # ------------------------
    # INTENT ROUTE: MOST TECH
    # ------------------------
    if intent == "top_tech":
        df = run_sql(f"""
            SELECT employer_name, COUNT(*) AS tech_roles
            FROM {TABLE_JOB_POSTINGS}
            WHERE fixed_is_tech_job = TRUE
            GROUP BY employer_name
            ORDER BY tech_roles DESC
            LIMIT 15
        """)
        show_results(df, "bar", "employer_name", "tech_roles", "Top Tech Employers (Recent)")

    # ------------------------
    # INTENT ROUTE: LEAST TECH
    # ------------------------
    elif intent == "bottom_tech":
        df = run_sql(f"""
            SELECT employer_name, COUNT(*) AS tech_roles
            FROM {TABLE_JOB_POSTINGS}
            WHERE fixed_is_tech_job = TRUE
            GROUP BY employer_name
            HAVING tech_roles > 0
            ORDER BY tech_roles ASC
            LIMIT 15
        """)
        show_results(df, "bar", "employer_name", "tech_roles", "Employers With Fewest Tech Roles")

    # ------------------------
    # INTENT ROUTE: ENTRY TECH
    # ------------------------
    elif intent == "entry_tech":
        df = run_sql(f"""
            SELECT job_title, employer_name, salary_avg
            FROM {TABLE_JOB_POSTINGS}
            WHERE fixed_is_tech_job = TRUE
              AND experience_bucket = 'entry'
            ORDER BY posting_date_clean DESC
            LIMIT 50
        """)
        show_results(df)

    # ------------------------
    # INTENT ROUTE: HIGHEST SALARY
    # ------------------------
    if intent == "high_salary":
        df = run_sql(f"""
            SELECT 
                year,
                MAX((salary_min + salary_max) / 2) AS max_salary
            FROM {TABLE_JOB_POSTINGS}
            WHERE salary_min IS NOT NULL AND salary_max IS NOT NULL
            GROUP BY year
            ORDER BY year
        """)
        show_results(df, "line", "year", "max_salary", "Highest Tech Salaries by Year")

    # ------------------------
    # INTENT ROUTE: LOWEST SALARY
    # ------------------------
    elif intent == "low_salary":
        df = run_sql(f"""
            SELECT 
                year,
                MIN((salary_min + salary_max) / 2) AS min_salary
            FROM {TABLE_JOB_POSTINGS}
            WHERE salary_min IS NOT NULL AND salary_max IS NOT NULL
            GROUP BY year
            ORDER BY year
        """)
        show_results(df, "line", "year", "min_salary", "Lowest Tech Salaries by Year")

    # ------------------------
    # INTENT ROUTE: AVERAGE SALARY
    # ------------------------
    elif intent == "avg_salary":
        df = run_sql(f"""
            SELECT 
                year,
                AVG((salary_min + salary_max) / 2) AS avg_salary
            FROM {TABLE_JOB_POSTINGS}
            WHERE salary_min IS NOT NULL AND salary_max IS NOT NULL
            GROUP BY year
            ORDER BY year
        """)
        show_results(df, "line", "year", "avg_salary", "Average Tech Salaries by Year")

    # ------------------------
    # INTENT ROUTE: SALARY TREND
    # ------------------------
    elif intent == "salary_trend":
        df = run_sql(f"""
            SELECT year_month, AVG(salary_avg) AS avg_salary
            FROM {TABLE_JOB_POSTINGS}
            GROUP BY year_month
            ORDER BY year_month
        """)
        show_results(df, "line", "year_month", "avg_salary", "Salary Trend Over Time")

    # ------------------------
    # DEFAULT: GENERAL ROUTE
    # ------------------------
    else:
        df = run_sql(f"SELECT * FROM {TABLE_JOB_POSTINGS} ORDER BY posting_date_clean DESC LIMIT 50")
        show_results(df)

# ============================================================
# STEP 3 — LABOUR FORCE SURVEY (LFS) TAB
# ============================================================

if selected_tab == "Labour Force Survey":

    st.title("Labour Force Survey — Fall 2024")

    # ------------------------------------------------------------
    # LOAD DATA
    # ------------------------------------------------------------
    df_over = run_sql(f"SELECT * FROM {TABLE_LFS_OVERVIEW}")
    df_ind = run_sql(f"SELECT * FROM {TABLE_LFS_INDUSTRY}")

    # Some LFS TXT files may not include occupation data
    try:
        df_occ = run_sql(f"SELECT * FROM {TABLE_LFS_OCC}")
        has_occ = not df_occ.empty
    except:
        df_occ = pd.DataFrame()
        has_occ = False

    # ------------------------------------------------------------
    # KPI SECTION (Overview)
    # ------------------------------------------------------------
    st.subheader("Labour Force Overview")

    if df_over.empty:
        st.warning("No LFS overview data available.")
    else:
        col1, col2, col3 = st.columns(3)

        # Labour Force
        lf = df_over[df_over["metric"].str.contains("Labour Force", case=False)]
        lf_val = lf["value"].iloc[0] if not lf.empty else "N/A"
        col1.metric("Labour Force", fmt_int(lf_val))

        # Employment
        emp = df_over[df_over["metric"].str.contains("Employment", case=False)]
        emp_val = emp["value"].iloc[0] if not emp.empty else "N/A"
        col2.metric("Employment", fmt_int(emp_val))

        # Unemployment
        unemp = df_over[df_over["metric"].str.contains("Unemployment", case=False)]
        unemp_val = unemp["value"].iloc[0] if not unemp.empty else "N/A"
        col3.metric("Unemployment", fmt_int(unemp_val))

    st.markdown("---")

    # ------------------------------------------------------------
    # INDUSTRY EMPLOYMENT
    # ------------------------------------------------------------
    st.subheader("Employment by Industry")

    if df_ind.empty:
        st.warning("No LFS industry data found.")
    else:
        df_ind["employment"] = df_ind["employment"].astype(float)

        bar_chart(
            df_ind.sort_values("employment", ascending=False),
            "industry",
            "employment",
            "Employment by Industry"
        )

        st.dataframe(df_ind)

    st.markdown("---")

    # ------------------------------------------------------------
    # OCCUPATION EMPLOYMENT (Optional)
    # ------------------------------------------------------------
    if has_occ:
        st.subheader("Employment by Occupation")

        df_occ["employment"] = df_occ["employment"].astype(float)

        bar_chart(
            df_occ.sort_values("employment", ascending=False).head(20),
            "occupation",
            "employment",
            "Top 20 Occupations by Employment"
        )

        st.dataframe(df_occ)
    else:
        st.info("No LFS Occupation data available in this dataset.")

    st.markdown("---")

    # ------------------------------------------------------------
    # AI SUMMARY (Overview + Industry)
    # ------------------------------------------------------------
    if st.button("Generate AI Summary"):
        sample_text = f"""
        LFS Overview:
        {df_over.head().to_string(index=False)}

        Industry Employment:
        {df_ind.head(10).to_string(index=False)}
        """

        summary = ask_gpt(
            "Provide an accurate, concise, executive-level summary "
            "of Cayman’s Labour Force using ONLY the data below:\n\n"
            + sample_text
        )

        st.markdown("### AI Summary")
        st.write(summary)
# ============================================================
# STEP 4 — WAGES (OWS) TAB
# ============================================================

if selected_tab == "Wages (OWS)":

    st.title("Occupational Wage Survey — 2023")

    # ------------------------------------------------------------
    # LOAD WAGE DATA
    # ------------------------------------------------------------
    df_wage = run_sql(f"SELECT * FROM {TABLE_WAGES}")

    if df_wage.empty:
        st.error("No wage data found.")
        st.stop()

    # Clean numeric fields
    for col in ["employee_count", "mean", "p10", "p25", "median"]:
        df_wage[col] = pd.to_numeric(df_wage[col], errors="coerce")

    # ------------------------------------------------------------
    # KPIs
    # ------------------------------------------------------------
    st.subheader("Key Wage Indicators")

    col1, col2, col3 = st.columns(3)

    col1.metric("Total Occupations Surveyed", fmt_int(len(df_wage)))
    col2.metric("Average Mean Salary", fmt_ci_dec(df_wage["mean"].mean()))
    col3.metric("Median of Medians", fmt_ci_dec(df_wage["median"].median()))

    st.markdown("---")

    # ------------------------------------------------------------
    # TOP EARNING OCCUPATIONS
    # ------------------------------------------------------------
    st.subheader("Top Paying Occupations (By Mean Salary)")

    top_mean = df_wage.sort_values("mean", ascending=False).head(15)
    st.dataframe(top_mean)

    bar_chart(top_mean, "occupation", "mean", "Top Paying Occupations — Mean Salary")

    st.markdown("---")

    # ------------------------------------------------------------
    # DISTRIBUTION EXPLORER
    # ------------------------------------------------------------
    st.subheader("Explore Wage Distribution")

    occupations = df_wage["occupation"].unique()
    selected_occ = st.selectbox("Choose an occupation", sorted(occupations))

    df_occ = df_wage[df_wage["occupation"] == selected_occ]

    if not df_occ.empty:
        occ_row = df_occ.iloc[0]

        st.markdown(f"### {selected_occ}")
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("P10", fmt_ci_dec(occ_row["p10"]))
        d2.metric("P25", fmt_ci_dec(occ_row["p25"]))
        d3.metric("Median", fmt_ci_dec(occ_row["median"]))
        d4.metric("Mean", fmt_ci_dec(occ_row["mean"]))

        # Visualize distribution
        dist_df = pd.DataFrame({
            "Metric": ["P10", "P25", "Median", "Mean"],
            "Value": [occ_row["p10"], occ_row["p25"], occ_row["median"], occ_row["mean"]],
        })

        bar_chart(dist_df, "Metric", "Value", f"Wage Distribution — {selected_occ}")

    st.markdown("---")

    # ------------------------------------------------------------
    # AI SUMMARY
    # ------------------------------------------------------------
    if st.button("Generate AI Summary (Wages)"):
        sample = df_wage.head(20)

        prompt = (
            "You are analyzing Cayman’s Occupational Wage Survey (2023). "
            "Using ONLY the following wage data (occupations + wage distribution metrics), "
            "write a precise, executive-level summary suitable for senior leadership.\n\n"
            + sample.to_string()
        )

        summary = ask_gpt(prompt)

        st.markdown("### AI Summary (Wages)")
        st.write(summary)
# ============================================================
# STEP 5 — SPS TAB (Strategic Policy Statement 2025)
# ============================================================

if selected_tab == "SPS":

    st.title("Strategic Policy Statement (2025)")

    # ------------------------------------------------------------
    # LOAD SPS TEXT DATA
    # ------------------------------------------------------------
    df_sps = run_sql(f"SELECT * FROM {TABLE_SPS}")

    if df_sps.empty:
        st.error("No SPS text data found.")
        st.stop()

    st.markdown("### SPS Document Viewer")

    # ------------------------------------------------------------
    # SEARCH BAR
    # ------------------------------------------------------------
    keyword = st.text_input(
        "Search SPS text:",
        placeholder="e.g., workforce, skills, immigration, education"
    )

    if keyword:
        df_filtered = df_sps[df_sps["content"].str.contains(keyword, case=False, na=False)]
        st.write(f"**Matches:** {len(df_filtered)}")
        st.dataframe(df_filtered)
    else:
        st.dataframe(df_sps.head(50))

    st.markdown("---")

    # ------------------------------------------------------------
    # AI SUMMARY OF SPS CONTENT
    # ------------------------------------------------------------
    st.subheader("AI Summary")

    if st.button("Generate SPS Executive Summary"):
        sample_text = "\n".join(df_sps['content'].head(100).tolist())

        prompt = (
            "You are summarizing Cayman’s Strategic Policy Statement (2025). "
            "Use ONLY the text provided below. "
            "Produce a concise, executive-level summary suitable for senior government officials.\n\n"
            + sample_text
        )

        summary = ask_gpt(prompt)

        st.markdown("### Executive Summary")
        st.write(summary)

    st.markdown("---")

    # ------------------------------------------------------------
    # AI QUESTION ABOUT SPS CONTENT
    # ------------------------------------------------------------
    st.subheader("Ask a Question About the SPS")

    user_sps_q = st.text_input(
        "Ask about priorities, outcomes, risks, or workforce recommendations:",
        placeholder="e.g., What does the SPS say about workforce readiness?"
    )

    if user_sps_q:
        # Provide GPT only with real SPS text to avoid hallucinations
        context = "\n".join(df_sps['content'].head(300).tolist())

        prompt = (
            f"User question: {user_sps_q}\n\n"
            "Use ONLY the SPS 2025 text below. "
            "Do NOT invent information. Only answer using real content.\n\n"
            + context
        )

        answer = ask_gpt(prompt)

        st.markdown("### SPS Answer")
        st.write(answer)
# ============================================================
# JOB POSTINGS EXPLORER — ENHANCED ICT + WORKFORCE DASHBOARD
# ============================================================

if selected_tab == "Job Postings Explorer":
    
    st.title("Job Postings Explorer")
    st.write("")  # spacing
   
    # ============================================================
    # AI ROLE PROMPT FOR JOB POSTINGS EXPLORER
    # ============================================================
    JOB_EXPLORER_PROMPT = """
You are a Cayman workforce intelligence analyst with more than 20 years 
of experience studying hiring patterns, job postings, employer movement, 
skill demand, and sector-level labor dynamics in the Cayman Islands. 
You have produced workforce insights for WORC, the Ministry of Labour, 
and multiple C-Suite audiences.

Your expertise includes:
- Cayman labor market structure
- ICT job classification and tech hiring trends
- Wage patterns and salary clustering by sector
- Caymanian vs non-Caymanian hiring behavior
- Seasonal hiring cycles in Cayman
- Employer and industry demand patterns
- Senior, mid, and entry-level segmentation

Answer with precision, data discipline, and relevance to the filtered dataset.
"""

    # ===========================
    # HOW TO USE (EXPANDER) — FIXED
    # ===========================
    with st.expander("📘 How to Use the Job Postings Explorer", expanded=False):
        st.markdown("""
### **How to Use This Dashboard (WORC Staff Guide)**

**1. Start with the Time Range filter.**  
This controls the entire dashboard — all KPIs, tables, charts, and AI summaries update based on the selected timeframe.

**2. Use the Filters panel** (Industry, Vertical Sector, ICT Roles Only)  
to narrow the analysis to specific sectors or ICT roles.

**3. Review the KPIs**  
(Posts, Avg Salary, ICT %, Industries) for a high-level summary.

**4. Explore the Job Table**  
showing the most recent job postings matching the filters.

**5. Posting Trend Chart**  
visualizes activity month-by-month.

**6. ICT Analysis**  
To answer WORC's year-over-year questions:  
👉 Set **Time Range = All Time**  
Then scroll to the **ICT Analysis** section to view:  
- ICT roles per Oct-Oct window  
- ICT entry-level (1–2 yrs)  
- ICT mid-level (3–4 yrs)  
- ICT senior roles (5+ yrs)

**7. Top Employers & Top Job Titles**  
show hiring concentration and demand patterns.

**8. Ask AI About These Jobs**  
Ask any question in natural language — AI will summarize the trends based only on the filtered dataset.

---
        """)

    # Load data
    df = run_sql(f"""
        SELECT 
            posting_date_clean,
            employer_name,
            job_title,
            industry,
            industry_vertical,
            salary_min,
            salary_max,
            (salary_min + salary_max)/2 AS salary_avg,
            experience_bucket,
            fixed_is_tech_job
        FROM {TABLE_JOB_POSTINGS}
        WHERE posting_date_clean IS NOT NULL
        ORDER BY posting_date_clean DESC
    """)

    df["posting_date_clean"] = pd.to_datetime(df["posting_date_clean"])
    df["year_month"] = df["posting_date_clean"].dt.to_period("M").astype(str)

    # ===========================
    # TIME RANGE FILTER
    # ===========================
    st.subheader("Time Range")
    range_choice = st.radio(
        "Select timeframe:",
        ["Last 30 days", "Last 90 days", "Last 180 days", "Last 12 months", "All Time"],
        horizontal=True
    )

    today = df["posting_date_clean"].max()

    if range_choice == "Last 30 days":
        df = df[df["posting_date_clean"] >= today - pd.Timedelta(days=30)]
    elif range_choice == "Last 90 days":
        df = df[df["posting_date_clean"] >= today - pd.Timedelta(days=90)]
    elif range_choice == "Last 180 days":
        df = df[df["posting_date_clean"] >= today - pd.Timedelta(days=180)]
    elif range_choice == "Last 12 months":
        df = df[df["posting_date_clean"] >= today - pd.Timedelta(days=365)]

    # ===========================
    # FILTERS
    # ===========================
    with st.expander("Filters"):
        industry_opt = ["All"] + sorted(df["industry"].dropna().unique())
        vertical_opt = ["All"] + sorted(df["industry_vertical"].dropna().unique())
        selected_industry = st.selectbox("Industry (WORC)", industry_opt)
        selected_vertical = st.selectbox("Vertical Sector", vertical_opt)
        tech_only = st.selectbox("ICT Roles Only?", ["No", "Yes"])

    filtered = df.copy()

    if selected_industry != "All":
        filtered = filtered[filtered["industry"] == selected_industry]

    if selected_vertical != "All":
        filtered = filtered[filtered["industry_vertical"] == selected_vertical]

    if tech_only == "Yes":
        filtered = filtered[filtered["fixed_is_tech_job"] == True]

    # ===========================
    # SUMMARY KPIs
    # ===========================
    st.markdown("<h4 class='section-header'>Summary</h4>", unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Postings", f"{len(filtered):,}")
    col2.metric("Avg Salary", fmt_ci_dec(filtered["salary_avg"].mean()))
    col3.metric("ICT Role %", f"{(filtered['fixed_is_tech_job'].mean() * 100):.1f}%")
    col4.metric("Industries", filtered["industry"].nunique())

    # ===========================
    # DATA TABLE
    # ===========================
    st.dataframe(filtered.head(300))

    # ===========================
    # TREND CHART — FILTERED
    # ===========================
    st.markdown("<h4 class='section-header'>Posting Trend</h4>", unsafe_allow_html=True)

    df_month = (
        filtered.groupby("year_month")
        .size()
        .reset_index(name="postings")
        .sort_values("year_month")
    )

    if not df_month.empty:
        bar_chart(df_month, "year_month", "postings", "Postings per Month")
    # ============================================================
    # AI ROLE PROMPT FOR ICT ANALYSIS
    # ============================================================
    ICT_PROMPT = """
You are a Cayman Islands ICT labor market specialist with deep expertise 
in analyzing technology job postings, skill trends, employer hiring patterns, 
and year-over-year ICT demand. You understand ICT classification rules in the 
Cayman context and are fluent in WORC reporting needs.

Your expertise includes:
- ICT job classification (software, IT, data, engineering, cyber, cloud)
- Tech sector hiring patterns and employer behavior
- Entry (1–2 yrs), Mid (3–4 yrs), Senior (5+ yrs) segmentation
- Year-over-year (Oct to Oct) ICT job movement
- Salary patterns and skill signals in tech jobs
- Sector-level ICT demand (Finance, Tech, Public Sector, etc.)

All insights must be based ONLY on the ICT subset provided.
Answer with clarity, precision, and executive-grade relevance.
"""
    
    # ===========================
    # ICT ANALYSIS (FIXED)
    # ===========================
    st.markdown("### ICT Analysis (Tech Futures Week)")
    
    df_ict = filtered[filtered["fixed_is_tech_job"] == True]
    
    # Year windows: correct now that dates & buckets work
    def ict_window(start_year):
        start = pd.Timestamp(f"{start_year}-10-01")
        end = pd.Timestamp(f"{start_year+1}-10-01")
        return df_ict[(df_ict["posting_date_clean"] >= start) &
                      (df_ict["posting_date_clean"] < end)].shape[0]
    
    ranges = [2024, 2023, 2022, 2021]
    df_ict_years = pd.DataFrame([(f"Oct {y} – Oct {y+1}", ict_window(y)) for y in ranges],
                                columns=["Period", "ICT Roles"])
    st.dataframe(df_ict_years)
    
    # Entry / Mid / Senior — FIXED because bucket parser now works
    df_ict_2025 = df_ict[
        (df_ict["posting_date_clean"] >= pd.Timestamp("2024-10-01")) &
        (df_ict["posting_date_clean"] < pd.Timestamp("2025-10-01"))
    ]
    
    entry_count = df_ict_2025[df_ict_2025["experience_bucket"] == "entry"].shape[0]
    mid_count   = df_ict_2025[df_ict_2025["experience_bucket"] == "mid"].shape[0]
    senior_count = df_ict_2025[df_ict_2025["experience_bucket"] == "senior"].shape[0]
    
    col1, col2, col3 = st.columns(3)
    col1.metric("ICT Entry-Level (1–2 yrs)", entry_count)
    col2.metric("ICT Mid-Level (3–4 yrs)", mid_count)
    col3.metric("ICT Senior (5+ yrs)", senior_count)

    # ===========================
    # TOP EMPLOYERS (FILTERED)
    # ===========================
    st.markdown("### Top Employers (Filtered)")
    
    top_emp = (
        filtered.groupby("employer_name")
        .size()
        .reset_index(name="postings")
        .sort_values("postings", ascending=False)
        .head(10)
    )
    
    st.dataframe(top_emp)

    # ===========================
    # TOP JOB TITLES (FILTERED)
    # ===========================
    st.markdown("### Top Job Titles (Filtered)")
    
    top_titles = (
        filtered.groupby("job_title")
        .size()
        .reset_index(name="postings")
        .sort_values("postings", ascending=False)
        .head(10)
    )
    
    st.dataframe(top_titles)

    # ===========================
    # TOP EMPLOYERS BY SECTOR
    # ===========================
    st.markdown("<h4 class='section-header'>Top Employers by Sector</h4>", unsafe_allow_html=True)

    selected_sector = st.selectbox("Select Vertical Sector", sorted(df["industry_vertical"].dropna().unique()))
    df_sec = df[df["industry_vertical"] == selected_sector]

    top_emp = df_sec.groupby("employer_name").size().reset_index(name="postings").sort_values("postings", ascending=False).head(10)
    st.dataframe(top_emp)

    # ===========================
    # TOP JOB TITLES
    # ===========================
    st.markdown("<h4 class='section-header'>Top Job Titles</h4>", unsafe_allow_html=True)

    top_titles = filtered.groupby("job_title").size().reset_index(name="postings").sort_values("postings", ascending=False).head(10)
    st.dataframe(top_titles)

    # ===========================
    # SALARY DISTRIBUTION (LOG SCALE — BEST PRACTICE)
    # ===========================
    st.markdown("### Salary Distribution")
    
    hist_df = filtered[filtered["salary_avg"].notna()].copy()
    
    if not hist_df.empty:
        # Cap outliers (anything absurdly high)
        hist_df["salary_capped"] = hist_df["salary_avg"].clip(upper=250000)
    
        fig = px.histogram(
            hist_df,
            x="salary_capped",
            nbins=50,
            title="Salary Distribution (Log Scale, capped at CI$250,000)",
        )
    
        fig.update_layout(
            xaxis_title="Average Salary (CI$)",
            yaxis_title="Number of Postings",
            bargap=0.05,
        )
    
        # 🚀 CRITICAL FIX — make distribution readable
        fig.update_xaxes(type="log", tickformat=",.0f")
    
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.write("No salary data available for this filter.")


    # ============================================================
    # ASK AI ABOUT THESE JOBS (INTENT-AWARE + ROLE-AWARE)
    # ============================================================
    st.markdown("### Ask AI About These Jobs")

    user_q = st.text_input("Ask a question about the filtered postings:")

    if user_q:

        # --- INTENT DETECTION: Should AI restrict to ICT roles? ---
        q = user_q.lower()
        tech_terms = ["tech", "ict", "it ", "it job", "technology", "software",
                      "developer", "computer", "engineer", "cyber"]

        # If user is asking about ICT, force ICT subset
        if any(t in q for t in tech_terms):
            ai_df = filtered[filtered["fixed_is_tech_job"] == True]
        else:
            ai_df = filtered

        # Protect against empty ICT datasets
        if ai_df.empty:
            st.warning("No matching job postings found in this timeframe for your question.")
        sample = ai_df.head(100)

        # --- CALL THE SECTION-SPECIFIC ANALYST ---
        ai_response = ask_ai_section(
            user_q,
            sample,
            JOB_EXPLORER_PROMPT
        )

        st.markdown("### Executive Summary")
        st.write(ai_response)

   
