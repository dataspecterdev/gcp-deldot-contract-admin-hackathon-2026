"""Retrieve a few Title 29 § 69xx paragraphs per CC — never dump the whole chapter."""

from __future__ import annotations

import re

from ccrf.config import REPO_ROOT

STATUTE_PATH = REPO_ROOT / "References" / "Delaware_Title29_Chapter69_SubchapterIV.txt"

# Only overlap CCs. Do not retrieve prevailing wage, craft training, or
# public-building 50% rules (those are not road/highway CC-14).
CC_STATUTE_QUERY: dict[str, dict[str, str]] = {
    "CC-02": {"section": "6962", "must_contain": "10% of the bid"},
    "CC-04": {"section": "6962", "must_contain": "100% of the contract price"},
    "CC-05": {"section": "6962", "must_contain": "within 20 days of the awarding"},
    "CC-06": {"section": "6968", "must_contain": "certificate of registration"},
    "CC-07": {"section": "6967", "must_contain": "occupational"},
    "CC-11": {"section": "6963", "must_contain": "change order"},
}


def _section_blocks(text: str) -> dict[str, str]:
    parts = re.split(r"(?=^§\s+69)", text, flags=re.MULTILINE)
    out: dict[str, str] = {}
    for part in parts:
        m = re.match(r"^§\s+(69\d+[A-Z]?)", part.strip())
        if m:
            out[m.group(1)] = part.strip()
    return out


def retrieve_statute_excerpt(requirement_id: str, *, max_chars: int = 1600) -> str:
    query = CC_STATUTE_QUERY.get(requirement_id)
    if not query or not STATUTE_PATH.exists():
        return ""
    text = STATUTE_PATH.read_text(encoding="utf-8")
    block = _section_blocks(text).get(query["section"], "")
    if not block:
        return ""
    needle = query["must_contain"].lower()
    paras = [p.strip() for p in re.split(r"\n\s*\n", block) if p.strip()]
    chosen = [p for p in paras if needle in p.lower()]
    if not chosen:
        chosen = paras[:1]
    excerpt = "\n\n".join(chosen)
    excerpt = re.sub(r"\s+", " ", excerpt).strip()
    if len(excerpt) > max_chars:
        excerpt = excerpt[: max_chars - 3] + "..."
    return (
        f"Delaware Code Title 29 § {query['section']} "
        f"(retrieved; do not flag issues outside Challenge_Reference_Rule):\n{excerpt}\n"
    )
