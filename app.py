import streamlit as st
import pandas as pd
import plotly.express as px
import duckdb

from db_loader import ensure_database
from openai import OpenAI

# ---------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------
st.set_page_config(
    page_title="Cayman Workforce Intelligence",
    layout="wide"
)

# ---------------------------------------------------------
# DB CONNECTION
# ---------------------------------------------------------
DB_PATH = ensure_database()
conn = duckdb.connect(DB_PATH, read_only=True)

def run_sql(query: str) -> pd.DataFrame:
    try:
        return conn.execute(query).df()
    except Exception as e:
        st.error(f"SQL Error: {e}")
        return pd.DataFrame()

# ---------------------------------------------------------
# OPENAI SETUP
# ---------------------------------------------------------
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

def ask_gpt(prompt: str):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500
        )
        return response.choices[0].message["content"]
    except Exception as e:
        return f"AI Error: {e}"

# ---------------------------------------------------------
# TOP TABS
# ---------------------------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Ask Anything", "LFS", "Wages", "Job Postings", "SPS"]
)

# =========================================================
# TAB 1 — ASK ANYTHING
# =========================================================
with tab1:

    st.header("Ask the Workforce Database Anything")
    user_q = st.text_input("Enter your question:")

    if user_q:
        q = user_q.lower()

        # ----------------------------
        # ROUTED ANSWERS (7 QUESTIONS)
        # ----------------------------

        # 1. Employer with most tech roles
        if "most" in q and "tech" in q and "employer" in q:
            st.subheader("Employers Posting the Most Tech Roles")
            df = run_sql("""
                SELECT employer_name, COUNT(*) AS tech_roles
                FROM curated.fact_job_posting
                WHERE is_tech_role = TRUE
                GROUP BY employer_name
                ORDER BY tech_roles DESC
                LIMIT 10;
            """)
            st.dataframe(df)

        # 2. Employer with least tech roles
        elif "least" in q and "tech" in q and "employer" in q:
            st.subheader("Employers Posting the Fewest Tech Roles")
            df = run_sql("""
                SELECT employer_name, COUNT(*) AS tech_roles
                FROM curated.fact_job_posting
                WHERE is_tech_role = TRUE
                GROUP BY employer_name
                ORDER BY tech_roles ASC
                LIMIT 10;
            """)
            st.dataframe(df)

        # 3. Entry-level tech roles + common requirements
        elif "entry" in q and "tech" in q:
            st.subheader("Entry-Level Tech Roles")
            count_df = run_sql("""
                SELECT COUNT(*) AS entry_level_tech_roles
                FROM curated.fact_job_posting
                WHERE is_tech_role = TRUE AND is_entry_level = TRUE;
            """)
            st.dataframe(count_df)

            st.subheader("Most Common Requirements")
            req_df = run_sql("""
                SELECT years_experience, COUNT(*) AS frequency
                FROM curated.fact_job_posting
                WHERE is_tech_role = TRUE AND is_entry_level = TRUE
                GROUP BY years_experience
                ORDER BY frequency DESC
                LIMIT 10;
            """)
            st.dataframe(req_df)

        # 4. Highest salary YoY (tech)
        elif "highest" in q and "salary" in q and "tech" in q:
            st.subheader("Highest Tech Salaries (Year by Year)")
            df = run_sql("""
                SELECT YEAR(posted_date) AS year,
                       MAX(salary_max) AS highest_salary
                FROM curated.fact_job_posting
                WHERE is_tech_role = TRUE
                GROUP BY year
                ORDER BY year;
            """)
            st.dataframe(df)
            st.plotly_chart(px.line(df, x="year", y="highest_salary", markers=True))

        # 5. Average salary YoY (tech)
        elif "average" in q and "salary" in q and "tech" in q:
            st.subheader("Average Tech Salaries (Year by Year)")
            df = run_sql("""
                SELECT YEAR(posted_date) AS year,
                       AVG((salary_min + salary_max) / 2) AS avg_salary
                FROM curated.fact_job_posting
                WHERE is_tech_role = TRUE
                GROUP BY year
                ORDER BY year;
            """)
            st.dataframe(df)
            st.plotly_chart(px.line(df, x="year", y="avg_salary", markers=True))

        # 6. Lowest salary YoY (tech)
        elif "lowest" in q and "salary" in q and "tech" in q:
            st.subheader("Lowest Tech Salaries (Year by Year)")
            df = run_sql("""
                SELECT YEAR(posted_date) AS year,
                       MIN(salary_min) AS lowest_salary
                FROM curated.fact_job_posting
                WHERE is_tech_role = TRUE
                GROUP_BY year
                ORDER BY year;
            """)
            st.dataframe(df)
            st.plotly_chart(px.line(df, x="year", y="lowest_salary", markers=True))

        # 7. Fallback: AI-powered general answer
        else:
            st.subheader("AI Response")
            context_sample = run_sql("""
                SELECT *
                FROM curated.fact_job_posting
                ORDER BY posted_date DESC
                LIMIT 50;
            """).to_markdown(index=False)

            prompt = f"""
You are a Cayman workforce intelligence analyst.
User question: {user_q}

Here is a sample of job posting data for context:
{context_sample}

Answer the user's question directly and concisely.
"""
            st.write(ask_gpt(prompt))


