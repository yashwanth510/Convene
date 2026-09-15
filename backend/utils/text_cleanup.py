"""Text normalization / formatting helpers."""

from __future__ import annotations

import re
import unicodedata


_WHITESPACE_RE = re.compile(r"\s+")
_FILTH_SENTINELS = [
    "[DONE]",
    "[INST]",
    "<<SYS>>",
    "<s>",
    "</s>",
    "<|endoftext|>",
    "```json",
    "</think>",
    "<think>",
]


def normalize_whitespace(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def strip_model_sentinels(text: str) -> str:
    out = text
    for s in _FILTH_SENTINELS:
        out = out.replace(s, " ")
    return out


def normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def clean_text(text: str) -> str:
    if not text:
        return ""
    t = normalize_unicode(text)
    t = strip_model_sentinels(t)
    # Remove zero-width chars
    t = re.sub(r"[\u200b-\u200f\u202a-\u202e\ufeff]", "", t)
    t = normalize_whitespace(t)
    return t


def truncate_middle(text: str, max_len: int, sep: str = "...") -> str:
    if len(text) <= max_len:
        return text
    half = (max_len - len(sep)) // 2
    return text[:half] + sep + text[-half:]


def split_sentences(text: str) -> list[str]:
    if not text:
        return []
    # Very light sentence splitter; works for most western languages
    parts = re.split(r"(?<=[.!?。！？])\s+(?=[A-Z0-9\u4e00-\u9fff\"'(“‘\-–—]", text)
    return [p.strip() for p in parts if p.strip()]


_MD_CODE_BLOCK_RE = re.compile(r"```[\w-]*\n([\s\S]*?)\n```", re.MULTILINE)


def strip_markdown_code(text: str) -> str:
    return _MD_CODE_BLOCK_RE.sub(lambda m: "\n" + m.group(1).strip() + "\n", text)


def extract_terms(text: str, min_len: int = 3) -> set[str]:
    """Very small keyword extractor: lowercase alphanumeric runs minus common stopwords."""
    STOP = {
        "the",
        "and",
        "for",
        "are",
        "but",
        "not",
        "you",
        "all",
        "can",
        "had",
        "her",
        "was",
        "one",
        "our",
        "out",
        "day",
        "get",
        "has",
        "him",
        "his",
        "how",
        "man",
        "new",
        "now",
        "old",
        "see",
        "two",
        "way",
        "who",
        "boy",
        "did",
        "its",
        "let",
        "put",
        "say",
        "she",
        "too",
        "use",
        "that",
        "this",
        "with",
        "from",
        "they",
        "been",
        "have",
        "were",
        "their",
        "what",
        "when",
        "will",
        "your",
        "them",
        "then",
        "also",
        "back",
        "after",
        "over",
        "such",
        "into",
        "than",
        "only",
        "come",
        "made",
        "find",
        "here",
        "just",
        "like",
        "long",
        "make",
        "many",
        "most",
        "much",
        "over",
        "some",
        "time",
        "very",
        "well",
        "which",
        "about",
        "would",
        "could",
        "should",
        "before",
        "between",
        "through",
        "because",
        "between",
    }
    terms: set[str] = set()
    for m in re.finditer(r"[A-Za-z][A-Za-z\-]{2,}", text.lower()):
        w = m.group(0).strip("-")
        if len(w) >= min_len and w not in STOP:
            terms.add(w)
    # Also include capitalized words (entities)
    for m in re.finditer(r"[A-Z][a-z]{2,}", text):
        terms.add(m.group(0).lower())
    return terms
