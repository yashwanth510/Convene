"""Lightweight token estimators (no external deps).

Approximation strategy:
- For English-like text: ~4 chars per token (GPT-2 rule of thumb)
- For CJK characters: ~1 char per token
- Code / mixed: weighted average

These are intentionally conservative estimators — they tend to OVERESTIMATE slightly,
which is the safe side for token-budget limits.
"""

from __future__ import annotations

import re


_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def estimate_tokens(text: str) -> int:
    if not text:
        return 0

    cjk_chars = len(_CJK_RE.findall(text))
    raw_len = len(text)
    non_cjk_chars = max(0, raw_len - cjk_chars)

    # English chars / ~4, CJK / ~1.25
    est = (non_cjk_chars / 4.0) + (cjk_chars * 1.25)

    # Bump for punctuation (tend to produce extra tokens)
    punct_count = len(_PUNCT_RE.findall(text))
    est += punct_count * 0.2

    return max(1, int(est + 0.5))


def estimate_tokens_messages(messages: list[dict] | list[str]) -> int:
    total = 0
    for item in messages:
        if isinstance(item, str):
            total += estimate_tokens(item) + 3  # small role/sep overhead
        elif isinstance(item, dict):
            for v in item.values():
                if isinstance(v, str):
                    total += estimate_tokens(v) + 3
    # ChatML-ish overhead per message
    total += 4 * len(messages)
    return total


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate *text* roughly so its *estimated* token count <= max_tokens."""
    if estimate_tokens(text) <= max_tokens:
        return text
    # Binary-search-ish approach: start from ratio
    target_chars = int(max_tokens * 4)
    out = text[:target_chars]
    while estimate_tokens(out) > max_tokens and len(out) > 0:
        out = out[: int(len(out) * 0.9)]
    return out + "…"
