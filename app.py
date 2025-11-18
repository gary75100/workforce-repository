###############################################################
#  SECTION 1 — GLOBAL IMPORTS + CONFIG + GPT ENGINE + DB SETUP
###############################################################

import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
import time
from datetime import datetime, timedelta
from openai import OpenAI, RateLimitError, APIError, APIConnectionError, APITimeoutError

from db_loader import ensure_database


###############################################################
#  STREAMLIT PAGE SETTINGS
###############################################################

st.set_page_config(
    page_title="Cayman Workforce Intelligence Assistant",
    layout="wide"
)

MODEL_NAME = "gpt-4.1"

# Global OpenAI client
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])


###############################################################
#  GPT ENGINE — ENTERPRISE SAFE
###############################################################

from openai import OpenAI
from openai import APIError, APIConnectionError, APITimeoutError, RateLimitError
import time

def ask_gpt(
    prompt,
    system="You are a Cayman labour market analyst. Provide precise, executive-level insights based on the data."
):
    """
    Enterprise-safe GPT caller with:
    - Retry logic with exponential backoff
    - Graceful rate-limit handling
    - Fallback client recovery
    - Clean, predictable output
    - No exceptions propagate to UI
    """

    retries = 4
    delay = 1

    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=900,
            )

            # Correct OpenAI v1 SDK access
            return response.choices[0].message.content.strip()

        except RateLimitError:
            # === RATE LIMIT HANDLING (your problem from this morning) ===
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            return "⚠️ AI is temporarily rate-limited. Please retry in a moment."

        except (APIError, APIConnectionError, APITimeoutError):
            # === FALLBACK CLIENT RECOVERY ===
            try:
                fallback = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
                response = fallback.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=900,
                )
                return response.choices[0].message.content.strip()
            except:
                pass

            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
                continue

            return "⚠️ AI Error: Unable to contact OpenAI."

        except Exception as e:
            # === CATCH-ALL PROTECTION ===
            return f"⚠️ AI Error: {str(e)}"

    return "⚠️ AI Error: Fatal failure."

###############################################################
#  DATABASE SETUP
###############################################################

db_path = ensure_database()
conn = duckdb.connect(db_path, read_only=False)

def run_sql(sql: str) -> pd.DataFrame:
    try:
        return conn.execute(sql).df()
    except Exception as e:
        st.error(f"SQL Error: {e}")
        return pd.DataFrame()


###############################################################
#  CURRENCY FORMATTER
###############################################################

def fmt_currency(x):
    """Format all numeric salaries as CI$ 12,345"""
    if x is None or x == "" or pd.isna(x):
        return "—"
    try:
        return f"CI$ {x:,.0f}"
    except:
        return "—"
###############################################################
#  SECTION 2 — INTENT CLASSIFIER + ROUTED QUESTIONS + CHAT TAB
###############################################################

############################################
# INTENT LABELS (Your 7 guaranteed questions)
############################################

INTENT_LABELS = """
- employer_most_tech_roles
- employer_least_tech_roles
- entry_level_tech_roles
- highest_tech_salary_by_year
- lowest_tech_salary_by_year
- average_tech_salary_by_year
- tech_salary_trend
- general_question
"""


############################################
# INTENT CLASSIFIER — GPT-4.1
############################################

def classify_intent(user_q: str) -> str:
    prompt = f"""
    Classify the user question into EXACTLY one of:

    {INTENT_LABELS}

    USER QUESTION:
    "{user_q}"

    Respond with ONLY the label, no explanation.
    """

    intent = ask_gpt(prompt).strip().lower()

    # Safety: normalize unexpected responses
    if intent not in INTENT_LABELS:
        return "general_question"
    return intent


############################################
# RENDER HELPERS — tables + charts
############################################

def render_table(df, title=None):
    if title:
        st.subheader(title)
    st.dataframe(df, use_container_width=True)


def render_line(df, x, y, color=None, title=None):
    fig = px.line(df, x=x, y=y, color=color, markers=True, title=title)
    st.plotly_chart(fig, use_container_width=True)


############################################
# 7 GUARANTEED QUESTIONS — SQL HANDLERS
############################################

