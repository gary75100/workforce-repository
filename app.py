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
#   TOPIC DETECTION
# ============================================================
TOPIC_KEYWORDS = {
    "job_postings": ["job", "posting", "vacanc", "recruit", "opening"],
    "labour_force": ["labour", "labor", "employment", "participation", "unemployment"],
    "wages": ["wage", "salary", "earnings", "compensation"],
    "industry": ["industry", "sector"],
    "occupation": ["occupation", "role", "job title"],
    "policy": ["sps", "policy", "strategic", "broad outcome"],
}

def detect_topic(q: str) -> str:
    q = q.lower()
    for topic, kws in TOPIC_KEYWORDS.items():
        if any(k in q for k in kws):
            return topic
    return "general"


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
#   STREAMLIT UI
# ============================================================
st.title("🇰🇾 Cayman Workforce Intelligence Assistant")

tab_chat, tab_lfs, tab_wages, tab_jobs, tab_policy = st.tabs(
    ["💬 Ask Anything", "📊 LFS", "💵 Wages", "📈 Job Postings", "📘 SPS"]
)


# ============================================================
#   CHAT TAB — WITH HARD-WIRED JOB POSTING CHARTS
# ============================================================

with tab_chat:
    st.header("Ask any workforce question")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    user_q = st.text_input(
        "Your question:",
        placeholder="e.g., Plot job postings by industry over the last 5 years",
        key="chat_input"
    )

    if user_q:
        q_lower = user_q.lower()
        topic = detect_topic(user_q)
        st.info(f"Detected topic: **{topic}**")

        # ----------------------------------------------------
        # HARD-WIRED JOB POSTING CHART LOGIC (ALWAYS WORKS)
        # ----------------------------------------------------
        job_posting_chart = (
            "job posting" in q_lower
            and "industry" in q_lower
            and any(w in q_lower for w in ["plot", "chart", "graph", "visualize", "trend"])
        )

        if job_posting_chart:
            sql = """
                SELECT
                    date_trunc('year', posted_date) AS year,
                    industry,
                    COUNT(*) AS postings
                FROM curated.fact_job_posting
                WHERE posted_date IS NOT NULL
                GROUP BY year, industry
                ORDER BY year DESC, industry
            """

            df = run_sql(sql)

            st.subheader("Job Postings by Industry Over Time (Newest First)")
            st.dataframe(df)

            fig = px.line(
                df,
                x="year",
                y="postings",
                color="industry",
                title="Job Postings by Industry — Yearly Trend"
            )
            st.plotly_chart(fig, use_container_width=True)

            # GPT EXPLANATION
            snippet = df.head(100).to_json(orient="records")
            prompt = f"""
You are a Cayman labour market analyst.

Here is job posting data:
{snippet}

Explain how job postings have changed over time across industries.
Highlight which industries are growing or declining.
"""
            explanation = ask_gpt(prompt)
            st.subheader("AI Explanation")
            st.write(explanation)

            st.session_state.chat_history.append(("You", user_q))
            st.session_state.chat_history.append(("Assistant", explanation))

        # ----------------------------------------------------
        # NON-CHART QUESTIONS — GPT SUMMARY / ANALYSIS
        # ----------------------------------------------------
        else:
            try:
                sample_df = run_sql("SELECT * FROM curated.fact_job_posting ORDER BY posted_date DESC LIMIT 50")
                sample_json = sample_df.to_json(orient="records")
            except:
                sample_json = ""

            prompt = f"""
User question:
{user_q}

Here is recent job posting sample data:
{sample_json}

Provide an insightful answer based on Cayman labour data and SPS policy.
"""
            response = ask_gpt(prompt)
            st.session_state.chat_history.append(("You", user_q))
            st.session_state.chat_history.append(("Assistant", response))
            st.success("Response generated.")

    st.subheader("Conversation")
    for role, msg in st.session_state.chat_history:
        st.markdown(f"**{role}:** {msg}")


# ============================================================
#   LFS TAB — NEWEST FIRST & AI SUMMARY
# ============================================================

with tab_lfs:
    st.header("Labour Force Survey (LFS)")

    df = run_sql("""
        SELECT *
        FROM curated.fact_lfs_overview_status
        ORDER BY survey_date DESC
    """)
    st.subheader("LFS Overview (Newest First)")
    st.dataframe(df)

    fig = px.line(
        df,
        x="survey_date",
        y="value",
        color="status",
        title="Labour Force Status Trend"
    )
    st.plotly_chart(fig, use_container_width=True)

    if st.button("Summarize LFS with AI"):
        snippet = df.to_json(orient="records")
        prompt = f"""
Summarize the latest LFS labour market insights from this dataset:
{snippet}

Highlight employment, unemployment, and participation patterns.
"""
        st.write(ask_gpt(prompt))


# ============================================================
#   WAGES TAB — NEWEST FIRST & AI SUMMARY
# ============================================================

with tab_wages:
    st.header("Occupational Wage Survey (OWS)")

    df = run_sql("""
        SELECT *
        FROM curated.fact_wages
        WHERE category = 'industry'
          AND measure_type = 'basic_earnings'
          AND metric = 'mean'
        ORDER BY survey_date DESC
    """)
    st.subheader("Mean Earnings by Industry (Newest First)")
    st.dataframe(df)

    fig = px.bar(
        df,
        x="subcategory",
        y="value",
        title="Mean Monthly Basic Earnings by Industry"
    )
    fig.update_layout(xaxis_tickangle=45)
    st.plotly_chart(fig, use_container_width=True)

    if st.button("Summarize wages with AI"):
        snippet = df.to_json(orient="records")
        prompt = f"""
Provide an AI summary of Cayman wage levels and differences by industry.
Data:
{snippet}
"""
        st.write(ask_gpt(prompt))


# ============================================================
#   JOB POSTINGS TAB — NEWEST FIRST & AI SUMMARY
# ============================================================

with tab_jobs:
    st.header("Job Postings")

    df = run_sql("""
        SELECT posted_date, industry, COUNT(*) AS postings
        FROM curated.fact_job_posting
        WHERE posted_date IS NOT NULL
        GROUP BY posted_date, industry
        ORDER BY posted_date DESC
    """)
    st.subheader("Daily Job Postings by Industry (Newest First)")
    st.dataframe(df)

    fig = px.line(
        df,
        x="posted_date",
        y="postings",
        color="industry",
        title="Job Postings Over Time"
    )
    st.plotly_chart(fig, use_container_width=True)

    if st.button("Summarize job postings with AI"):
        snippet = df.head(200).to_json(orient="records")
        prompt = f"""
Summarize Cayman job posting activity using this dataset:
{snippet}
"""
        st.write(ask_gpt(prompt))


# ============================================================
#   SPS TAB — AI SUMMARIZATION
# ============================================================

with tab_policy:
    st.header("Strategic Policy Statement (SPS)")

    df = run_sql("""
        SELECT *
        FROM curated.fact_sps_context
        ORDER BY page DESC
        LIMIT 200
    """)
    st.subheader("SPS Text Blocks (Newest First)")
    st.dataframe(df)

    if st.button("Summarize SPS workforce direction"):
        snippet = df.to_json(orient="records")
        prompt = f"""
Summarize the SPS workforce, education, immigration, and economic development direction.
Use this dataset:
{snippet}
Write an executive-level brief.
"""
        st.write(ask_gpt(prompt))

