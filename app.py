import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
import json
import traceback

# NEW OpenAI API
from openai import OpenAI

# DB loader for GitHub Release download
from db_loader import ensure_database


# ============================================================
#   CONFIG
# ============================================================

st.set_page_config(
    page_title="Cayman Workforce Intelligence Assistant",
    layout="wide",
)

MODEL_NAME = "gpt-4o"
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])


# ============================================================
#   DATABASE CONNECTION
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
#   GPT FUNCTIONS
# ============================================================

def ask_gpt(prompt: str, system="You are a Cayman workforce analyst."):
    """Generic GPT call."""
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=1000,
    )
    return resp.choices[0].message.content.strip()


def ask_gpt_for_chart(user_query: str, sample_data=""):
    """
    GPT chart mode:
    Returns JSON:
    {
      "sql": "...",
      "chart_code": "fig = px.line(df, ...)",
      "explanation": "..."
    }
    """
    prompt = f"""
You are an analytics copilot for the Cayman Islands Government Workforce Intelligence Application.

User question:
{user_query}

You MUST return ONLY valid JSON with keys: sql, chart_code, explanation.

STRICT RULES:
- SQL must be READ-ONLY (SELECT only).
- For job posting questions YOU MUST USE:
      curated.fact_job_posting
- Valid job posting fields:
      posted_date, industry, occupation, employer_name,
      salary_min, salary_max, annual_salary_mean, work_type
- NEVER use tables with names:
      worc_job_postings_*, *_historical, *_nov_*, *_aug_*
  (THEY DO NOT EXIST)
- For wages, use curated.fact_wages.
- For labour force, use curated.fact_lfs_*.
- chart_code must assume df is a pandas DataFrame.
- Chart must be Plotly Express (px) only.

Here is sample data to guide SQL structure (JSON format):
{sample_data}

Return ONLY JSON. Do NOT wrap it in markdown fences.
    """

    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are a strict analytics generator."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=1000,
    )

    text = resp.choices[0].message.content.strip()

    # TRY to load JSON safely
    try:
        parsed = json.loads(text)
        return parsed
    except Exception:
        return {"error": "invalid_json", "raw": text, "trace": traceback.format_exc()}


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

    q = st.text_input(
        "Your question:",
        placeholder="e.g., Plot job postings by industry over the last 5 years",
        key="chat_input",
    )

    if q:
        topic = detect_topic(q)
        st.info(f"Detected topic: **{topic}**")

        # -----------------------------------------------
        # CHART MODE
        # -----------------------------------------------
        if any(x in q.lower() for x in ["plot", "chart", "graph", "trend"]):

            # (Optional) send sample data for schema help
            try:
                sample = run_sql("SELECT * FROM curated.fact_job_posting LIMIT 50")
                sample_json = sample.to_json(orient="records")
            except:
                sample_json = ""

            result = ask_gpt_for_chart(q, sample_data=sample_json)

            # FIXED ERROR CHECK
            if isinstance(result, dict) and "error" in result:
                st.error("AI could not generate chart JSON.")
                st.code(result.get("raw", ""))
                return

            sql = result["sql"]
            code = result["chart_code"]
            explanation = result["explanation"]

            st.subheader("SQL Generated")
            st.code(sql, language="sql")

            # execute SQL
            try:
                df = run_sql(sql)
            except Exception as e:
                st.error(f"SQL execution failed: {e}")
                st.code(sql)
                return

            st.dataframe(df)

            # run chart code safely
            try:
                env = {"px": px, "df": df}
                exec(code, {}, env)
                fig = env["fig"]

                st.subheader("Chart")
                st.plotly_chart(fig, use_container_width=True)

                st.subheader("Explanation")
                st.write(explanation)

            except Exception as e:
                st.error(f"Chart execution failed: {e}")
                st.code(code)
                return

            st.session_state.chat_history.append(("You", q))
            st.session_state.chat_history.append(("Assistant", explanation))
            st.success("Chart generated.")
            return

        # -----------------------------------------------
        # NON-CHART QUESTION
        # -----------------------------------------------
        else:
            df_sample = run_sql("SELECT * FROM curated.fact_job_posting LIMIT 50")
            data_json = df_sample.to_json(orient="records")

            prompt = f"""
User question:
{q}

Here is a JSON sample of job posting data:
{data_json}

Provide a clear answer with labour insights and SPS alignment.
            """

            answer = ask_gpt(prompt)
            st.session_state.chat_history.append(("You", q))
            st.session_state.chat_history.append(("Assistant", answer))

    # Render chat history
    st.subheader("Conversation")
    for role, msg in st.session_state.chat_history:
        st.markdown(f"**{role}:** {msg}")


# ============================================================
#   LFS TAB
# ============================================================

with tab_lfs:
    st.header("Labour Force Survey (LFS)")

    df = run_sql("SELECT * FROM curated.fact_lfs_overview_status")
    st.dataframe(df)

    if not df.empty:
        fig = px.line(
            df, x="survey_date", y="value", color="status",
            title="LFS Overview by Status"
        )
        st.plotly_chart(fig, use_container_width=True)


# ============================================================
#   WAGES TAB
# ============================================================

with tab_wages:
    st.header("Occupational Wage Survey (OWS)")

    df = run_sql("""
        SELECT *
        FROM curated.fact_wages
        WHERE category = 'industry'
          AND metric = 'mean'
          AND measure_type = 'basic_earnings'
    """)
    st.dataframe(df)

    if not df.empty:
        fig = px.bar(
            df,
            x="subcategory",
            y="value",
            title="Mean Basic Earnings by Industry",
        )
        st.plotly_chart(fig, use_container_width=True)


# ============================================================
#   JOB POSTINGS TAB
# ============================================================

with tab_jobs:
    st.header("Job Postings")

    df = run_sql("""
        SELECT posted_date, industry, COUNT(*) AS postings
        FROM curated.fact_job_posting
        WHERE posted_date IS NOT NULL
        GROUP BY posted_date, industry
        ORDER BY posted_date
    """)
    st.dataframe(df)

    if not df.empty:
        fig = px.line(
            df,
            x="posted_date",
            y="postings",
            color="industry",
            title="Job Posting Trend by Industry",
        )
        st.plotly_chart(fig, use_container_width=True)


# ============================================================
#   SPS TAB
# ============================================================

with tab_policy:
    st.header("Strategic Policy Statement (SPS)")

    df = run_sql("SELECT * FROM curated.fact_sps_context LIMIT 200")
    st.dataframe(df)

    if st.button("Summarize SPS workforce direction"):
        snippet = df.to_json(orient="records")
        prompt = f"""
Here are SPS text excerpts in JSON:
{snippet}

Summarize the workforce, education, and economic development direction
as a policy brief for senior leadership.
        """
        answer = ask_gpt(prompt)
        st.subheader("AI Summary")
        st.write(answer)

