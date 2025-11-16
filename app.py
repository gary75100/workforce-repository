import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px

from openai import OpenAI       # <-- NEW
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])   # <-- NEW

# ----------------------------------------------------
# CONFIG / CONNECTIONS
# ----------------------------------------------------
st.set_page_config(
    page_title="Cayman Workforce Intelligence Assistant",
    layout="wide"
)

# DuckDB connection (make sure this matches your filename)
from db_loader import ensure_database

db_path = ensure_database()
conn = duckdb.connect(db_path, read_only=False)

def run_sql(sql: str) -> pd.DataFrame:
    return conn.execute(sql).df()

# OpenAI client (expects OPENAI_API_KEY in .streamlit/secrets.toml)


MODEL_NAME = "gpt-4o"  # recommended for this app


# ----------------------------------------------------
# TOPIC CLASSIFICATION (simple keyword routing)
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
        "jobs", "postings", "vacancies", "openings", "demand"
    ],
    "industry": [
        "industry", "sector", "economic sector"
    ],
    "occupation": [
        "occupation", "job title", "role", "position", "profession"
    ],
    "policy": [
        "sps", "policy", "strategic", "broad outcomes", "government priority"
    ]
}

def pick_topic(user_query: str) -> str:
    q = user_query.lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(k in q for k in keywords):
            return topic
    return "general"


# ----------------------------------------------------
# ROUTING HELPERS (meta.routing + SPS context)
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
# OPENAI HELPER
# ----------------------------------------------------
def ask_gpt(prompt: str, system_msg: str = "You are a helpful Cayman workforce and policy analyst."):
    """
    NEW OpenAI API – correct schema for GPT-4o on Streamlit Cloud.
    """
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=700
    )

    # FIX: correct field access for new API
    return response.choices[0].message.content.strip()


# ----------------------------------------------------
# LAYOUT / TABS
# ----------------------------------------------------
st.title("🇰🇾 Cayman Workforce Intelligence Assistant")

tab_chat, tab_lfs, tab_wages, tab_jobs, tab_policy = st.tabs(
    ["💬 Ask a Question", "📊 Labour Force (LFS)", "💵 Wages (OWS)", "🧳 Job Postings", "📘 SPS Policy"]
)


# ====================================================
# TAB 1 — NATURAL LANGUAGE CHAT (AI + DATA, HYBRID)
# ====================================================
with tab_chat:
    st.header("Ask any workforce question")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []  # list of (role, content)

    user_q = st.text_input(
        "Your question:",
        placeholder="e.g., How have Caymanian wages in construction changed compared to job postings?",
        key="user_question_chat"
    )

    if user_q:
        topic = pick_topic(user_q)
        st.info(f"Detected topic: **{topic}**")

        tables = get_tables_for_topic(topic)
        main_table = tables[0] if tables else None

        df = pd.DataFrame()
        data_snippet = ""
        if main_table:
            try:
                # pull a small sample from the relevant table
                df = run_sql(f"SELECT * FROM {main_table} LIMIT 200")
                if not df.empty:
                    data_snippet = df.head(25).to_markdown(index=False)
            except Exception as e:
                data_snippet = f"(Error reading data: {e})"

        # SPS policy snippet
        sps_df = get_sps_context(topic)
        sps_snippet = ""
        if not sps_df.empty:
            sps_snippet = "\n\nSPS policy context:\n" + "\n\n---\n\n".join(
                [f"(Page {row['page']}): {row['text_block'][:800]}" for _, row in sps_df.iterrows()]
            )

        # Build prompt for GPT
        prompt = f"""
User question:
{user_q}

Relevant topic: {topic}

Here is a sample of relevant data from the database (if any):
{data_snippet}

{sps_snippet}

Please:
- Interpret the question in the Cayman workforce / policy context.
- Reference the data directly where possible.
- If data is limited, say so and answer qualitatively.
- Be concise but informative, and write as if briefing a senior policymaker.
"""

        answer = ask_gpt(prompt)

        # Update chat history
        st.session_state.chat_history.append(("You", user_q))
        st.session_state.chat_history.append(("Assistant", answer))
        if not df.empty:
            st.session_state.chat_history.append(("Data sample", df))
        if not sps_df.empty:
            st.session_state.chat_history.append(("SPS Context", sps_df))

    # Render full conversation
    st.markdown("### Conversation")
    for role, content in st.session_state.chat_history:
        if role in ("You", "Assistant"):
            st.markdown(f"**{role}:** {content}")
        elif role == "Data sample":
            st.markdown("**Data sample:**")
            st.dataframe(content)
        elif role == "SPS Context":
            st.markdown("**Relevant SPS Policy Context:**")
            st.dataframe(content)


