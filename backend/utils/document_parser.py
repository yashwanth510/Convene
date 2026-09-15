"""
Lightweight document parsers for common file types.

Strategy:
- Text / CSV / JSON / XML / YAML / source code: read as UTF-8 text.
- DOCX: use `python-docx` (already declared dependency).
- XLSX: use `openpyxl` (already declared dependency).
- PPTX: use `python-pptx` (already declared dependency).
- PDF:
    1. Try `pypdf` if user has it installed.
    2. Else try `PyPDF2`.
    3. Else fall back to basic embedded-text extraction using a regex over raw bytes.
- Images: return metadata only; text extraction is NOT provided here.
"""

from __future__ import annotations

import csv
import io
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zipfile import ZipFile


@dataclass
class ParsedDocument:
    kind: str
    pages: int
    length_chars: int
    length_words: int
    text: str
    meta: dict[str, Any]


_MAX_TEXT_LEN = 200_000


def _trim(text: str) -> str:
    if len(text) <= _MAX_TEXT_LEN:
        return text
    head = text[: _MAX_TEXT_LEN // 2]
    tail = text[-_MAX_TEXT_LEN // 2 :]
    return f"{head}\n\n… [truncated; original length {len(text):,} chars] …\n\n{tail}"


# ──────────────────────────────────────────────────────────────────────────────
# Plain text (handles code, markdown, CSV as fallback, etc.)
# ──────────────────────────────────────────────────────────────────────────────
def parse_text(data: bytes, encoding_hint: str | None = None) -> str:
    for enc in filter(None, [encoding_hint, "utf-8", "utf-8-sig", "latin-1"]):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")


# ──────────────────────────────────────────────────────────────────────────────
# CSV / TSV (pretty-printed as a grid)
# ──────────────────────────────────────────────────────────────────────────────
def parse_csv(data: bytes, delimiter: str | None = None) -> str:
    text = parse_text(data)
    buf = io.StringIO(text)
    try:
        sample = buf.read(4096)
        buf.seek(0)
        if delimiter is None:
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
                delimiter = dialect.delimiter
            except csv.Error:
                delimiter = ","
        reader = csv.reader(buf, delimiter=delimiter)
        rows = list(reader)
    except Exception:
        return parse_text(data)

    if not rows:
        return ""
    # Pretty print first 500 rows as markdown-ish table
    out: list[str] = []
    max_rows = 500
    for i, row in enumerate(rows[:max_rows]):
        cleaned = [str(cell).strip().replace("|", "/") for cell in row]
        out.append("| " + " | ".join(cleaned) + " |")
        if i == 0 and len(rows) > 1:
            out.append("|" + "|".join(["---"] * len(cleaned)) + "|")
    if len(rows) > max_rows:
        out.append(f"\n\n_… ({len(rows) - max_rows:,} more rows omitted)_")
    return "\n".join(out)


# ──────────────────────────────────────────────────────────────────────────────
# DOCX
# ──────────────────────────────────────────────────────────────────────────────
def parse_docx(data: bytes) -> str:
    try:
        from docx import Document as DocxDocument  # type: ignore
    except Exception:
        return _parse_zip_xml_fallback(data, "word/document.xml")

    buf = io.BytesIO(data)
    doc = DocxDocument(buf)
    parts: list[str] = []
    for p in doc.paragraphs:
        if p.text.strip():
            parts.append(p.text.strip())
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip().replace("|", "/") for c in row.cells]
            parts.append("| " + " | ".join(cells) + " |")
    return "\n".join(parts)


def _parse_zip_xml_fallback(data: bytes, inner_path: str) -> str:
    """Super-light fallback: unzip file & extract body text from XML."""
    try:
        with ZipFile(io.BytesIO(data)) as zf:
            with zf.open(inner_path) as f:
                xml_bytes = f.read()
        root = ET.fromstring(xml_bytes)
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        texts = [el.text for el in root.iter() if el.text and el.text.strip()]
        return "\n".join(t for t in texts if t.strip())
    except Exception:
        return ""


# ──────────────────────────────────────────────────────────────────────────────
# XLSX (openpyxl)
# ──────────────────────────────────────────────────────────────────────────────
def parse_xlsx(data: bytes) -> str:
    try:
        from openpyxl import load_workbook  # type: ignore
    except Exception:
        return "[OpenPyXL not available; cannot parse .xlsx]"

    buf = io.BytesIO(data)
    wb = load_workbook(buf, read_only=True, data_only=True)
    out: list[str] = []
    for sheet in wb.sheetnames:
        ws = wb[sheet]
        out.append(f"\n\n## Sheet: {sheet}\n")
        max_rows = 500
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i >= max_rows:
                out.append(f"\n_… (rows after {max_rows} omitted)_")
                break
            cells = [
                ("" if v is None else str(v)).strip().replace("|", "/") for v in row
            ]
            if any(c for c in cells):
                out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


# ──────────────────────────────────────────────────────────────────────────────
# PPTX (python-pptx)
# ──────────────────────────────────────────────────────────────────────────────
def parse_pptx(data: bytes) -> str:
    try:
        from pptx import Presentation  # type: ignore
    except Exception:
        return "[python-pptx not available; cannot parse .pptx]"

    buf = io.BytesIO(data)
    prs = Presentation(buf)
    out: list[str] = []
    for idx, slide in enumerate(prs.slides, 1):
        out.append(f"\n\n--- Slide {idx} ---\n")
        for shape in slide.shapes:
            if shape.has_text_frame:
                for p in shape.text_frame.paragraphs:
                    t = "".join(run.text for run in p.runs)
                    if t.strip():
                        out.append(t.strip())
            if shape.has_table:
                tbl = shape.table
                for row in tbl.rows:
                    cells = [c.text.strip().replace("|", "/") for c in row.cells]
                    out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


# ──────────────────────────────────────────────────────────────────────────────
# PDF (best-effort)
# ──────────────────────────────────────────────────────────────────────────────
_PDF_WORD_RE = re.compile(rb"[A-Za-z][A-Za-z'\-]{1,}")


def parse_pdf(data: bytes) -> str:
    # 1. pypdf
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(io.BytesIO(data))
        pages = [p.extract_text() or "" for p in reader.pages]
        text = "\n\n".join(pages)
        if text.strip():
            return text
    except Exception:
        pass
    # 2. PyPDF2
    try:
        from PyPDF2 import PdfReader as Py2Reader  # type: ignore

        reader = Py2Reader(io.BytesIO(data))
        pages = [p.extract_text() or "" for p in reader.pages]
        text = "\n\n".join(pages)
        if text.strip():
            return text
    except Exception:
        pass
    # 3. Fallback: extract obvious ASCII tokens from raw bytes so we have *something*
    try:
        words = [m.group(0).decode("latin-1") for m in _PDF_WORD_RE.finditer(data)]
        text = " ".join(words)
        if len(text) < 200:
            return "[PDF text extraction failed: install `pypdf` for best results]"
        return (
            text
            + "\n\n[_Note: basic byte-scrape extraction — install `pypdf` for accurate PDF parsing._]"
        )
    except Exception:
        return "[PDF text extraction failed]"


# ──────────────────────────────────────────────────────────────────────────────
# JSON / YAML / XML (pretty printed)
# ──────────────────────────────────────────────────────────────────────────────
def parse_json_bytes(data: bytes) -> str:
    text = parse_text(data)
    try:
        obj = json.loads(text)
        return json.dumps(obj, indent=2, ensure_ascii=False, default=str)
    except Exception:
        return text


def parse_xml_bytes(data: bytes) -> str:
    text = parse_text(data)
    try:
        ET.fromstring(text)
        return text  # XML is already fairly human-readable
    except Exception:
        return text


# ──────────────────────────────────────────────────────────────────────────────
# Dispatcher
# ──────────────────────────────────────────────────────────────────────────────
_PARSERS: dict[tuple[str, ...], tuple[str, Any]] = {
    (".txt", ".md", ".markdown", ".log", ".cfg", ".ini", ".conf", ".rst", ".rtf"): (
        "text",
        parse_text,
    ),
    (".csv",): ("csv", parse_csv),
    (".tsv",): ("tsv", lambda d: parse_csv(d, "\t")),
    (".json", ".ipynb"): ("json", parse_json_bytes),
    (".yaml", ".yml"): ("yaml", parse_text),
    (".xml", ".svg"): ("xml", parse_xml_bytes),
    (".html", ".htm"): ("html", parse_text),
    (".docx",): ("docx", parse_docx),
    (".xlsx",): ("xlsx", parse_xlsx),
    (".pptx",): ("pptx", parse_pptx),
    (".pdf",): ("pdf", parse_pdf),
}

_SOURCE_EXTS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".rs",
    ".go",
    ".java",
    ".kt",
    ".scala",
    ".swift",
    ".rb",
    ".php",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cc",
    ".hh",
    ".cs",
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".ps1",
    ".sql",
    ".lua",
    ".r",
    ".R",
    ".m",
    ".mm",
    ".pl",
    ".pm",
    ".ex",
    ".exs",
    ".erl",
    ".hs",
    ".elm",
    ".clj",
    ".dart",
    ".vue",
    ".svelte",
    ".css",
    ".scss",
    ".less",
    ".toml",
    ".Dockerfile",
    ".vim",
    ".tex",
}


