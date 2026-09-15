"""Extract text from the formats accepted by the upload API."""

import csv
import io
import json
from dataclasses import dataclass
from pathlib import Path

from docx import Document
from pypdf import PdfReader

TEXT_LIMIT = 24000
SUPPORTED_EXTENSIONS = {
    ".txt",
    ".md",
    ".pdf",
    ".docx",
    ".csv",
    ".json",
    ".py",
    ".js",
    ".ts",
}


@dataclass
class ParsedDocument:
    text: str
    truncated: bool = False


def _text(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        if data.startswith((b"\xff\xfe", b"\xfe\xff")):
            return data.decode("utf-16")
        raise ValueError("Text documents must use UTF-8 or UTF-16") from None


def _parts(parts) -> str:
    """Read enough text to report truncation without collecting the whole document."""
    output, length = [], 0
    for part in parts:
        output.append(part)
        length += len(part) + 2
        if length > TEXT_LIMIT:
            break
    return "\n\n".join(output)


def parse_document(
    data: bytes, filename: str, mime: str | None = None
) -> ParsedDocument:
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("Unsupported document format")
    if extension == ".pdf":
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("Upload an unlocked PDF")
        if len(reader.pages) > 200:
            raise ValueError("PDFs may contain at most 200 pages")
        text = _parts(page.extract_text() or "" for page in reader.pages)
    elif extension == ".docx":
        doc = Document(io.BytesIO(data))

        def parts():
            yield from (p.text for p in doc.paragraphs if p.text.strip())
            for table in doc.tables:
                for row in table.rows:
                    yield " | ".join(cell.text for cell in row.cells)

        text = _parts(parts())
    elif extension == ".csv":
        decoded = _text(data)
        try:
            dialect = csv.Sniffer().sniff(decoded[:4096], delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        text = _parts(
            " | ".join(row) for row in csv.reader(io.StringIO(decoded), dialect)
        )
    elif extension == ".json":
        text = json.dumps(json.loads(_text(data)), ensure_ascii=False, indent=2)
    else:
        text = _text(data)
    text = text.strip()
    return ParsedDocument(text=text[:TEXT_LIMIT], truncated=len(text) > TEXT_LIMIT)
