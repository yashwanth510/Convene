"""
Conversation memory with a light-weight TF-IDF-style retrieval.

This avoids an external vector DB while still giving useful recall: each message
is tokenized into terms (including 2-word ngrams for phrase hits). At search time
we compute a small IDF table over the corpus and rank messages by cosine-like
similarity. Results are still filtered by `top_k` AND by a minimum relevance
floor so clearly unrelated messages are dropped.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from collections import Counter
from typing import List


_NGRAM_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'\-]{2,}")
_STOPWORDS = {
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
    "there",
    "these",
    "those",
    "each",
    "where",
    "every",
    "both",
    "same",
    "than",
    "being",
    "might",
    "must",
    "other",
}


def _tokenize(text: str, ngram: int = 2) -> list[str]:
    words = [m.group(0).lower() for m in _NGRAM_RE.finditer(text or "")]
    words = [w for w in words if w not in _STOPWORDS]
    tokens: list[str] = words[:]
    if ngram >= 2:
        for i in range(len(words) - 1):
            tokens.append(f"{words[i]} {words[i + 1]}")
    if ngram >= 3:
        for i in range(len(words) - 2):
            tokens.append(f"{words[i]} {words[i + 1]} {words[i + 2]}")
    return tokens


@dataclass
class MemoryMessage:
    id: str
    role: str
    content: str
    tokens: Counter
    length: int


class ConversationMemory:
    def __init__(self, max_messages: int = 40):
        self.max_messages = max_messages
        self.messages: List[MemoryMessage] = []

    def add(self, msg_id: str, role: str, content: str):
        if not content or not str(content).strip():
            return
        tokens = Counter(_tokenize(content))
        msg = MemoryMessage(
            id=msg_id,
            role=role,
            content=str(content),
            tokens=tokens,
            length=sum(tokens.values()),
        )
        self.messages.append(msg)
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages :]

    # ──────────────────────────────────────────────────────────────────────────
    # Search
    # ──────────────────────────────────────────────────────────────────────────
    def semantic_search(
        self, query: str, top_k: int = 6, min_score: float = 0.05
    ) -> List:
        """Return the top-k memory messages matching *query*, ranked by relevance.

        Ranking is a simple TF-IDF-style dot product; scores are normalized to
        [0, 1] for convenience, and messages below *min_score* are dropped.
        """
        if not self.messages or not query or not query.strip():
            return []

        q_tokens = Counter(_tokenize(query, ngram=2))
        if not q_tokens:
            return []

        N = len(self.messages)
        # IDF: log((N + 1) / (df + 1)) + 1
        df: Counter = Counter()
        for m in self.messages:
            for t in set(m.tokens.keys()):
                df[t] += 1

        def idf(t: str) -> float:
            return math.log((N + 1) / (df.get(t, 0) + 1)) + 1.0

        q_norm_sq = 0.0
        q_weighted: dict[str, float] = {}
        for t, f in q_tokens.items():
            w = f * idf(t)
            q_weighted[t] = w
            q_norm_sq += w * w
        if q_norm_sq <= 0:
            return []
        q_norm = math.sqrt(q_norm_sq)

        scored: list[tuple[float, MemoryMessage]] = []
        for m in self.messages:
            if m.length == 0:
                continue
            dot = 0.0
            m_norm_sq = 0.0
            for t, f in m.tokens.items():
                w = f * idf(t)
                m_norm_sq += w * w
                if t in q_weighted:
                    dot += q_weighted[t] * w
            if m_norm_sq <= 0:
                continue
            score = dot / (q_norm * math.sqrt(m_norm_sq))
            if score >= min_score:
                scored.append((score, m))

        scored.sort(key=lambda sm: -sm[0])
        out: List = []
        for score, m in scored[:top_k]:
            # Attach score as a convenience attribute (returns the original message-like objects)
            obj = type("ScoredMsg", (), {})()
            obj.id = m.id
            obj.role = m.role
            obj.content = m.content
            obj.score = round(score, 4)
            out.append(obj)
        return out

    def get_context_window(
        self, query: str, max_chars: int = 4000, top_k: int = 5
    ) -> str:
        """Return a single string summarizing the top-k relevant messages."""
        hits = self.semantic_search(query, top_k=top_k)
        if not hits:
            return ""
        chunks: list[str] = []
        total = 0
        for h in hits:
            snippet = f"[{h.role}] {h.content}"
            if total + len(snippet) > max_chars and chunks:
                break
            chunks.append(snippet)
            total += len(snippet) + 2
        return "\n\n".join(chunks)