def answer_employer_most_tech():
    sql = """
        SELECT employer_name, COUNT(*) AS tech_roles
        FROM curated.fact_job_posting
        WHERE is_tech_role = TRUE
        GROUP BY employer_name
        ORDER BY tech_roles DESC
        LIMIT 1;
    """
    df = run_sql(sql)
    render_table(df, "Employer With Most Tech Roles")
    st.markdown("### AI Interpretation")
    st.write(ask_gpt(f"Interpret this result:\n{df.to_json()}"))


def answer_employer_least_tech():
    sql = """
        SELECT employer_name, COUNT(*) AS tech_roles
        FROM curated.fact_job_posting
        WHERE is_tech_role = TRUE
        GROUP BY employer_name
        HAVING COUNT(*) > 0
        ORDER BY tech_roles ASC
        LIMIT 1;
    """
    df = run_sql(sql)
    render_table(df, "Employer With Fewest Tech Roles")
    st.markdown("### AI Interpretation")
    st.write(ask_gpt(f"Interpret this result:\n{df.to_json()}"))


def answer_entry_level_tech():
    sql = """
        SELECT job_title, employer_name, required_education, years_experience
        FROM curated.fact_job_posting
        WHERE is_tech_role = TRUE AND is_entry_level = TRUE
        ORDER BY posted_date DESC
        LIMIT 200;
    """
    df = run_sql(sql)
    render_table(df, "Entry-Level Tech Roles (Most Recent)")
    st.markdown("### AI Interpretation")
    st.write(ask_gpt(f"Summarize common requirements:\n{df.to_json()}"))


def answer_highest_tech_salary():
    sql = """
        SELECT EXTRACT(YEAR FROM posted_date) AS year,
               MAX(salary_max) AS highest_salary
        FROM curated.fact_job_posting
        WHERE is_tech_role = TRUE
        GROUP BY year
        ORDER BY year;
    """
    df = run_sql(sql)
    df["highest_salary"] = df["highest_salary"].apply(fmt_currency)
    render_table(df, "Highest Tech Salary by Year")
    render_line(df, "year", "highest_salary", title="Tech Salary Ceiling Trend")
    st.markdown("### AI Interpretation")
    st.write(ask_gpt(f"Explain the tech salary ceiling trend:\n{df.to_json()}"))


def answer_lowest_tech_salary():
    sql = """
        SELECT EXTRACT(YEAR FROM posted_date) AS year,
               MIN(salary_min) AS lowest_salary
        FROM curated.fact_job_posting
        WHERE is_tech_role = TRUE 
          AND salary_min > 1000
        GROUP BY year
        ORDER BY year;
    """
    df = run_sql(sql)
    df["lowest_salary"] = df["lowest_salary"].apply(fmt_currency)
    render_table(df, "Lowest Tech Salary by Year")
    render_line(df, "year", "lowest_salary", title="Tech Salary Floor Trend")
    st.markdown("### AI Interpretation")
    st.write(ask_gpt(f"Explain lower salary bounds:\n{df.to_json()}"))


def answer_avg_tech_salary():
    sql = """
        SELECT EXTRACT(YEAR FROM posted_date) AS year,
               AVG((salary_min + salary_max)/2) AS avg_salary
        FROM curated.fact_job_posting
        WHERE is_tech_role = TRUE
        GROUP BY year
        ORDER BY year;
    """
    df = run_sql(sql)
    df["avg_salary"] = df["avg_salary"].apply(fmt_currency)
    render_table(df, "Average Tech Salary by Year")
    render_line(df, "year", "avg_salary", title="Average Tech Salary Trend")
    st.markdown("### AI Interpretation")
    st.write(ask_gpt(f"Explain average tech earnings:\n{df.to_json()}"))


def answer_tech_salary_trend():
    sql = """
        SELECT posted_date,
               (salary_min + salary_max)/2 AS salary
        FROM curated.fact_job_posting
        WHERE is_tech_role = TRUE
        ORDER BY posted_date;
    """
    df = run_sql(sql)
    df["salary"] = df["salary"].apply(fmt_currency)
    render_table(df.head(50), "Most Recent Tech Salaries")
    render_line(df, "posted_date", "salary", title="Tech Salary Trend Over Time")
    st.markdown("### AI Interpretation")
    st.write(ask_gpt(f"Interpret salary momentum:\n{df.to_json()}"))


