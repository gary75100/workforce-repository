import pdfplumber
import re
from pathlib import Path
import csv

PDF_PATH = Path("data/SPS Report 2025 FA (002).pdf")
OUT_PATH = Path("data/sps_numeric_extracted.csv")

patterns = [
    r"\b[\d,]+\.\d+\b",    # decimal numbers
    r"\b[\d,]+\b",         # integers with/without commas
    r"\b\d+%?\b",          # percentages
]

def extract_numbers():
    rows = []
    with pdfplumber.open(PDF_PATH) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            for pattern in patterns:
                for match in re.findall(pattern, text):
                    rows.append([page_num, match, text.strip()[:200]])
    return rows

rows = extract_numbers()

with open(OUT_PATH, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["page", "value", "context"])
    writer.writerows(rows)

print("Extraction complete:", OUT_PATH)

