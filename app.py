import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
from openai import OpenAI
from db_loader import ensure_database

# ============================================================
#   CONFIG
# ============================================================
st.set_page_config(
    page_title="Cayman Workforce Intelligence Assistant",
    layout="wide"
)

MODEL_NAME = "gpt-4o"
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ============================================================
#   DATABASE
# ============================================================
db_path = ensure_database()
conn = duckdb.connect(db_path, read_only=False)

def run_sql(sql: str) -> pd.DataFrame:
    return conn.execute(sql).df()

# ============================================================
#   GPT HELPER
# ============================================================
def ask_gpt(prompt, system="You are a Cayman workforce analyst."):
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=900,
    )
    return resp.choices[0].message.content.strip()

# ============================================================
#   UI: PAGE TITLE + TABS
# ============================================================
st.title("🇰🇾 Cayman Workforce Intelligence Assistant")

tab_chat, tab_lfs, tab_wages, tab_jobs, tab_policy = st.tabs(
    ["💬 Ask Anything", "📊 LFS", "💵 Wages", "📈 Job Postings", "📘 SPS"]
)
# ============================================================
# GLOBAL CURRENCY SELECTOR
# ============================================================
currency = st.selectbox("Currency:", ["CI$", "US$"], index=0)

def convert(value):
    if currency == "CI$":
        return value
    elif currency == "US$":
        return value * 1.20   # Standard Cayman-to-US conversion unless you give me another rate
    return value

def fmt(value):
    if value is None or pd.isna(value):
        return ""
    if currency == "CI$":
        return f"CI${value:,.2f}"
    else:
        return f"US${convert(value):,.2f}"

