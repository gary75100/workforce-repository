from fpdf import FPDF
import tempfile

def export_summary_to_pdf(title, summary_text):
    """
    Creates a simple branded PDF containing:
    - Title
    - Summary text
    """

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Title Section
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, title, ln=True)

    # Summary Body
    pdf.set_font("Arial", "", 12)
    for line in summary_text.split("\n"):
        pdf.multi_cell(0, 8, line)

    # Save to temp file
    temp_path = tempfile.mktemp(suffix=".pdf")
    pdf.output(temp_path)

    return temp_path

