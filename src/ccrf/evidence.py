from __future__ import annotations

import re


def _norm(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9%$]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def evidence_supported(quote: str, corpus_text: str, *, min_overlap: float = 0.72) -> bool:
    if not quote or not quote.strip():
        return False
    nq = _norm(quote)
    nt = _norm(corpus_text)
    if not nq or not nt:
        return False
    if nq in nt:
        return True
    # allow a slightly collapsed quote to match
    words = [w for w in nq.split() if len(w) > 2]
    if len(words) < 6:
        return False
    window = 12
    hits = 0
    needle = set(words[:window])
    corpus_words = nt.split()
    for i in range(0, max(1, len(corpus_words) - window + 1), 4):
        chunk = set(corpus_words[i : i + window + 8])
        overlap = len(needle & chunk) / max(len(needle), 1)
        if overlap >= min_overlap:
            return True
        hits = max(hits, overlap)
    return hits >= min_overlap
