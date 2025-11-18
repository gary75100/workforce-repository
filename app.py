###############################################################
#  CAYMAN WORKFORCE INTELLIGENCE ASSISTANT — FULL PRODUCTION  #
#  MODEL: GPT-4.1                                              #
#  ARCHITECTURE: HYBRID SQL + AI                               #
#  AUTHOR: ChatGPT                                              #
#  FOR: Gary Allen (NFD / Cayman Workforce)                     #
###############################################################

import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
import time
from openai import OpenAI, RateLimitError, APIError, APIConnectionError, APITimeoutError
from db_loader import ensure_database


###############################################################
#  GLOBAL CONFIG
###############################################################

st.set_page_config(
    page_title="Cayman Workforce Intelligence Assistant",
    layout="wide"
)

MODEL_NAME = "gpt-4.1"

# Global primary OpenAI client
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])


###############################################################
#  SAFE GPT WRAPPER — dual-mode client + retries
###############################################################

def ask_gpt(prompt, system="You are a Cayman labour market analyst. Provide clear, factual insights based on the data."):
    """
    Production-safe GPT caller with:
    - retry handling
    - fallback client instantiation
    - descriptive error messages
    - rate limit protection
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
            return response.choices[0].message["content"].strip()

        except RateLimitError:
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            return "The AI is currently receiving too many requests. Please try again shortly."

        except (APIError, APIConnectionError, APITimeoutError):
            # Fallback client — instantiate a new connection
            try:
                fallback_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
                response = fallback_client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=900,
                )
                return response.choices[0].message["content"].strip()
            except:
                if attempt < retries - 1:
                    time.sleep(delay)
                    delay *= 2
                    continue
                return "AI service is temporarily unavailable. Please try again."

        except Exception as e:
            return f"AI Error: {str(e)}"

    return "The AI could not respond. Please try again."


###############################################################
#  DATABASE
###############################################################

db_path = ensure_database()
conn = duckdb.connect(db_path, read_only=False)

def run_sql(sql: str) -> pd.DataFrame:
    return conn.execute(sql).df()


###############################################################
#  CURRENCY FORMATTER (CI$ ONLY)
###############################################################

def fmt(value):
    if value is None:
        return "—"
    return f"CI${value:,.0f}"


###############################################################
#  INTENT CLASSIFIER
###############################################################

INTENT_LABELS = """
- highest_tech_salary_by_year
- lowest_tech_salary_by_year
- average_tech_salary_by_year
- employer_most_tech_roles
- employer_least_tech_roles
- entry_level_tech_roles
- tech_salary_trend
- general_question
"""

def classify_intent(q: str) -> str:
    prompt = f"""
    Classify the following user question into EXACTLY one of these labels:

    {INTENT_LABELS}

    USER QUESTION:
    "{q}"

    Respond with ONLY the label. No explanation.
    """

    return ask_gpt(prompt).strip().lower()


###############################################################
#  STREAMLIT UI SETUP
###############################################################

st.title("🇰🇾 Cayman Workforce Intelligence Assistant")

tab_chat, tab_lfs, tab_wages, tab_jobs, tab_sps = st.tabs(
    ["💬 Ask Anything", "📊 LFS", "💵 Wages", "📈 Job Postings", "📘 SPS"]
)


################################################################
#  TAB 1 — ASK ANYTHING (with intent routing)
################################################################

with tab_chat:

    st.header("Ask any workforce question")

    user_q = st.text_input(
        "Your question:",
        placeholder="e.g., What employer posts the most tech roles?",
        key="chat_input"
    )

    if not user_q:
        st.stop()

    intent = classify_intent(user_q)
    st.info(f"Detected intent: **{intent}**")

    # =====================================================================
    # Guaranteed SQL-based answers (7 core questions)
    # =====================================================================

    # Helper for rendering
    def render(df, x=None, y=None, title=None):
        st.dataframe(df, use_container_width=True)
        if x and y:
            fig = px.line(df, x=x, y=y, title=title, markers=True)
            st.plotly_chart(fig, use_container_width=True)

    q = user_q.lower()

    # 1. Employer with most tech roles ------------------------------------
    if intent == "employer_most_tech_roles":
        sql = """
        SELECT employer_name, COUNT(*) AS tech_roles
        FROM curated.fact_job_posting
        WHERE is_tech_role = TRUE
        GROUP BY employer_name
        ORDER BY tech_roles DESC
        LIMIT 1;
        """
        df = run_sql(sql)
        render(df)
        st.write(ask_gpt(f"Explain why this employer appears most frequently:\n{df.to_json()}"))
        st.stop()

    # 2. Employer with least tech roles -----------------------------------
    if intent == "employer_least_tech_roles":
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
        render(df)
        st.write(ask_gpt(f"Explain why this employer has the fewest tech roles:\n{df.to_json()}"))
        st.stop()

    # 3. Entry-level tech roles -------------------------------------------
    if intent == "entry_level_tech_roles":
        sql = """
        SELECT job_title, employer_name, required_education, years_experience
        FROM curated.fact_job_posting
        WHERE is_entry_level = TRUE AND is_tech_role = TRUE
        ORDER BY posted_date DESC
        LIMIT 200;
        """
        df = run_sql(sql)
        render(df)
        st.write(ask_gpt(f"Summarize common entry-level requirements:\n{df.to_json()}"))
        st.stop()

    # 4. Highest tech salaries by year ------------------------------------
    if intent == "highest_tech_salary_by_year":
        sql = """
        SELECT EXTRACT(YEAR FROM posted_date) AS year,
               MAX(salary_max) AS highest_salary
        FROM curated.fact_job_posting
        WHERE is_tech_role = TRUE
        GROUP BY year
        ORDER BY year;
        """
        df = run_sql(sql)
        df["highest_salary"] = df["highest_salary"].apply(fmt)
        render(df, x="year", y="highest_salary", title="Highest Tech Salary by Year")
        st.write(ask_gpt(f"Explain the tech salary ceiling over time:\n{df.to_json()}"))
        st.stop()

    # 5. Lowest tech salaries by year -------------------------------------
    if intent == "lowest_tech_salary_by_year":
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
        df["lowest_salary"] = df["lowest_salary"].apply(fmt)
        render(df, x="year", y="lowest_salary", title="Lowest Tech Salary by Year")
        st.write(ask_gpt(f"Explain the lower salary bounds for tech roles:\n{df.to_json()}"))
        st.stop()

    # 6. Average tech salaries by year ------------------------------------
    if intent == "average_tech_salary_by_year":
        sql = """
        SELECT EXTRACT(YEAR FROM posted_date) AS year,
               AVG((salary_min + salary_max)/2) AS avg_salary
        FROM curated.fact_job_posting
        WHERE is_tech_role = TRUE
        GROUP BY year
        ORDER BY year;
        """
        df = run_sql(sql)
        df["avg_salary"] = df["avg_salary"].apply(fmt)
        render(df, x="year", y="avg_salary", title="Average Tech Salary by Year")
        st.write(ask_gpt(f"Explain average earnings for tech roles:\n{df.to_json()}"))
        st.stop()

    # 7. Tech salary trend -------------------------------------------------
    if intent == "tech_salary_trend":
        sql = """
        SELECT posted_date,
               (salary_min + salary_max)/2 AS salary
        FROM curated.fact_job_posting
        WHERE is_tech_role = TRUE
        ORDER BY posted_date;
        """
        df = run_sql(sql)
        df["salary"] = df["salary"].apply(fmt)
        render(df, x="posted_date", y="salary", title="Tech Salary Trend Over Time")
        st.write(ask_gpt(f"Interpret Cayman tech salary momentum:\n{df.to_json()}"))
        st.stop()

    # =====================================================================
    # GENERAL QUESTION (fallback)
    # =====================================================================

    sample = run_sql("""
        SELECT *
        FROM curated.fact_job_posting
        ORDER BY posted_date DESC
        LIMIT 50;
    """)

    ai_answer = ask_gpt(
        f"User asked: {user_q}\nHere is sample Cayman labour market data:\n{sample.to_json(orient='records')}\nAnswer clearly and factually."
    )

    st.subheader("AI Analysis")
    st.write(ai_answer)


################################################################
#  TAB 2 — LFS
################################################################

with tab_lfs:
    st.header("Labour Force Survey (LFS)")

    df = run_sql("""
        SELECT *
        FROM curated.fact_lfs_overview_status
        ORDER BY survey_date DESC
    """)
    st.dataframe(df, use_container_width=True)

    fig = px.line(df, x="survey_date", y="value", color="status", title="Labour Force Status Trend")
    st.plotly_chart(fig, use_container_width=True)

    if st.button("Summarize LFS with AI"):
        st.write(ask_gpt(f"Summarize Cayman LFS:\n{df.to_json()}"))


################################################################
#  TAB 3 — WAGES
################################################################

with tab_wages:
    st.header("Occupational Wage Survey (OWS)")

    df = run_sql("""
        SELECT *
        FROM curated.fact_wages
        WHERE category='industry' AND measure_type='basic_earnings' AND metric='mean'
        ORDER BY survey_date DESC
    """)

    df["value"] = df["value"].apply(fmt)

    st.dataframe(df, use_container_width=True)
    fig = px.bar(df, x="subcategory", y="value", title="Mean Monthly Earnings by Industry")
    fig.update_layout(xaxis_tickangle=45)
    st.plotly_chart(fig, use_container_width=True)

    if st.button("Summarize Wage Patterns"):
        st.write(ask_gpt(f"Summarize Cayman wage levels:\n{df.to_json()}"))


################################################################
#  TAB 4 — JOB POSTINGS EXPLORER
################################################################

with tab_jobs:

    st.header("Job Postings Explorer")

    df = run_sql("""
        SELECT *
        FROM curated.fact_job_posting
        ORDER BY posted_date DESC
    """)

    # Filters
    industries = ["All"] + sorted(df["industry"].dropna().unique().tolist())
    employers = ["All"] + sorted(df["employer_name"].dropna().unique().tolist())

    c1, c2, c3 = st.columns(3)

    f_industry = c1.selectbox("Industry", industries)
    f_employer = c2.selectbox("Employer", employers)
    date_range = c3.date_input("Date Range", [df["posted_date"].min(), df["posted_date"].max()])

    filtered = df.copy()
    filtered = filtered[
        (filtered["posted_date"] >= pd.to_datetime(date_range[0])) &
        (filtered["posted_date"] <= pd.to_datetime(date_range[1]))
    ]

    if f_industry != "All":
        filtered = filtered[filtered["industry"] == f_industry]

    if f_employer != "All":
        filtered = filtered[filtered["employer_name"] == f_employer]

    # Table
    show_df = filtered.copy()
    show_df["salary_min"] = show_df["salary_min"].apply(fmt)
    show_df["salary_max"] = show_df["salary_max"].apply(fmt)
    st.dataframe(show_df, use_container_width=True, height=500)

    # Trend
    st.subheader("Posting Trend")

    filtered["month"] = pd.to_datetime(filtered["posted_date"]).dt.to_period("M").dt.to_timestamp()

    trend = filtered.groupby(["month", "industry"]).size().reset_index(name="postings")

    st.plotly_chart(
        px.line(trend, x="month", y="postings", color="industry", markers=True),
        use_container_width=True
    )

    # Metrics (last 6 months)
    st.subheader("Quick Insights")

    six_months_ago = pd.to_datetime("today") - pd.Timedelta(days=180)
    recent = filtered[filtered["posted_date"] >= six_months_ago]

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Postings", len(recent))
    m2.metric("Tech Roles", int(recent["is_tech_role"].sum()))
    m3.metric("Entry-Level Roles", int(recent["is_entry_level"].sum()))

    # AI Summary
    if st.button("Summarize This Dataset"):
        st.write(ask_gpt(f"Summarize patterns in Cayman job postings:\n{show_df.head(50).to_json()}"))


################################################################
#  TAB 5 — SPS
################################################################

with tab_sps:
    st.header("Strategic Policy Statement (SPS)")

    df = run_sql("""
        SELECT *
        FROM curated.fact_sps_context
        ORDER BY page DESC
    """)

    st.dataframe(df, use_container_width=True)

    if st.button("Summarize SPS Direction"):
        st.write(ask_gpt(f"Summarize major SPS themes related to workforce:\n{df.to_json()}"))

