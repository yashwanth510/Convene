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
