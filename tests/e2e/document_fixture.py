"""Make an image-only PDF so the browser check exercises real OCR, not a text layer."""

import sys
from pathlib import Path

import pypdfium2 as pdfium
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

folder = Path(sys.argv[1])
folder.mkdir(parents=True, exist_ok=True)
digital = folder / "table-original.pdf"
styles = getSampleStyleSheet()
table = Table(
    [
        ["Month", "Failed", "Completed", "Failure rate"],
        ["August", "300", "10000", "3.00%"],
        ["September", "380", "10000", "3.80%"],
        ["October", "1110", "10000", "11.10%"],
    ],
    colWidths=[130, 100, 130, 140],
    rowHeights=44,
)
table.setStyle(
    TableStyle(
        [
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 14),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5efea")),
        ]
    )
)
SimpleDocTemplate(str(digital), pagesize=(612, 792), leftMargin=48, rightMargin=48).build(
    [
        Paragraph("Synthetic payment failure summary", styles["Title"]),
        Spacer(1, 24),
        table,
        Spacer(1, 24),
        Paragraph(
            "Failed / completed transactions. Pending transactions are excluded.",
            styles["BodyText"],
        ),
    ]
)
with pdfium.PdfDocument(digital) as pdf:
    page = pdf[0]
    bitmap = page.render(scale=3)
    image = bitmap.to_pil()
    image.save(folder / "scanned-table.pdf", "PDF", resolution=216)
    image.close()
    bitmap.close()
    page.close()
print(folder / "scanned-table.pdf")
