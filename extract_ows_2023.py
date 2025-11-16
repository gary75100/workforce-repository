import pdfplumber
import pandas as pd
from pathlib import Path

# Path to the OWS PDF in your project
PDF_PATH = Path("data/The Cayman Islands_ Occupational Wage Survey 2023 Report.pdf")
# Output directory for extracted tables
OUT_DIR = Path("app/data/ows_2023_tables")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def extract_all_tables():
    print(f"Opening PDF: {PDF_PATH}")
    with pdfplumber.open(PDF_PATH) as pdf:
        print(f"PDF has {len(pdf.pages)} pages. Beginning extraction...")

        for page_num, page in enumerate(pdf.pages, start=1):

            # Try table extraction using a grid-like detection
            tables = page.extract_tables({
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
                "intersection_tolerance": 5
            })

            if tables:
                for idx, table in enumerate(tables, start=1):
                    df = pd.DataFrame(table)
                    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
                    if df.empty:
                        continue

                    filename = OUT_DIR / f"table_page{page_num:03d}_{idx}.csv"
                    df.to_csv(filename, index=False)
                    print(f"Saved table: {filename}")

            else:
                # Fallback: extract ANY grid-like text in case lines didn't register
                alt_tables = page.extract_tables()
                if alt_tables:
                    for idx, table in enumerate(alt_tables, start=1):
                        df = pd.DataFrame(table)
                        df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
                        if df.empty:
                            continue

                        filename = OUT_DIR / f"table_page{page_num:03d}_{idx}.csv"
                        df.to_csv(filename, index=False)
                        print(f"Saved fallback table: {filename}")

    print("Extraction complete.")

if __name__ == "__main__":
    extract_all_tables()

