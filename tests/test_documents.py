import io

import pytest
from docx import Document
from pypdf import PdfWriter

from backend.utils.document_parser import parse_document


def test_pdf_without_text_is_not_fabricated():
    buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(buffer)
    assert parse_document(buffer.getvalue(), "scan.pdf").text == ""
    with pytest.raises(Exception):
        parse_document(b"%PDF invalid raw bytes", "broken.pdf")


def test_docx_and_text_truncation():
    buffer = io.BytesIO()
    doc = Document()
    doc.add_paragraph("The project deadline is Friday.")
    doc.save(buffer)
    assert "deadline is Friday" in parse_document(buffer.getvalue(), "notes.docx").text
    result = parse_document(b"x" * 25000, "long.txt")
    assert result.truncated and len(result.text) == 24000


def test_unsupported_formats_are_rejected():
    with pytest.raises(ValueError):
        parse_document(b"data", "sheet.xlsx")
