import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
import json
import traceback

from openai import OpenAI
from db_loader import ensure_database

# ============================================================
#   CONFIG
# ============================================================
st.set_page_config(page_title="Cayman Workforce Intelligence Assistant", layout="wide")
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
#   GPT HELPERS
# ============================================================
def ask_gpt(prompt: str, system="You are a Cayman workforce analyst."):
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1000,
    )
    return resp.choices[0].message.content.strip()

def ask_gpt_for_chart(user_query: str, sample_data=""):
    prompt = f"""
You are an analytics copilot for the Cayman Government Workforce App.

User question: {user_query}

Return ONLY JSON with keys: sql, chart_code, explanation.

RULES:
- SQL must be SELECT only.
- For job posting questions use ONLY: curated.fact_job_posting
- Valid fields: posted_date, industry, occupation, employer_name,
                salary_min, salary_max, annual_salary_mean, work_type
- NEVER use worc_job_postings_* or *_historical (DO NOT EXIST).
- Use Plotly Express with df already loaded.
- Return ONLY raw JSON, no markdown.

Sample data:
{sample_data}
"""

    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "system", "content": "Strict JSON only."},
                  {"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1200,
    )

    txt = resp.choices[0].message.content.strip()
    try:
        return json.loads(txt)
    except Exception:
        return {"error": "invalid_json", "raw": txt, "trace": traceback.format_exc()}

# ============================================================
#   STREAMLIT UI
# ============================================================
st.title("🇰🇾 Cayman Workforce Intelligence Assistant")

tab_chat, tab_lfs, tab_wages, tab_jobs, tab_policy = st.tabs(
    ["💬 Ask Anything", "📊 LFS", "💵 Wages", "📈 Job Postings", "📘 SPS"]
)
# ============================================================
#   CHAT TAB
# ============================================================

with tab_chat:
    st.header("Ask any workforce question")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    user_q = st.text_input(
        "Your question:",
        placeholder="e.g., Plot job postings by industry over the last 5 years",
        key="chat_input_box"
    )

    if user_q:
        topic = detect_topic(user_q)
        st.info(f"Detected topic: **{topic}**")

        # ----------------------------------------------------
        #   AUTO-CHART MODE
        # ----------------------------------------------------
        if any(w in user_q.lower() for w in ["plot", "chart", "graph", "visualize"]):

            # Load sample schema for GPT
            try:
                df_sample = run_sql("SELECT * FROM curated.fact_job_posting LIMIT 50")
                sample_json = df_sample.to_json(orient="records")
            except Exception:
                sample_json = ""

            result = ask_gpt_for_chart(user_q, sample_json)

            # Correct JSON error detection
            if isinstance(result, dict) and "error" in result:
                st.error("AI could not generate valid JSON for the chart.")
                st.code(result.get("raw", "No raw output."))
            else:
                sql = result.get("sql", "")
                chart_code = result.get("chart_code", "")
                explanation = result.get("explanation", "")

                st.subheader("Generated SQL")
                st.code(sql, language="sql")

                # Run SQL
                try:
                    df = run_sql(sql)
                    st.subheader("Data")
                    st.dataframe(df)
                except Exception as e:
                    st.error(f"SQL execution failed: {e}")
                    st.code(sql)
                    st.session_state.chat_history.append(("Assistant", "SQL failed."))
                    st.stop()

                # Execute chart code
                try:
                    env = {"px": px, "df": df}
                    exec(chart_code, {}, env)
                    fig = env["fig"]

                    st.subheader("Chart")
                    st.plotly_chart(fig, use_container_width=True)

                    st.subheader("Explanation")
                    st.write(explanation)

                    st.session_state.chat_history.append(("Assistant", explanation))

                except Exception as e:
                    st.error(f"Chart execution failed: {e}")
                    st.code(chart_code)

        # ----------------------------------------------------
        #   NON-CHART QUESTIONS
        # ----------------------------------------------------
        else:
            try:
                df_sample = run_sql("SELECT * FROM curated.fact_job_posting LIMIT 50")
                sample_json = df_sample.to_json(orient="records")
            except:
                sample_json = ""

            prompt = f"""
User question:
{user_q}

Relevant job posting sample data (JSON):
{sample_json}

Provide a clear, analytical answer referencing the Cayman labour market.
Include SPS policy alignment when relevant.
"""
            answer = ask_gpt(prompt)
            st.session_state.chat_history.append(("Assistant", answer))
            st.success("Response generated.")

    st.subheader("Conversation")
    for role, msg in st.session_state.chat_history:
        st.markdown(f"**{role}:** {msg}")


# ============================================================
#   LFS TAB
# ============================================================

with tab_lfs:
    st.header("Labour Force Survey (LFS)")

    df_lfs = run_sql("SELECT * FROM curated.fact_lfs_overview_status")
    st.subheader("Overview by Status")
    st.dataframe(df_lfs)

    if not df_lfs.empty:
        fig = px.line(
            df_lfs, x="survey_date", y="value",
            color="status", title="LFS Overview by Status"
        )
        st.plotly_chart(fig, use_container_width=True)


# ============================================================
#   WAGES TAB
# ============================================================

with tab_wages:
    st.header("Occupational Wage Survey (OWS)")

    df_wages = run_sql("""
        SELECT *
        FROM curated.fact_wages
        WHERE category = 'industry'
          AND measure_type = 'basic_earnings'
          AND metric = 'mean'
    """)
    st.subheader("Mean Wages by Industry")
    st.dataframe(df_wages)

    if not df_wages.empty:
        fig = px.bar(
            df_wages, x="subcategory", y="value",
            title="Mean Monthly Basic Earnings by Industry (CI$)"
        )
        fig.update_layout(xaxis_tickangle=45)
        st.plotly_chart(fig, use_container_width=True)


# ============================================================
#   JOB POSTINGS TAB
# ============================================================

with tab_jobs:
    st.header("Job Posting Trends")

    df_jobs = run_sql("""
        SELECT posted_date, industry, COUNT(*) AS postings
        FROM curated.fact_job_posting
        WHERE posted_date IS NOT NULL
        GROUP BY posted_date, industry
        ORDER BY posted_date
    """)

    st.subheader("Job Postings by Industry Over Time")
    st.dataframe(df_jobs)

    if not df_jobs.empty:
        fig = px.line(
            df_jobs, x="posted_date", y="postings",
            color="industry", title="Industry Job Posting Trends"
        )
        st.plotly_chart(fig, use_container_width=True)


# ============================================================
#   SPS TAB
# ============================================================

with tab_policy:
    st.header("Strategic Policy Statement (SPS)")

    df_sps = run_sql("SELECT * FROM curated.fact_sps_context LIMIT 200")
    st.subheader("SPS Excerpts")
    st.dataframe(df_sps)

    if st.button("Summarize SPS Workforce Direction"):
        sps_json = df_sps.to_json(orient="records")
        prompt = f"""
Here are SPS excerpts (JSON):
{sps_json}

Provide an executive-level summary of the workforce, education,
and labour-market direction in the SPS.
Include implications for policy and workforce planning.
"""
        answer = ask_gpt(prompt)
        st.subheader("AI SPS Summary")
        st.write(answer)