# ============================================================
#   TAB 1 — ASK ANYTHING (7 GUARANTEED ANSWERS + FREEFORM GPT)
# ============================================================
with tab_chat:

    st.header("Ask any workforce question")

    # Chat history for multi-turn conversation
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    user_q = st.text_input(
        "Your question:",
        placeholder="e.g., What employer posts the most tech roles?",
        key="chat_input"
    )

    if user_q:
        q = user_q.lower()

        # =======================================================
        # ROUTED ANSWERS (7 guaranteed client questions)
        # =======================================================

        # 1. Employer posting the most tech roles
        if "most" in q and "tech" in q and "employer" in q:
            df = run_sql("""
                SELECT employer_name, COUNT(*) AS tech_roles
                FROM curated.fact_job_posting
                WHERE is_tech_role = TRUE
                GROUP BY employer_name
                ORDER BY tech_roles DESC
                LIMIT 10;
            """)
            st.subheader("Employers Posting the Most Tech Roles")
            st.dataframe(df, use_container_width=True)

        # 2. Employer posting the least tech roles
        elif "least" in q and "tech" in q and "employer" in q:
            df = run_sql("""
                SELECT employer_name, COUNT(*) AS tech_roles
                FROM curated.fact_job_posting
                WHERE is_tech_role = TRUE
                GROUP BY employer_name
                ORDER BY tech_roles ASC
                LIMIT 10;
            """)
            st.subheader("Employers Posting the Fewest Tech Roles")
            st.dataframe(df, use_container_width=True)

        # 3. Entry-level tech roles + common requirements
        elif "entry" in q and "tech" in q:
            st.subheader("Entry-Level Tech Roles")
            df_count = run_sql("""
                SELECT COUNT(*) AS entry_level_tech_roles
                FROM curated.fact_job_posting
                WHERE is_tech_role = TRUE AND is_entry_level = TRUE;
            """)
            st.dataframe(df_count)

            st.subheader("Most Common Requirements")
            df_req = run_sql("""
                SELECT years_experience, COUNT(*) AS freq
                FROM curated.fact_job_posting
                WHERE is_tech_role = TRUE AND is_entry_level = TRUE
                GROUP BY years_experience
                ORDER BY freq DESC
                LIMIT 10;
            """)
            st.dataframe(df_req)

        # 4. Highest tech salary YoY (2020–2025)
        elif "highest" in q and "salary" in q and "tech" in q:
            df = run_sql("""
                SELECT YEAR(posted_date) AS year,
                       MAX(salary_max) AS highest_salary
                FROM curated.fact_job_posting
                WHERE is_tech_role = TRUE
                  AND posted_date >= '2020-01-01'
                GROUP BY year
                ORDER BY year;
            """)
            st.subheader("Highest Tech Salaries by Year")
            st.dataframe(df)
            st.plotly_chart(px.line(df, x="year", y="highest_salary", markers=True))

        # 5. Average tech salary YoY
        elif "average" in q and "salary" in q and "tech" in q:
            df = run_sql("""
                SELECT YEAR(posted_date) AS year,
                       AVG((salary_min + salary_max)/2) AS avg_salary
                FROM curated.fact_job_posting
                WHERE is_tech_role = TRUE
                  AND posted_date >= '2020-01-01'
                GROUP BY year
                ORDER BY year;
            """)
            st.subheader("Average Tech Salaries by Year")
            st.dataframe(df)
            st.plotly_chart(px.line(df, x="year", y="avg_salary", markers=True))

        # 6. Lowest tech salary YoY
        elif "lowest" in q and "salary" in q and "tech" in q:
            df = run_sql("""
                SELECT YEAR(posted_date) AS year,
                       MIN(salary_min) AS lowest_salary
                FROM curated.fact_job_posting
                WHERE is_tech_role = TRUE
                  AND posted_date >= '2020-01-01'
                GROUP BY year
                ORDER BY year;
            """)
            st.subheader("Lowest Tech Salaries by Year")
            st.dataframe(df)
            st.plotly_chart(px.line(df, x="year", y="lowest_salary", markers=True))

        # ======================
        # FALLBACK — FREEFORM AI
        # ======================
        else:
            st.subheader("AI Analysis")

            sample_df = run_sql("""
                SELECT *
                FROM curated.fact_job_posting
                ORDER BY posted_date DESC
                LIMIT 50
            """)

            sample_context = sample_df.to_markdown(index=False)

            prompt = f"""
User question:
{user_q}

Here is a recent sample of Cayman job posting data:
{sample_context}

Answer the user's question directly, using:
- Cayman labour market context
- industry patterns
- job posting trends
- SPS policy alignment (if applicable)
"""

            ai_answer = ask_gpt(prompt)
            st.write(ai_answer)

        # Save conversation
        st.session_state.chat_history.append(("You", user_q))
        st.session_state.chat_history.append(("Assistant", ai_answer if 'ai_answer' in locals() else ""))

        # Show conversation
        st.subheader("Conversation")
        for role, msg in st.session_state.chat_history:
            st.markdown(f"**{role}:** {msg}")
# ============================================================
#   TAB 2 — LFS (Labour Force Survey)
# ============================================================
with tab_lfs:

    st.header("Labour Force Survey (LFS)")

    df = run_sql("""
        SELECT *
        FROM curated.fact_lfs_overview_status
        ORDER BY survey_date DESC
    """)

    st.subheader("LFS Overview (Newest First)")
    st.dataframe(df, use_container_width=True)

    # Trend chart
    fig = px.line(
        df,
        x="survey_date",
        y="value",
        color="status",
        title="LFS Labour Status Trend"
    )
    st.plotly_chart(fig, use_container_width=True)

    # AI Summary
    if st.button("Summarize LFS with AI"):
        snippet = df.head(50).to_markdown(index=False)
        prompt = f"""
Summarize key trends in the latest Cayman Labour Force Survey:
{snippet}

Highlight:
- labour force participation
- employment vs unemployment
- Caymanian vs non-Caymanian differences
"""
        st.write(ask_gpt(prompt))


