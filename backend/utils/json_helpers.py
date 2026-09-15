"""JSON extraction + sanitization helpers for LLM output strings.

LLMs often emit JSON embedded inside markdown fences, with trailing commas, or
nested in natural-language sentences. This module tries very hard to recover a
parseable dict out of whatever the model produced.
"""

from __future__ import annotations

import json
import re
from typing import Any


_JSON_JS_FENCE_RE = re.compile(r"```(?:json|js)?\s*([\s\S]*?)\s*```", re.IGNORECASE)
_LAX_COMMA_RE = re.compile(r",\s*([\]}])")
_SINGLE_QUOTE_MAP = {0: 0}  # sentinel


def _strip_outer_braces(text: str) -> str:
    # Find first { or [ and last } or ]
    first_obj = text.find("{")
    first_arr = text.find("[")
    first = min(
        first_obj if first_obj >= 0 else 10**9, first_arr if first_arr >= 0 else 10**9
    )
    if first == 10**9:
        return text
    last_obj = text.rfind("}")
    last_arr = text.rfind("]")
    last = max(last_obj, last_arr)
    if last < first:
        return text
    return text[first : last + 1]


def extract_json(text: str, default: Any | None = None) -> Any:
    """Best-effort JSON extraction from arbitrary model output."""
    if not text:
        return default
    candidate = text.strip()

    # 1) direct parse
    try:
        return json.loads(candidate)
    except Exception:
        pass

    # 2) fenced code block
    m = _JSON_JS_FENCE_RE.search(candidate)
    if m:
        candidate = m.group(1).strip()
        try:
            return json.loads(candidate)
        except Exception:
            pass

    # 3) Slice between outermost braces / brackets
    candidate = _strip_outer_braces(candidate)
    try:
        return json.loads(candidate)
    except Exception:
        pass

    # 4) Fix trailing commas
    try:
        fixed = _LAX_COMMA_RE.sub(r"\1", candidate)
        return json.loads(fixed)
    except Exception:
        pass

    # 5) Replace stray single quotes with double in a very limited way
    try:
        quoted = candidate
        # Naive replace of ':  'word' -> "word" within tokens
        quoted = re.sub(
            r"'([^'\\\n]{0,120}?)'",
            lambda mm: '"' + mm.group(1).replace('"', '\\"') + '"',
            quoted,
        )
        return json.loads(quoted)
    except Exception:
        pass

    return default


def safe_dump(obj: Any, *, indent: int = 2) -> str:
    return json.dumps(obj, indent=indent, ensure_ascii=False, default=str)


def validate_shape(obj: Any, required_keys: list[str]) -> bool:
    if not isinstance(obj, dict):
        return False
    return all(k in obj for k in required_keys)