###############################################################
#   ASK ANYTHING TAB
###############################################################

tab_chat, tab_lfs, tab_wages, tab_jobs, tab_sps = st.tabs(
    ["💬 Ask Anything", "📊 LFS", "💵 Wages", "📈 Job Postings", "📘 SPS"]
)

with tab_chat:

    st.header("Ask Any Workforce Question")

    user_q = st.text_input(
        "Your question:",
        placeholder="e.g., What employer posts the most tech roles?",
        key="ask_anything_q"
    )

    if user_q:

        # Identify user intent
        intent = classify_intent(user_q)
        st.info(f"Detected intent: **{intent}**")

        # Route to correct handler
        if intent == "employer_most_tech_roles":
            answer_employer_most_tech()
            st.stop()

        if intent == "employer_least_tech_roles":
            answer_employer_least_tech()
            st.stop()

        if intent == "entry_level_tech_roles":
            answer_entry_level_tech()
            st.stop()

        if intent == "highest_tech_salary_by_year":
            answer_highest_tech_salary()
            st.stop()

        if intent == "lowest_tech_salary_by_year":
            answer_lowest_tech_salary()
            st.stop()

        if intent == "average_tech_salary_by_year":
            answer_avg_tech_salary()
            st.stop()

        if intent == "tech_salary_trend":
            answer_tech_salary_trend()
            st.stop()

        # GENERAL QUESTION — fallback GPT
        st.subheader("AI Analysis")

        # Provide recent sample for context
        sample = run_sql("""
            SELECT *
            FROM curated.fact_job_posting
            ORDER BY posted_date DESC
            LIMIT 50;
        """)

        ai_answer = ask_gpt(
            f"User asked: {user_q}\nHere is recent Cayman labour data:\n{sample.to_json(orient='records')}\nProvide an accurate, executive-level answer."
        )

        st.write(ai_answer)
###############################################################
#  SECTION 3 — LFS TAB (Labour Force Survey)
###############################################################