def detect_kind(filename: str, mime: str | None = None) -> str:
    ext = Path(filename).suffix.lower()
    if mime and mime.startswith("image/"):
        return "image"
    if ext in _SOURCE_EXTS:
        return "code"
    for exts, (kind, _) in _PARSERS.items():
        if ext in exts:
            return kind
    if mime and mime.startswith("text/"):
        return "text"
    return "unknown"


def parse_document(
    data: bytes, filename: str, mime: str | None = None
) -> ParsedDocument:
    ext = Path(filename).suffix.lower()
    kind = detect_kind(filename, mime)

    if kind == "image":
        return ParsedDocument(
            kind="image",
            pages=1,
            length_chars=0,
            length_words=0,
            text="",
            meta={
                "type": "image",
                "size_bytes": len(data),
                "mime": mime or "",
                "ext": ext,
            },
        )

    # Pick a parser
    parser: Any = parse_text
    for exts, (k, p) in _PARSERS.items():
        if ext in exts:
            parser = p
            break
    if kind == "code":
        parser = parse_text

    try:
        raw_text = parser(data) if parser is not parse_text else parse_text(data)
    except Exception as e:
        raw_text = f"[_Parser error: {e}_]\n\n" + parse_text(data)

    cleaned = _trim(raw_text.strip())
    words = cleaned.split()
    pages = max(1, len(words) // 300)

    meta: dict[str, Any] = {
        "size_bytes": len(data),
        "mime": mime or "",
        "ext": ext,
    }

    return ParsedDocument(
        kind=kind,
        pages=pages,
        length_chars=len(cleaned),
        length_words=len(words),
        text=cleaned,
        meta=meta,
    )