# ====================================================
# TAB 2 — LFS (Labour Force)
# ====================================================
with tab_lfs:
    st.header("Labour Force Survey (LFS)")

    # Overview by status
    df_status = run_sql("SELECT * FROM curated.fact_lfs_overview_status")
    st.subheader("Overview by Status")
    st.dataframe(df_status)

    if not df_status.empty:
        fig = px.line(
            df_status,
            x="survey_date",
            y="value",
            color="status",
            title="LFS Metrics by Status over Time"
        )
        st.plotly_chart(fig, use_container_width=True)

        if st.button("Explain this LFS status chart with AI"):
            snippet = df_status.head(40).to_markdown(index=False)
            prompt = f"""
You are a Cayman labour market analyst.

Here is a table showing LFS status metrics over time:
{snippet}

Explain the key patterns and any notable trends in simple, executive-level language.
"""
            explanation = ask_gpt(prompt)
            st.markdown("### AI Explanation")
            st.write(explanation)

    # Participation rates
    df_part = run_sql("SELECT * FROM curated.fact_lfs_participation")
    st.subheader("Participation Rates")
    st.dataframe(df_part)


# ====================================================
# TAB 3 — Wages (OWS)
# ====================================================
with tab_wages:
    st.header("Occupational Wage Survey (OWS)")

    df_ind = run_sql("""
        SELECT *
        FROM curated.fact_wages
        WHERE category = 'industry' AND metric = 'mean' AND measure_type = 'basic_earnings'
    """)
    st.subheader("Mean Basic Earnings by Industry")
    st.dataframe(df_ind)

    if not df_ind.empty:
        fig = px.bar(
            df_ind,
            x="subcategory",
            y="value",
            title="Mean Monthly Basic Earnings by Industry",
            labels={"subcategory": "Industry", "value": "Mean Basic Earnings (CI$)"}
        )
        fig.update_layout(xaxis_tickangle=45)
        st.plotly_chart(fig, use_container_width=True)

        if st.button("Explain this wage chart with AI"):
            snippet = df_ind.head(40).to_markdown(index=False)
            prompt = f"""
You are a Cayman wage and labour market analyst.

Here is a table of mean basic monthly earnings by industry:
{snippet}

Explain which industries are highest and lowest paying, and what this implies for workforce and policy.
"""
            explanation = ask_gpt(prompt)
            st.markdown("### AI Explanation")
            st.write(explanation)

    df_occ = run_sql("""
        SELECT *
        FROM curated.fact_wages
        WHERE category = 'occupation' AND metric = 'mean' AND measure_type = 'basic_earnings'
        LIMIT 200
    """)
    st.subheader("Sample: Mean Basic Earnings by Occupation")
    st.dataframe(df_occ)


# ====================================================
# TAB 4 — Job Postings
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
            title="Job Posting Trend by Industry"
        )
        st.plotly_chart(fig, use_container_width=True)

        if st.button("Explain this job posting trend with AI"):
            snippet = df_jobs.head(60).to_markdown(index=False)
            prompt = f"""
You are a Cayman labour market analyst.

Here is a table of job postings by industry over time:
{snippet}

Explain which industries are growing or declining in demand, and what this means for workforce planning.
"""
            explanation = ask_gpt(prompt)
            st.markdown("### AI Explanation")
            st.write(explanation)


# ====================================================
# TAB 5 — SPS Policy
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
                title="SPS Topic Distribution"
            )
            st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.write("Could not load SPS topic distribution:", str(e))

    if st.button("Summarize SPS workforce direction with AI"):
        snippet = df_sps.head(30).to_markdown(index=False)
        prompt = f"""
You are a Cayman government policy analyst.

Here are sample excerpts from the Strategic Policy Statement:
{snippet}

Summarize the key themes related to:
- workforce
- education
- immigration
- economic development

Write as a short briefing for senior leadership.
"""
        explanation = ask_gpt(prompt)
        st.markdown("### AI SPS Summary")
        st.write(explanation)
