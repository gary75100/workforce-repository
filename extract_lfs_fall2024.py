import pdfplumber
import pandas as pd
from pathlib import Path

PDF_PATH = Path("data/The Cayman Islands Labour Force Survey Report Fall 2024.pdf")
OUT_DIR = Path("data/lfs_fall_2024_tables")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def extract_all_tables():
    with pdfplumber.open(PDF_PATH) as pdf:
        table_index = 1
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables(
                {
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "intersection_tolerance": 5,
                }
            )

            if not tables:
                continue

            for t_i, table in enumerate(tables, start=1):
                df = pd.DataFrame(table)
                df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
                if df.empty:
                    continue

                fname = OUT_DIR / f"table_page{page_num}_{t_i}.csv"
                df.to_csv(fname, index=False)
                print(f"Saved: {fname}")
                table_index += 1

def extract_tables():
    table_index = 1
    manifest_rows = []

    with pdfplumber.open(PDF_PATH) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            for t_i, table in enumerate(tables, start=1):
                df = pd.DataFrame(table)

                # Drop fully empty rows and columns
                df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")

                if df.empty:
                    continue

                table_id = f"t{table_index:03d}"
                csv_path = OUT_DIR / f"{table_id}_p{page_number:03d}.csv"

                df.to_csv(csv_path, index=False)

                manifest_rows.append(
                    {
                        "table_id": table_id,
                        "page": page_number,
                        "csv_file": csv_path.name,
                        "n_rows": len(df),
                        "n_cols": len(df.columns),
                    }
                )

                table_index += 1

    manifest = pd.DataFrame(manifest_rows)
    manifest.sort_values(["page", "table_id"], inplace=True)
    manifest.to_csv(OUT_DIR / "manifest_lfs_fall2024.csv", index=False)
def extract_summary_tables():
    import pdfplumber
    import pandas as pd

    pages_to_extract = [10, 11, 14, 16]   # summary table 1 on page 10, summary table 2 on page 11
    OUT_DIR = Path("data/lfs_fall_2024_tables")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with pdfplumber.open(PDF_PATH) as pdf:
        for page_num in pages_to_extract:
            page = pdf.pages[page_num - 1]  # zero indexed
            tables = page.extract_tables(
                {
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "intersection_tolerance": 5,
                }
            )

            for idx, table in enumerate(tables, start=1):
                df = pd.DataFrame(table)
                df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
                if df.empty:
                    continue
                filename = OUT_DIR / f"summary_table_{page_num}_{idx}.csv"
                df.to_csv(filename, index=False)
                print(f"Saved: {filename}")
def force_extract_summary_tables():
    import pdfplumber
    import pandas as pd

    pages = [10, 11, 14, 16]  # summary tables
    OUT_DIR = Path("data/lfs_fall_2024_tables")

    with pdfplumber.open(PDF_PATH) as pdf:
        for page_num in pages:
            page = pdf.pages[page_num - 1]

            # treat the ENTIRE page as a table region
            table = page.extract_table(
                {
                    "vertical_strategy": "text",
                    "horizontal_strategy": "text",
                }
            )

            if table:
                df = pd.DataFrame(table)
                df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
                filename = OUT_DIR / f"summary_forced_{page_num}.csv"
                df.to_csv(filename, index=False)
                print(f"Forced extract saved: {filename}")
            else:
                print(f"No table found on page {page_num} even with forced extraction.")

if __name__ == "__main__":
    extract_all_tables()
    print("Extraction complete")

