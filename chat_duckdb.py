from pathlib import Path
import os

import duckdb
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

# --------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

DB_PATH = BASE_DIR / "Workforce Development Data Team" / "cayman_workforce.duckdb"

# Key tables / prefixes in your lake
LFS_TABLE = "pdf_the_cayman_islands_labour_force_survey_report_fall_2024_t1"
WORC_ANNUAL_POSTINGS = "worc_data_v3_annual_postings"
WORC_TOTAL_POSTINGS = "worc_data_v3_total_postings"
WORC_INDUSTRY = "worc_data_v3_industry"
PERMITS_TABLE = "copy_of_current_wp_by_occupations_6_dec_2024_sheet2"
SCHOLARSHIP_TABLE = "scholarship_database_cj_edits_v2_bonding"  # use main logical view
LOCAL_STUDENT_PREFIX = "local_students"
OVERSEAS_STUDENT_PREFIX = "overseas_students"

# Load API key from .env
load_dotenv(BASE_DIR / ".env")
API_KEY = os.getenv("OPENAI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY is missing.\n"
        "Create a file named '.env' in this folder with a line like:\n"
        "OPENAI_API_KEY=sk-...your_key_here..."
    )

client = OpenAI(api_key=API_KEY)


# --------------------------------------------------------------------
# DB helpers
# --------------------------------------------------------------------

def connect_db() -> duckdb.DuckDBPyConnection:
    if not DB_PATH.exists():
        raise RuntimeError(f"Database not found at: {DB_PATH}")
    return duckdb.connect(str(DB_PATH))


def safe_select(con: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    """Run a query and return a DataFrame, with clear error messages."""
    try:
        return con.execute(sql).fetchdf()
    except Exception as e:
        raise RuntimeError(f"SQL error: {e}\nQUERY:\n{sql}")


def table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    df = con.execute(
        "SELECT 1 FROM duckdb_tables() WHERE lower(table_name) = lower(?)",
        [name],
    ).fetchdf()
    return not df.empty


# --------------------------------------------------------------------
# Executive-style LLM formatter
# --------------------------------------------------------------------

def llm_format(question: str, data_text: str) -> str:
    """
    Take raw text representing data (tables or lines) and return a short
    executive-style answer to the question.
    """
    prompt = f"""
You are a senior business analyst preparing a brief for executives. Use the DATA below to answer the QUESTION.

QUESTION:
{question}

DATA:
{data_text}

GUIDELINES:
- Write 3–7 sentences, concise and clear.
- Use business-oriented language suitable for a board or senior leadership.
- Focus on the most recent or most relevant figures when multiple time periods appear.
- Use commas in large numbers (e.g., 1048 -> 1,048).
- Use percentages with one decimal place where appropriate.
- Turn any table-like text into insights; do not show raw tables back.
- If data is incomplete, say what can be inferred and what cannot.

Return ONLY the final written answer.
""".strip()

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You write clear, executive-level analytical summaries."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.25,
    )

    return resp.choices[0].message.content.strip()


# --------------------------------------------------------------------
# Handlers
# --------------------------------------------------------------------

def handle_lfs(con: duckdb.DuckDBPyConnection, question: str) -> str:
    """
    Fall 2024 Labour Force Survey (OCR). We treat the table as flat text and let the LLM
    interpret it for unemployment, labour force, participation, etc.
    """
    if not table_exists(con, LFS_TABLE):
        return "The Fall 2024 Labour Force Survey table is not present in the data lake."

    df = safe_select(con, f'SELECT "Unnamed: 0" FROM "{LFS_TABLE}"')
    text = "LABOUR FORCE SURVEY FALL 2024 (flattened OCR table)\n" + "\n".join(
        df["Unnamed: 0"].astype(str).tolist()
    )
    return llm_format(question, text)


def handle_worc(con: duckdb.DuckDBPyConnection, question: str) -> str:
    """
    WORC job postings tables: annual totals, totals, and industry breakdown.
    """
    parts = []

    if table_exists(con, WORC_ANNUAL_POSTINGS):
        df = safe_select(con, f'SELECT * FROM "{WORC_ANNUAL_POSTINGS}"')
        parts.append("WORC ANNUAL JOB POSTINGS\n" + df.to_string(index=False))

    if table_exists(con, WORC_TOTAL_POSTINGS):
        df = safe_select(con, f'SELECT * FROM "{WORC_TOTAL_POSTINGS}"')
        parts.append("WORC TOTAL POSTINGS SUMMARY\n" + df.to_string(index=False))

    if table_exists(con, WORC_INDUSTRY):
        df = safe_select(con, f'SELECT * FROM "{WORC_INDUSTRY}"')
        parts.append("WORC JOB POSTINGS BY INDUSTRY\n" + df.to_string(index=False))

    if not parts:
        return "No WORC job-posting tables were found in the data lake."

    return llm_format(question, "\n\n".join(parts))


def handle_permits(con: duckdb.DuckDBPyConnection, question: str) -> str:
    """
    Work permits by occupation.
    """
    if not table_exists(con, PERMITS_TABLE):
        return "The work-permits-by-occupation table is not present in the data lake."

    df = safe_select(con, f'SELECT * FROM "{PERMITS_TABLE}"')
    if "Grand Total" in df.columns:
        df = df.sort_values("Grand Total", ascending=False)

    text = "WORK PERMITS BY OCCUPATION (Top rows by total permits)\n" + df.head(150).to_string(index=False)
    return llm_format(question, text)


