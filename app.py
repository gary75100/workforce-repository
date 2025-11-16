import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
import json
import traceback

from openai import OpenAI
from db_loader import ensure_database

# ----------------------------------------------------
# CONFIG / CONNECTIONS
# ----------------------------------------------------
st.set_page_config(
    page_title="Cayman Workforce Intelligence Assistant",
    layout="wide"
)

# DuckDB connection
db_path = ensure_database()
conn = duckdb.connect(db_path, read_only=False)


def run_sql(sql: str) -> pd.DataFrame:
    return conn.execute(sql).df()


# OpenAI Client (expects OPENAI_API_KEY in secrets)
MODEL_NAME = "gpt-4o"
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])


# ----------------------------------------------------
# TOPIC CLASSIFICATION
# ----------------------------------------------------
TOPIC_KEYWORDS = {
    "labour_force": [
        "unemployment", "employment", "participation", "labour", "labor",
        "workforce", "economically active", "inactive"
    ],
    "wages": [
        "wage", "salary", "pay", "earnings", "compensation", "mean annual"
    ],
    "job_postings": [
        "jobs", "postings", "vacancies", "openings", "demand", "recruiting"
    ],
    "industry": [
        "industry", "sector", "economic sector"
    ],
    "occupation": [
        "occupation", "job title", "role", "position", "profession"
    ],
    "policy": [
        "sps", "policy", "strategic", "broad outcomes", "government priority"
    ],
}


def pick_topic(user_query: str) -> str:
    q = user_query.lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(k in q for k in keywords):
            return topic
    return "general"


# ----------------------------------------------------
# ROUTING HELPERS
# ----------------------------------------------------
def get_tables_for_topic(topic: str) -> list[str]:
    sql = f"""
        SELECT tables
        FROM meta.routing
        WHERE topic = '{topic}'
        LIMIT 1
    """
    row = conn.execute(sql).fetchone()
    if not row:
        return []
    return [t.strip() for t in row[0].split(",")]


def get_sps_context(topic: str) -> pd.DataFrame:
    sql = f"""
        SELECT page, text_block
        FROM curated.fact_sps_context
        WHERE text_block ILIKE '%{topic}%'
        LIMIT 3
    """
    return run_sql(sql)


# ----------------------------------------------------
# GPT HELPERS
# ----------------------------------------------------
def ask_gpt(
    prompt: str,
    system_msg: str = "You are a helpful Cayman workforce and policy analyst."
) -> str:
    """
    Generic GPT-4o call for explanations and summaries.
    """
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=900,
    )
    return response.choices[0].message.content.strip()