with tab_lfs:

    st.header("Labour Force Survey (LFS)")

    ###########################################################
    # LOAD MOST RECENT LFS DATA
    ###########################################################

    df_status = run_sql("""
        SELECT *
        FROM curated.fact_lfs_overview_status
        ORDER BY survey_date DESC;
    """)

    df_participation = run_sql("""
        SELECT *
        FROM curated.fact_lfs_participation
        ORDER BY survey_date DESC;
    """)

    df_sex = run_sql("""
        SELECT *
        FROM curated.fact_lfs_overview_sex
        ORDER BY survey_date DESC;
    """)

    # MOST RECENT LFS DATE
    latest_date = (
        df_status["survey_date"].max()
        if not df_status.empty
        else None
    )

    if latest_date:
        st.subheader(f"Latest LFS Survey: **{latest_date.strftime('%B %Y')}**")

    ###########################################################
    # DISPLAY MOST RECENT OVERVIEW TABLE
    ###########################################################

    st.subheader("LFS Overview (Most Recent)")
    latest_status = df_status[df_status["survey_date"] == latest_date]
    st.dataframe(latest_status, use_container_width=True)

    ###########################################################
    # KPI CARDS
    ###########################################################

    st.subheader("Key Metrics")

    col1, col2, col3 = st.columns(3)

    try:
        employed = latest_status[latest_status["status"] == "employed"]["value"].iloc[0]
        unemployed = latest_status[latest_status["status"] == "unemployed"]["value"].iloc[0]
        labour_force = latest_status[latest_status["status"] == "labour_force"]["value"].iloc[0]
    except:
        employed = unemployed = labour_force = None

    col1.metric("Employed", f"{employed:,.0f}" if employed else "—")
    col2.metric("Unemployed", f"{unemployed:,.0f}" if unemployed else "—")
    col3.metric("Labour Force", f"{labour_force:,.0f}" if labour_force else "—")

    ###########################################################
    # TREND CHART — STATUS OVER TIME
    ###########################################################

    if not df_status.empty:
        fig = px.line(
            df_status,
            x="survey_date",
            y="value",
            color="status",
            markers=True,
            title="LFS Status Trend Over Time",
        )
        st.plotly_chart(fig, use_container_width=True)

    ###########################################################
    # PARTICIPATION RATE TREND
    ###########################################################

    st.subheader("Labour Force Participation Rates")

    if not df_participation.empty:
        fig2 = px.line(
            df_participation,
            x="survey_date",
            y="value",
            color="category",
            markers=True,
            title="Participation Rate by Category",
        )
        st.plotly_chart(fig2, use_container_width=True)

    ###########################################################
    # LFS TAB — ASK A QUESTION ABOUT THIS DATA
    ###########################################################

    st.subheader("Ask a Question About LFS Data")

    lfs_q = st.text_input(
        "Ask about labour force patterns, participation, or employment trends:",
        placeholder="e.g., What is the unemployment trend for Caymanians?",
        key="lfs_question"
    )

    if lfs_q:
        snippet = df_status.head(60).to_json(orient="records")
        analysis = ask_gpt(
            f"""
            The user asked about the Labour Force Survey (LFS):

            QUESTION:
            {lfs_q}

            Here is sample LFS data (status overview, newest first):
            {snippet}

            Provide an accurate, executive-level analysis using only this dataset.
            """
        )
        st.markdown("### AI Answer")
        st.write(analysis)

    ###########################################################
    # LFS TAB — SUMMARIZE DATA
    ###########################################################

    st.subheader("Summarize the Latest LFS Data")

    if st.button("Summarize LFS With AI"):
        combined = pd.concat([df_status, df_participation, df_sex]).head(200)
        summary = ask_gpt(
            f"""
            Produce an executive summary of the Cayman Islands Labour Force Survey.

            Use ONLY this dataset:
            {combined.to_json(orient='records')}

            Include:
            - overall employment trends
            - unemployment interpretation
            - participation rate insights
            - demographic comparisons
            - any meaningful risks or opportunities
            - concise and business-ready explanation
            """
        )

        st.markdown("### AI Summary")
        st.write(summary)
###############################################################
#  SECTION 4 — OCCUPATIONAL WAGE SURVEY (OWS) TAB
###############################################################