def handle_scholarships(con: duckdb.DuckDBPyConnection, question: str) -> str:
    """
    Scholarship programmes. We use your 'bonding' or core view; adjust SCHOLARSHIP_TABLE above
    if a different sheet is more representative.
    """
    if not table_exists(con, SCHOLARSHIP_TABLE):
        return "Scholarship programme tables are not present in the data lake."

    df = safe_select(con, f'SELECT * FROM "{SCHOLARSHIP_TABLE}"')
    text = "SCHOLARSHIPS / BURSARIES (Sample rows)\n" + df.head(200).to_string(index=False)
    return llm_format(question, text)


def handle_students(con: duckdb.DuckDBPyConnection, question: str) -> str:
    """
    Local + overseas students. This is where we interpret 'college students near graduation'
    and similar questions using Expected Completion Date and degree level hints.
    """
    all_tables = safe_select(
        con,
        "SELECT table_name FROM duckdb_tables() WHERE internal = false"
    )["table_name"].tolist()

    parts = []

    for t in all_tables:
        t_lower = t.lower()
        if t_lower.startswith(LOCAL_STUDENT_PREFIX):
            df = safe_select(con, f'SELECT * FROM "{t}"')
            parts.append(
                f"TABLE {t} (LOCAL STUDENTS)\n"
                "Columns may include Local School, Degree Level, Major, etc.\n"
                + df.head(400).to_string(index=False)
            )
        if t_lower.startswith(OVERSEAS_STUDENT_PREFIX):
            df = safe_select(con, f'SELECT * FROM "{t}"')
            parts.append(
                f"TABLE {t} (OVERSEAS STUDENTS)\n"
                "Columns may include Degree Level, Major or Minor, and Expected Completion Date.\n"
                + df.head(600).to_string(index=False)
            )

    if not parts:
        return "No local or overseas student tables were found in the data lake."

    guidance = """
NOTES FOR INTERPRETING 'NEAR GRADUATION':

- Treat 'near graduation' or 'about to graduate' as students whose expected completion dates
  fall within roughly the next 12–18 months from today.
- In overseas student tables, use the 'Expected Completion Date' column to identify those cohorts.
- In local student tables, if no explicit completion date is present, use the highest degree
  levels or any 'final year' indicators (if present) as proxies.
- Summarize how many students are near graduation overall, and by major/degree level where possible.
"""
    text = guidance.strip() + "\n\n" + "\n\n".join(parts)
    return llm_format(question, text)


# --------------------------------------------------------------------
# Router
# --------------------------------------------------------------------

def route(question: str):
    """
    Decide which handler to use based on the content of the question.
    This is where we anticipate synonyms (college, grad, etc.).
    """
    q = question.lower()

    # Labour Force / Unemployment / Participation / LFS
    if any(k in q for k in [
        "labour", "labor", "unemployment", "unemployed", "employment",
        "employed", "participation rate", "lfs", "labour force survey",
        "labor force survey", "jobless", "joblessness"
    ]):
        return handle_lfs

    # Job postings / vacancies / WORC
    if any(k in q for k in [
        "job posting", "postings", "vacancy", "vacancies",
        "openings", "worc", "job board", "advertised roles"
    ]):
        return handle_worc

    # Work permits / occupations
    if any(k in q for k in [
        "work permit", "work permits", "permits", "permit",
        "occupation", "occupations", "jobs filled by permits"
    ]):
        return handle_permits

    # Scholarships / bursaries
    if any(k in q for k in [
        "scholarship", "scholarships", "bursary", "bursaries",
        "grant", "grants", "funding for students"
    ]):
        return handle_scholarships

    # Students / college / graduation / degree / university
    if any(k in q for k in [
        "student", "students", "college", "university", "undergrad",
        "undergraduate", "postgrad", "postgraduate", "degree",
        "degrees", "graduation", "graduate", "graduating",
        "near graduation", "about to graduate", "final year"
    ]):
        return handle_students

    # Fallback
    def fallback(_con, _q):
        return (
            "I can help with these domains right now:\n"
            "- Labour Force Survey (Fall 2024)\n"
            "- WORC job postings and vacancies\n"
            "- Work permits by occupation\n"
            "- Scholarship and bursary programmes\n"
            "- Local and overseas student cohorts\n\n"
            "Please rephrase your question in one of these areas."
        )

    return fallback


# --------------------------------------------------------------------
# Main loop
# --------------------------------------------------------------------

def main():
    try:
        con = connect_db()
    except Exception as e:
        print("ERROR connecting to the data lake:", e)
        return

    print("✅ Connected to Cayman Workforce Data Lake")
    print("You can ask about: LFS, job postings, work permits, scholarships, students.")
    print("Press Enter on an empty line to exit.\n")

    while True:
        try:
            q = input("Q> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if q == "":
            print("Goodbye.")
            break

        handler = route(q)

        try:
            answer = handler(con, q)
        except Exception as e:
            print("\nERROR while processing your request:\n", e)
            continue

        print("\nResult:\n")
        print(answer)
        print()

    con.close()


if __name__ == "__main__":
    main()

