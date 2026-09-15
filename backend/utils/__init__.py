"""Shared utility helpers for the Convene backend."""

from backend.utils.text_cleanup import (
    clean_text,
    extract_terms,
    normalize_unicode,
    normalize_whitespace,
    split_sentences,
    strip_markdown_code,
    strip_model_sentinels,
    truncate_middle,
)
from backend.utils.token_estimator import (
    estimate_tokens,
    estimate_tokens_messages,
    truncate_to_tokens,
)
from backend.utils.json_helpers import (
    extract_json,
    safe_dump,
    validate_shape,
)
from backend.utils.document_parser import (
    ParsedDocument,
    detect_kind,
    parse_document,
)

__all__ = [
    # text cleanup
    "clean_text",
    "extract_terms",
    "normalize_unicode",
    "normalize_whitespace",
    "split_sentences",
    "strip_markdown_code",
    "strip_model_sentinels",
    "truncate_middle",
    # tokens
    "estimate_tokens",
    "estimate_tokens_messages",
    "truncate_to_tokens",
    # json
    "extract_json",
    "safe_dump",
    "validate_shape",
    # documents
    "ParsedDocument",
    "detect_kind",
    "parse_document",
]