with tab_wages:

    st.header("Occupational Wage Survey (OWS)")

    ###########################################################
    # LOAD MOST RECENT WAGE DATA
    ###########################################################

    df_wages = run_sql("""
        SELECT *
        FROM curated.fact_wages
        ORDER BY survey_date DESC;
    """)

    if df_wages.empty:
        st.warning("No wage survey data available.")
        st.stop()

    latest_wage_date = df_wages["survey_date"].max()

    st.subheader(f"Latest Wage Survey: **{latest_wage_date.strftime('%B %Y')}**")

    latest_wages = df_wages[df_wages["survey_date"] == latest_wage_date]

    ###########################################################
    # DISPLAY TABLE
    ###########################################################

    st.subheader("Wage Overview (Most Recent)")
    df_display = latest_wages.copy()
    df_display["value"] = df_display["value"].apply(fmt_currency)
    st.dataframe(df_display, use_container_width=True, height=500)

    ###########################################################
    # KPI CARDS
    ###########################################################

    st.subheader("Key Compensation Metrics")

    col1, col2, col3 = st.columns(3)

    try:
        highest = latest_wages["value"].max()
        lowest = latest_wages["value"].min()
        avg = latest_wages["value"].mean()
    except:
        highest = lowest = avg = None

    col1.metric("Highest Earnings", fmt_currency(highest))
    col2.metric("Average Earnings", fmt_currency(avg))
    col3.metric("Lowest Earnings", fmt_currency(lowest))

    ###########################################################
    # BAR CHART — MEAN EARNINGS BY INDUSTRY
    ###########################################################

    st.subheader("Mean Monthly Earnings by Industry")

    df_mean_industry = run_sql(f"""
        SELECT subcategory AS industry,
               value
        FROM curated.fact_wages
        WHERE survey_date = '{latest_wage_date}'
          AND category = 'industry'
          AND measure_type = 'basic_earnings'
          AND metric = 'mean'
        ORDER BY value DESC;
    """)

    if not df_mean_industry.empty:
        fig = px.bar(
            df_mean_industry,
            x="industry",
            y="value",
            title="Mean Industry Earnings",
        )
        fig.update_traces(marker_color="#1f77b4")
        fig.update_layout(xaxis_tickangle=45)
        st.plotly_chart(fig, use_container_width=True)

    ###########################################################
    # BOX CHART — INDUSTRY DISTRIBUTION
    ###########################################################

    st.subheader("Earnings Distribution (Box Plot)")

    df_box = latest_wages.copy()
    df_box["value"] = df_box["value"]
    if not df_box.empty:
        fig_box = px.box(
            df_box,
            x="subcategory",
            y="value",
            title="Distribution of Earnings",
        )
        fig_box.update_layout(xaxis_tickangle=45)
        st.plotly_chart(fig_box, use_container_width=True)

    ###########################################################
    # WAGES TAB — ASK A QUESTION ABOUT THIS DATA
    ###########################################################

    st.subheader("Ask a Question About Wage Data")

    wages_q = st.text_input(
        "Ask about compensation, high earners, industry comparisons, or trends:",
        placeholder="e.g., Which industry has the highest average earnings?",
        key="wages_question"
    )

    if wages_q:
        snippet = latest_wages.head(60).to_json(orient="records")
        analysis = ask_gpt(
            f"""
            The user asked a question about Cayman wage levels.

            QUESTION:
            {wages_q}

            Here is the wage dataset (most recent):
            {snippet}

            Provide an accurate, executive-level answer.
            """
        )
        st.markdown("### AI Answer")
        st.write(analysis)

    ###########################################################
    # WAGES TAB — SUMMARIZE DATA
    ###########################################################

    st.subheader("Summarize Wage Survey With AI")

    if st.button("Summarize Wages With AI"):
        combined = df_wages[df_wages["survey_date"] == latest_wage_date]
        summary = ask_gpt(
            f"""
            Provide an executive summary of the latest Cayman Occupational Wage Survey.

            Use ONLY this dataset:
            {combined.to_json(orient='records')}

            Include:
            - key pay differences
            - highest and lowest-earning sectors
            - compensation risks or trends
            - macro interpretation
            - workforce implications
            """
        )
        st.markdown("### AI Summary")
        st.write(summary)
###############################################################
#  SECTION 5 — JOB POSTINGS TAB + SPS TAB
###############################################################

###############################################################
#  JOB POSTINGS TAB
###############################################################