def ask_gpt_for_chart(
    user_query: str,
    sample_data: str = "",
    system_msg: str = "You are a Cayman workforce analytics assistant."
) -> dict:
    """
    Ask GPT to produce:
    - SQL query (DuckDB SELECT)
    - Plotly code using a local df
    - Explanation of the chart

    Returns a dict with keys: sql, chart_code, explanation
    If parsing fails, returns {"error": ..., "raw": ..., "trace": ...}
    """
    prompt = f"""
You are an analytics copilot for Cayman workforce intelligence.

User question:
{user_query}

You MUST respond ONLY with valid JSON of the form:
{{
  "sql": "SELECT ...",
  "chart_code": "fig = px.line(df, x='col1', y='col2', color='col3')",
  "explanation": "brief explanation of what the chart shows"
}}

RULES:
- SQL must be READ-ONLY (only SELECT; no UPDATE, DELETE, INSERT, ALTER, DROP).
- For job postings, you MUST ALWAYS use this table:
    curated.fact_job_posting
- Valid job posting fields are:
    posted_date, industry, employer_name, occupation, salary_min, salary_max,
    annual_salary_mean, work_type
- NEVER use tables with names worc_job_postings_*, *_historical, *_nov_*, *_aug_*.
  Those DO NOT exist.
- For wages, use curated.fact_wages.
- For labour force, use curated.fact_lfs_*.
- The chart_code must assume a pandas DataFrame named df.
- Use Plotly Express (px) ONLY.
- Return ONLY JSON with keys: sql, chart_code, explanation.

Here is some optional sample data (may be empty):
{sample_data}
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=900,
    )

    text = response.choices[0].message.content.strip()

    try:
        parsed = json.loads(text)
        return parsed
    except Exception:
        return {
            "error": "Invalid JSON from GPT",
            "raw": text,
            "trace": traceback.format_exc(),
        }


# ----------------------------------------------------
# STREAMLIT APP LAYOUT
# ----------------------------------------------------
st.title("🇰🇾 Cayman Workforce Intelligence Assistant")

tab_chat, tab_lfs, tab_wages, tab_jobs, tab_policy = st.tabs(
    [
        "💬 Ask a Question",
        "📊 Labour Force (LFS)",
        "💵 Wages (OWS)",
        "🧳 Job Postings",
        "📘 SPS Policy",
    ]
)

# ====================================================
# TAB 1 — CHAT (HYBRID: QA + AUTO-CHART)
# ====================================================
with tab_chat:
    st.header("Ask any workforce question")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    user_q = st.text_input(
        "Your question:",
        placeholder="e.g., Plot job postings by industry 2019–2025 or Summarize Caymanian participation.",
        key="user_question_chat",
    )

    if user_q:
        topic = pick_topic(user_q)
        st.info(f"Detected topic: **{topic}**")

        # If question looks like a chart request → Chart mode
        if any(word in user_q.lower() for word in ["plot", "chart", "graph"]):
            # Optional sample data (kept simple to avoid heavy payloads)
            tables = get_tables_for_topic(topic)
            main_table = tables[0] if tables else None
            sample_data_str = ""
            if main_table:
                try:
                    sample_df = run_sql(f"SELECT * FROM {main_table} LIMIT 50")
                    sample_data_str = sample_df.to_json(orient="records")
                except Exception:
                    sample_data_str = ""

            result = ask_gpt_for_chart(user_q, sample_data=sample_data_str)

            st.session_state.chat_history.append(("You", user_q))

            if "error" in result:
                st.error("AI could not generate a chart. Showing raw output.")
                st.text(result.get("raw", ""))
                st.session_state.chat_history.append(
                    ("Assistant", "I could not safely generate a chart from that request.")
                )
            else:
                sql = result.get("sql", "")
                chart_code = result.get("chart_code", "")
                explanation = result.get("explanation", "")

                st.markdown("### Generated SQL")
                st.code(sql, language="sql")

                try:
                    df = run_sql(sql)
                    st.markdown("### Data")
                    st.dataframe(df)

                    # Safe environment for chart code
                    local_env = {"px": px, "df": df}
                    exec(chart_code, {}, local_env)
                    fig = local_env.get("fig", None)

                    if fig is not None:
                        st.markdown("### Chart")
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.error("The AI did not return a 'fig' object in chart_code.")

                    if explanation:
                        st.markdown("### Explanation")
                        st.write(explanation)

                    st.session_state.chat_history.append(
                        ("Assistant", f"Generated a chart and explanation for your request.")
                    )

                except Exception as e:
                    st.error(f"Error running AI-generated SQL or chart code: {e}")
                    st.session_state.chat_history.append(
                        ("Assistant", "I encountered an error generating that chart.")
                    )

        # Otherwise → QA / summary mode
        else:
            tables = get_tables_for_topic(topic)
            main_table = tables[0] if tables else None

            data_snippet = ""
            if main_table:
                try:
                    df = run_sql(f"SELECT * FROM {main_table} LIMIT 80")
                    data_snippet = df.to_json(orient="records")
                except Exception:
                    data_snippet = ""

            sps_df = get_sps_context(topic)
            sps_snippet = ""
            if not sps_df.empty:
                sps_snippet = sps_df.to_json(orient="records")

            prompt = f"""
User question:
{user_q}

Detected topic: {topic}

Here is a JSON sample of relevant data (if any):
{data_snippet}

Here is some SPS policy text in JSON (if any):
{sps_snippet}

Using the data and policy context:
- Answer the question directly.
- Reference the data where possible.
- Add SPS policy alignment where relevant.
- Keep it concise but executive-level.
"""
            answer = ask_gpt(prompt)

            st.session_state.chat_history.append(("You", user_q))
            st.session_state.chat_history.append(("Assistant", answer))

    # Render chat history
    st.markdown("### Conversation")
    for role, content in st.session_state.chat_history:
        if role in ("You", "Assistant"):
            st.markdown(f"**{role}:** {content}")


# ====================================================
# TAB 2 — LFS
# ====================================================
with tab_lfs:
    st.header("Labour Force Survey (LFS)")

    df_status = run_sql("SELECT * FROM curated.fact_lfs_overview_status")
    st.subheader("Overview by Status")
    st.dataframe(df_status)

    if not df_status.empty:
        fig = px.line(
            df_status,
            x="survey_date",
            y="value",
            color="status",
            title="LFS Metrics by Status over Time",
        )
        st.plotly_chart(fig, use_container_width=True)

        if st.button("Explain this LFS status chart with AI"):
            snippet = df_status.head(60).to_json(orient="records")
            prompt = f"""