# ============================================================
#   TAB 3 — WAGES (Occupational Wage Survey)
# ============================================================
with tab_wages:

    st.header("Occupational Wage Survey (OWS)")

    df = run_sql("""
        SELECT *
        FROM curated.fact_wages
        ORDER BY survey_date DESC
        LIMIT 500
    """)

    st.subheader("Wage Records (Newest First)")
    df["value_fmt"] = df["value"].apply(fmt)
    st.dataframe(df[["subcategory", "value_fmt"]])

    # Chart: mean earnings by industry if available
    if "subcategory" in df.columns and "value" in df.columns:
        fig = px.bar(
            df,
            x="subcategory",
            y=df["value"].apply(convert),
            color="category",
            title="Wage Levels by Industry / Category"
        )
        fig.update_layout(xaxis_tickangle=45)
        st.plotly_chart(fig, use_container_width=True)

    # --- AI SUMMARY ---------------------------------------------------
    if st.button("Summarize Wages with AI"):
        snippet = df.head(50).to_markdown(index=False)
        prompt = f"""
Provide a clear executive summary of Cayman wage levels based on this dataset:

{snippet}

Explain:
- which industries pay the most and least
- year-over-year changes
- tech vs non-tech earnings gaps (if visible)
- any anomalies or notable patterns
"""
        st.write(ask_gpt(prompt))

# ============================================================
#   TAB 4 — JOB POSTINGS EXPLORER
# ============================================================
with tab_jobs:

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
        ORDER BY posted_date DESC
    """)

    # Filters
    industries = sorted(df["industry"].dropna().unique())
    selected_industry = st.selectbox("Industry", ["All"] + industries)

    filtered_df = df.copy()
    if selected_industry != "All":
        filtered_df = filtered_df[filtered["industry"] == selected_industry]

    st.subheader("Daily Job Postings (Newest First)")
    
    # Apply formatting ONLY to salary columns
    show_df = filtered_df.copy()
    show_df["salary_min"] = show_df["salary_min"].apply(fmt)
    show_df["salary_max"] = show_df["salary_max"].apply(fmt)
    
    st.dataframe(show_df, use_container_width=True, height=500)
# --- QUICK INSIGHTS -----------------------------------------------
st.subheader("Quick Insights")

colA, colB, colC = st.columns(3)

colA.metric("Total Postings", len(filtered_df))
colB.metric("Tech Roles", filtered_df['is_tech_role'].sum())
colC.metric("Entry Level Roles", filtered_df['is_entry_level'].sum())

# Salary insights (converted)
if len(filtered_df) > 0:
    avg_min = filtered_df["salary_min"].mean()
    avg_max = filtered_df["salary_max"].mean()

    st.metric("Avg Minimum Salary", fmt(avg_min))
    st.metric("Avg Maximum Salary", fmt(avg_max))


    # Trend chart
    st.subheader("Posting Trend")
    filtered["month"] = pd.to_datetime(filtered["posted_date"]).dt.to_period("M").dt.to_timestamp()
    trend = filtered.groupby(["month", "industry"]).size().reset_index(name="postings")

    st.plotly_chart(
        px.line(trend, x="month", y="postings", color="industry", markers=True),
        use_container_width=True
    )

    # Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Total", len(filtered))
    col2.metric("Tech Roles", int(filtered["is_tech_role"].sum()))
    col3.metric("Entry-Level", int(filtered["is_entry_level"].sum()))

    if st.button("Summarize Job Postings with AI"):
        snippet = filtered.head(50).to_markdown(index=False)
        st.write(
            ask_gpt(f"Summarize Cayman job posting activity:\n{snippet}")
        )


# ============================================================
#   TAB 5 — SPS (Strategic Policy Statement)
# ============================================================
with tab_policy:

    st.header("Strategic Policy Statement (SPS)")

    df = run_sql("""
        SELECT *
        FROM curated.fact_sps_context
        ORDER BY page ASC
    """)

    st.subheader("SPS Context Blocks")
    st.dataframe(df, use_container_width=True)

    if st.button("Summarize SPS Workforce Direction with AI"):
        snippet = df.head(50).to_markdown(index=False)
        prompt = f"""
Provide a clear executive-level summary of SPS workforce, education, immigration,
economic, and social development direction, using this data:

{snippet}
"""
        st.write(ask_gpt(prompt))