with tab_jobs:

    st.header("Job Postings Explorer")

    ###########################################################
    # LOAD MOST RECENT JOB POSTING DATA
    ###########################################################

    df_jobs = run_sql("""
        SELECT *
        FROM curated.fact_job_posting
        ORDER BY posted_date DESC;
    """)

    if df_jobs.empty:
        st.warning("No job posting data available.")
        st.stop()

    latest_date = df_jobs["posted_date"].max()

    st.subheader(f"Latest Posting Date: **{latest_date}**")

    recent_jobs = df_jobs[df_jobs["posted_date"] >= (latest_date - pd.Timedelta(days=30))]

    ###########################################################
    # DISPLAY TABLE — MOST RECENT POSTINGS
    ###########################################################

    st.subheader("Recent Job Postings (Last 30 Days)")

    df_display = recent_jobs.copy()
    df_display["salary_min"] = df_display["salary_min"].apply(fmt_currency)
    df_display["salary_max"] = df_display["salary_max"].apply(fmt_currency)

    st.dataframe(df_display[
        ["posted_date", "employer_name", "job_title", "industry", "salary_min", "salary_max", "is_tech_role", "is_entry_level"]
    ], use_container_width=True, height=500)

    ###########################################################
    # KPI CARDS — HIRING SNAPSHOT
    ###########################################################

    st.subheader("Hiring Snapshot")

    col1, col2, col3 = st.columns(3)

    col1.metric("Total Postings (30 Days)", f"{len(recent_jobs):,}")
    col2.metric("Tech Roles", f"{recent_jobs['is_tech_role'].sum():,}")
    col3.metric("Entry-Level Roles", f"{recent_jobs['is_entry_level'].sum():,}")

    ###########################################################
    # POSTING TREND — LINE CHART
    ###########################################################

    st.subheader("Posting Trend by Industry")

    df_trend = df_jobs.copy()
    df_trend["month"] = pd.to_datetime(df_trend["posted_date"]).dt.to_period("M").dt.to_timestamp()
    df_trend = df_trend.groupby(["month", "industry"]).size().reset_index(name="postings")

    fig = px.line(
        df_trend,
        x="month",
        y="postings",
        color="industry",
        title="Monthly Posting Trend by Industry",
        markers=True
    )
    st.plotly_chart(fig, use_container_width=True)

    ###########################################################
    # JOBS TAB — ASK A QUESTION ABOUT THIS DATASET
    ###########################################################

    st.subheader("Ask a Question About Job Postings")

    jobs_q = st.text_input(
        "Ask about hiring trends, industries, tech jobs, employers, salaries…",
        placeholder="e.g., Which industries hired the most tech roles recently?",
        key="jobs_question"
    )

    if jobs_q:
        snippet = recent_jobs.head(50).to_json(orient="records")
        answer = ask_gpt(
            f"""
            User asked a question about job postings:

            QUESTION:
            {jobs_q}

            Here is the recent (last 30 days) job posting data:
            {snippet}

            Provide an accurate, executive-level answer.
            """
        )
        st.markdown("### AI Answer")
        st.write(answer)

    ###########################################################
    # JOBS TAB — SUMMARIZE DATASET WITH AI
    ###########################################################

    st.subheader("Summarize Job Posting Trends")

    if st.button("Summarize Job Postings With AI"):
        summary = ask_gpt(
            f"""
            Provide an executive-level summary of the latest Cayman job postings.

            Use ONLY this dataset:
            {recent_jobs.head(200).to_json(orient='records')}

            Include:
            - key hiring industries
            - employer activity
            - tech vs non-tech patterns
            - salary dynamics
            - entry-level opportunities
            - monthly trends
            """
        )
        st.markdown("### AI Summary")
        st.write(summary)


###############################################################
#  SPS TAB — STRATEGIC POLICY STATEMENT
###############################################################

with tab_sps:

    st.header("Strategic Policy Statement (SPS) — Workforce Insights")

    ###########################################################
    # LOAD SPS TEXT
    ###########################################################

    df_sps = run_sql("""
        SELECT *
        FROM curated.fact_sps_context
        ORDER BY page DESC;
    """)

    if df_sps.empty:
        st.warning("No SPS text available.")
        st.stop()

    ###########################################################
    # DISPLAY MOST RECENT 200 LINES OF SPS
    ###########################################################

    st.subheader("Most Recent SPS Pages")
    st.dataframe(df_sps.head(200), use_container_width=True)

    ###########################################################
    # SPS TAB — ASK A QUESTION
    ###########################################################

    st.subheader("Ask a Question About SPS Workforce Policy")

    sps_q = st.text_input(
        "Ask about policy direction, workforce strategy, education, immigration, economic development…",
        placeholder="e.g., What does the SPS say about digital skills development?",
        key="sps_question"
    )

    if sps_q:
        snippet = df_sps.head(100).to_json(orient="records")
        answer = ask_gpt(
            f"""
            The user asked a question about the Strategic Policy Statement (SPS):

            QUESTION:
            {sps_q}

            Here is the SPS text dataset:
            {snippet}

            Provide a precise, executive-level policy interpretation.
            """
        )
        st.markdown("### AI Answer")
        st.write(answer)

    ###########################################################
    # SPS TAB — SUMMARIZE DATASET
    ###########################################################

    st.subheader("Summarize SPS Workforce Direction")

    if st.button("Summarize SPS With AI"):
        summary = ask_gpt(
            f"""
            Provide an executive summary of the SPS workforce, education,
            immigration, and economic development direction.

            Use ONLY this SPS dataset:
            {df_sps.head(200).to_json(orient='records')}

            Include:
            - workforce priorities
            - education alignment
            - digital skills development
            - talent pipeline direction
            - economic growth implications
            - policy risks and opportunities
            """
        )
        st.markdown("### AI Summary")
        st.write(summary)