# =========================================================
# TAB 2 — LFS
# =========================================================
with tab2:

    st.header("Labour Force Survey (LFS)")

    df = run_sql("""
        SELECT *
        FROM curated.fact_lfs_overview_status
        ORDER BY survey_date DESC;
    """)

    st.subheader("LFS Status Overview")
    st.dataframe(df, use_container_width=True)

    st.subheader("AI Summary")
    sample = df.head(50).to_markdown(index=False)
    st.write(ask_gpt(f"Provide a clear summary of this LFS data:\n\n{sample}"))


# =========================================================
# TAB 3 — WAGES
# =========================================================
with tab3:

    st.header("Wage Data (Occupational Wage Survey)")

    df = run_sql("""
        SELECT *
        FROM curated.fact_wages
        ORDER BY survey_date DESC;
    """)

    st.subheader("Wage Table")
    st.dataframe(df, use_container_width=True)

    st.subheader("AI Summary")
    st.write(ask_gpt(f"Summarize key wage patterns:\n\n{df.head(50).to_markdown(index=False)}"))


# =========================================================
# TAB 4 — JOB POSTINGS EXPLORER
# =========================================================
with tab4:

    st.header("Job Postings Explorer")

    df = run_sql("""
        SELECT 
            posted_date,
            industry,
            employer_name,
            job_title,
            salary_min,
            salary_max,
            is_tech_role,
            is_entry_level
        FROM curated.fact_job_posting
        ORDER BY posted_date DESC;
    """)

    industries = sorted(df['industry'].dropna().unique())
    selected_industry = st.selectbox("Industry", ["All"] + industries)

    filtered = df.copy()
    if selected_industry != "All":
        filtered = filtered[filtered["industry"] == selected_industry]

    st.subheader("Job Postings")
    st.dataframe(filtered, use_container_width=True, height=500)

    st.subheader("Posting Trend")
    filtered["month"] = pd.to_datetime(filtered["posted_date"]).dt.to_period("M").dt.to_timestamp()
    trend = filtered.groupby(["month", "industry"]).size().reset_index(name="postings")

    st.plotly_chart(px.line(trend, x="month", y="postings", color="industry", markers=True))

    col1, col2, col3 = st.columns(3)
    col1.metric("Total", len(filtered))
    col2.metric("Tech Roles", int(filtered["is_tech_role"].sum()))
    col3.metric("Entry-Level", int(filtered["is_entry_level"].sum()))


# =========================================================
# TAB 5 — SPS
# =========================================================
with tab5:

    st.header("Strategic Policy Statement (SPS)")

    df = run_sql("SELECT * FROM curated.fact_sps_context;")
    st.dataframe(df, use_container_width=True)

    st.subheader("AI Summary")
    st.write(ask_gpt(f"Summarize this Strategic Policy Statement:\n\n{df.head(50).to_markdown(index=False)}"))