You are a Cayman labour market analyst.

Here are LFS status indicators in JSON:
{snippet}

Explain the key patterns and notable trends for status groups (e.g., Caymanian vs non-Caymanian, employed, unemployed).
Keep it short and executive-level.
"""
            explanation = ask_gpt(prompt)
            st.markdown("### AI Explanation")
            st.write(explanation)

    df_part = run_sql("SELECT * FROM curated.fact_lfs_participation")
    st.subheader("Participation Rates")
    st.dataframe(df_part)


# ====================================================
# TAB 3 — WAGES (OWS)
# ====================================================
with tab_wages:
    st.header("Occupational Wage Survey (OWS)")

    df_ind = run_sql("""
        SELECT *
        FROM curated.fact_wages
        WHERE category = 'industry'
          AND metric = 'mean'
          AND measure_type = 'basic_earnings'
    """)
    st.subheader("Mean Basic Earnings by Industry")
    st.dataframe(df_ind)

    if not df_ind.empty:
        fig = px.bar(
            df_ind,
            x="subcategory",
            y="value",
            title="Mean Monthly Basic Earnings by Industry (CI$)",
            labels={"subcategory": "Industry", "value": "Mean Basic Earnings"},
        )
        fig.update_layout(xaxis_tickangle=45)
        st.plotly_chart(fig, use_container_width=True)

        if st.button("Explain this wage chart with AI"):
            snippet = df_ind.head(40).to_json(orient="records")
            prompt = f"""
You are a Cayman wage and labour market analyst.

Here is JSON data: mean monthly basic earnings by industry:
{snippet}

Explain which industries are highest and lowest paying and what this implies for workforce and SPS policy.
"""
            explanation = ask_gpt(prompt)
            st.markdown("### AI Explanation")
            st.write(explanation)

    df_occ = run_sql("""
        SELECT *
        FROM curated.fact_wages
        WHERE category = 'occupation'
          AND metric = 'mean'
          AND measure_type = 'basic_earnings'
        LIMIT 200
    """)
    st.subheader("Sample: Mean Basic Earnings by Occupation")
    st.dataframe(df_occ)


# ====================================================
# TAB 4 — JOB POSTINGS
# ====================================================
with tab_jobs:
    st.header("Job Postings (WORC)")

    df_jobs = run_sql("""
        SELECT posted_date, industry, COUNT(*) AS postings
        FROM curated.fact_job_posting
        WHERE posted_date IS NOT NULL
        GROUP BY posted_date, industry
        ORDER BY posted_date
    """)
    st.subheader("Job Postings by Industry over Time")
    st.dataframe(df_jobs)

    if not df_jobs.empty:
        fig = px.line(
            df_jobs,
            x="posted_date",
            y="postings",
            color="industry",
            title="Job Posting Trend by Industry",
        )
        st.plotly_chart(fig, use_container_width=True)

        if st.button("Explain this job posting trend with AI"):
            snippet = df_jobs.head(80).to_json(orient="records")
            prompt = f"""
You are a Cayman labour market analyst.

Here is JSON data: job postings by industry over time:
{snippet}

Explain which industries show rising demand, which are flat or declining, and what this means for labour supply and SPS workforce priorities.
"""
            explanation = ask_gpt(prompt)
            st.markdown("### AI Explanation")
            st.write(explanation)


# ====================================================
# TAB 5 — SPS POLICY
# ====================================================
with tab_policy:
    st.header("Strategic Policy Statement (SPS) — Policy Context")

    df_sps = run_sql("SELECT * FROM curated.fact_sps_context LIMIT 200")
    st.subheader("SPS Text Blocks")
    st.dataframe(df_sps)

    try:
        df_topics = run_sql("""
            SELECT topic, COUNT(*) AS mentions
            FROM curated.dim_sps_topics
            GROUP BY topic
        """)
        if not df_topics.empty:
            st.subheader("SPS Topic Distribution")
            fig = px.pie(
                df_topics,
                names="topic",
                values="mentions",
                title="SPS Topic Distribution",
            )
            st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.write("Could not load SPS topic distribution:", str(e))

    if st.button("Summarize SPS workforce direction with AI"):
        snippet = df_sps.head(40).to_json(orient="records")
        prompt = f"""
You are a Cayman government policy analyst.

Here are sample SPS excerpts in JSON:
{snippet}

Summarize the key SPS themes related to:
- workforce
- education
- immigration
- economic development

Write this as a brief for senior leadership.
"""
        explanation = ask_gpt(prompt)
        st.markdown("### AI SPS Summary")
        st.write(explanation)
