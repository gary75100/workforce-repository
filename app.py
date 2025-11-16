import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px

# ----------------------------------------------------
# DATABASE CONNECTION
# ----------------------------------------------------
conn = duckdb.connect("cayman_workforce.duckdb", read_only=False)

def run_sql(sql: str) -> pd.DataFrame:
    return conn.execute(sql).df()

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
# ROUTING HELPERS (use meta.routing and meta.joins)
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
# STREAMLIT CONFIG
# ----------------------------------------------------
st.set_page_config(
    page_title="Cayman Workforce Intelligence Assistant",
    layout="wide"
)

st.title("🇰🇾 Cayman Workforce Intelligence Assistant")

tab_chat, tab_lfs, tab_wages, tab_jobs, tab_policy = st.tabs(
    ["💬 Ask a Question", "📊 Labour Force (LFS)", "💵 Wages (OWS)", "🧳 Job Postings", "📘 SPS Policy"]
)

# ====================================================
# TAB 1 — NATURAL LANGUAGE CHAT EXPERIENCE
# ====================================================
with tab_chat:
    st.header("Ask any workforce question")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    user_q = st.text_input(
        "Your question:",
        placeholder="e.g., How do wages for construction compare to job postings?",
        key="user_question"
    )

    if user_q:
        topic = pick_topic(user_q)
        st.info(f"Detected topic: **{topic}**")

        tables = get_tables_for_topic(topic)
        main_table = tables[0] if tables else None

        # Very simple query strategy: show sample from the main table
        df = pd.DataFrame()
        if main_table:
            try:
                df = run_sql(f"SELECT * FROM {main_table} LIMIT 100")
            except Exception as e:
                df = pd.DataFrame({"error": [str(e)]})

        # SPS policy context
        sps_df = get_sps_context(topic)

        # Append to chat history
        st.session_state.chat_history.append(("You", user_q))
        if main_table:
            assistant_text = f"Topic: **{topic}**. Showing sample data from `{main_table}`."
        else:
            assistant_text = f"Topic: **{topic}**. I could not find a matching data table."

        st.session_state.chat_history.append(("Assistant", assistant_text))
        if not df.empty:
            st.session_state.chat_history.append(("Data", df))
        if not sps_df.empty:
            st.session_state.chat_history.append(("SPS Context", sps_df))

    # Render conversation
    st.markdown("### Conversation")
    for role, content in st.session_state.chat_history:
        if role in ("You", "Assistant"):
            st.markdown(f"**{role}:** {content}")
        elif role == "Data":
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

    # Simple Plotly line chart: value over survey_date by status
    if not df_status.empty:
        fig = px.line(
            df_status,
            x="survey_date",
            y="value",
            color="status",
            title="LFS Metrics by Status over Time"
        )
        st.plotly_chart(fig, use_container_width=True)

    # Participation by category
    df_part = run_sql("SELECT * FROM curated.fact_lfs_participation")
    st.subheader("Participation Rates")
    st.dataframe(df_part)

# ====================================================
# TAB 3 — Wages (OWS)
# ====================================================
with tab_wages:
    st.header("Occupational Wage Survey (OWS)")

    # Mean wages by industry
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
            labels={"subcategory": "Industry", "value": "Mean Basic Earnings"}
        )
        fig.update_layout(xaxis_tickangle=45)
        st.plotly_chart(fig, use_container_width=True)

    # Example: mean wages by occupation (sample)
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

# ====================================================
# TAB 5 — SPS Policy
# ====================================================
with tab_policy:
    st.header("Strategic Policy Statement (SPS) — Policy Context")

    df_sps = run_sql("SELECT * FROM curated.fact_sps_context LIMIT 200")
    st.subheader("SPS Text Blocks")
    st.dataframe(df_sps)

    # Topic distribution from dim_sps_topics, if present
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
