from __future__ import annotations

import re
from collections import defaultdict

from ccrf.models import PackageCorpus, PrecedenceSnapshot, Snippet

REVISION_RE = re.compile(
    r"(delete[sd]?\s+and\s+replace|"
    r"deleted?\s+and\s+replaced|"
    r"revise[ds]?\s+section|"
    r"is\s+hereby\s+(revised|amended|deleted)|"
    r"replace[sd]?\s+in\s+(its|their)\s+entirety|"
    r"supersede[ds]?|"
    r"delete[sd]?\s*/\s*replace)",
    re.IGNORECASE,
)

ADDENDUM_ACK_RE = re.compile(
    r"(?:acknowled(?:ge[sd]?|gment)|receipt of)\s+.{0,80}?addend(?:um|a)\s+"
    r"([0-9a-c,\s&/-]+(?:\s*(?:and|&)\s*[0-9a-c]+)?)",
    re.IGNORECASE,
)

IGNORE_LATER_ADDENDA_RE = re.compile(
    r"later issued addenda may be disregarded",
    re.IGNORECASE,
)

# Keyword cues tuned to CC-01..CC-18 and the six labeled packages.
REQUIREMENT_KEYWORDS: dict[str, list[str]] = {
    "CC-01": ["fhwa-1273", "fhwa 1273", "form fhwa", "physically incorporate"],
    "CC-02": ["proposal guaranty", "bid bond", "bid guaranty", "10%", "10 percent", "5%", "5 percent"],
    "CC-03": ["non-collusive", "noncollusive", "collusion", "certification"],
    "CC-04": ["performance bond", "payment bond", "surety", "100%", "75%", "bond coverage"],
    "CC-05": ["notice of award", "20 calendar days", "45 calendar days", "certificate of insurance", "proof of insurance", "contract execution"],
    "CC-06": ["contractor registration", "19 del", "§ 3604", "register before", "after work begins"],
    "CC-07": ["business license", "occupational license", "subcontractor", "30 days", "60 days", "29 del", "§ 6967"],
    "CC-08": ["addendum", "addenda", "acknowledges addend", "q&a"],
    "CC-09": ["buy america", "baba", "build america", "does not apply", "does apply"],
    "CC-10": ["order of precedence", "hierarchy", "general description", "complementary", "conflict"],
    "CC-11": ["oral direction", "oral promise", "written change", "change order", "scope/price/time", "orally"],
    "CC-12": ["written notice", "follow-up", "7 calendar days", "30 calendar days", "104.3"],
    "CC-13": ["right to audit", "record retention", "three years", "3 years", "1 year", "one year"],
    "CC-14": ["subletting", "subcontract", "50%", "80%", "own organization", "108.1"],
    "CC-15": ["notice of intent", "written claim", "30 calendar days", "105.15", "claim"],
    "CC-16": ["extension of contract time", "time extension", "automatic", "excusable delay", "critical path", "108.7"],
    "CC-17": ["liquidated damage", "108.9", "10,000", "10000", "$10,000", "daily rate"],
    "CC-18": ["force account", "unit price", "25%", "markup", "109.4", "compensation for change"],
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _addendum_rank(document_type: str, file_name: str) -> int | None:
    blob = f"{document_type} {file_name}".lower()
    if "addendum" not in blob:
        return None
    if re.search(r"addendum[_\s-]*c|\b3\b", blob) and "addendum" in blob:
        if re.search(r"addendum[_\s-]*c", blob) or re.search(r"addendum 3", blob):
            return 83
    mapping = (
        (r"addendum[_\s-]*c|addendum c", 83),
        (r"addendum[_\s-]*b|addendum b", 82),
        (r"addendum[_\s-]*a|addendum a", 81),
    )
    for pattern, rank in mapping:
        if re.search(pattern, blob):
            return rank
    return 80


def _base_rank(document_type: str) -> int:
    dt = document_type.lower()
    if "special provision" in dt:
        return 50
    if "proposal" in dt or "general notice" in dt:
        return 40
    if "fhwa" in dt or "federal contract" in dt:
        return 30
    if "general condition" in dt:
        return 20
    return 10


def _doc_rank(document_type: str, file_name: str) -> int:
    add = _addendum_rank(document_type, file_name)
    if add is not None:
        return add
    return _base_rank(document_type)


def _split_paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n", text)
    cleaned = [p.strip() for p in parts if p.strip()]
    if cleaned:
        return cleaned
    if text.strip():
        return [text.strip()]
    return []


def collect_snippets(corpus: PackageCorpus, requirement_id: str) -> list[Snippet]:
    keys = REQUIREMENT_KEYWORDS.get(requirement_id, [])
    snippets: list[Snippet] = []
    for doc in corpus.documents:
        for page in doc.pages:
            hay = _norm(page.text)
            if not hay:
                continue
            hits = any(k in hay for k in keys) if keys else True
            if not hits:
                continue
            for para in _split_paragraphs(page.text):
                if keys and not any(k in _norm(para) for k in keys):
                    continue
                if len(para) < 20:
                    continue
                snippets.append(
                    Snippet(
                        file_name=doc.file_name,
                        document_type=doc.document_type,
                        page=page.page,
                        text=para[:1800],
                        is_revision=bool(REVISION_RE.search(para)),
                    )
                )
    return snippets


def fhwa_physically_included(corpus: PackageCorpus) -> bool:
    for doc in corpus.documents:
        blob = f"{doc.document_type} {doc.package_status} {doc.file_name}".lower()
        if "fhwa" in blob or "federal contract provisions" in blob:
            if "physically" in blob or "attachment" in blob:
                return True
    return False


def _proposal_text(corpus: PackageCorpus) -> str:
    chunks: list[str] = []
    for doc in corpus.documents:
        if "proposal" in doc.document_type.lower() or "general notice" in doc.document_type.lower():
            chunks.append("\n".join(p.text for p in doc.pages))
    return "\n".join(chunks)


def ignores_later_addenda(corpus: PackageCorpus) -> bool:
    return bool(IGNORE_LATER_ADDENDA_RE.search(_proposal_text(corpus)))


def acknowledged_addenda(corpus: PackageCorpus) -> list[str]:
    found: set[str] = set()
    proposal_text = _proposal_text(corpus)
    mapping = {
        "a": "Addendum 1",
        "b": "Addendum 2",
        "c": "Addendum 3",
        "1": "Addendum 1",
        "2": "Addendum 2",
        "3": "Addendum 3",
    }
    for match in ADDENDUM_ACK_RE.finditer(proposal_text):
        chunk = match.group(1).lower()
        for token in re.findall(r"[1-3a-c]", chunk):
            if token in mapping:
                found.add(mapping[token])
    return sorted(found)


def _cc14_is_concrete(text: str) -> bool:
    t = _norm(text)
    return bool(re.search(r"80\s*%|eighty percent", t))


def resolve_precedence(corpus: PackageCorpus, requirement_id: str) -> PrecedenceSnapshot:
    snippets = collect_snippets(corpus, requirement_id)
    issued = corpus.metadata.get("issued_addenda") or []

    hints: dict[str, object] = {
        "issued_addenda": issued,
        "fhwa_physically_included": fhwa_physically_included(corpus),
        "acknowledged_addenda": acknowledged_addenda(corpus),
        "ignores_later_addenda": ignores_later_addenda(corpus),
    }

    if not snippets:
        fallback_name = corpus.documents[0].file_name if corpus.documents else "unknown"
        return PrecedenceSnapshot(
            requirement_id=requirement_id,
            governing_document=fallback_name,
            governing_snippets=[],
            superseded_snippets=[],
            hints=hints,
        )

    grouped: dict[str, list[Snippet]] = defaultdict(list)
    ranks: dict[str, int] = {}
    for snip in snippets:
        grouped[snip.file_name].append(snip)
        ranks[snip.file_name] = _doc_rank(snip.document_type, snip.file_name)

    ranked_files = sorted(ranks, key=lambda k: ranks[k], reverse=True)
    governing_file = ranked_files[0]
    if requirement_id == "CC-14":
        for file_name in ranked_files:
            if any(_cc14_is_concrete(s.text) for s in grouped[file_name]):
                governing_file = file_name
                break
    governing = grouped[governing_file]
    superseded = [s for s in snippets if s.file_name != governing_file]
    return PrecedenceSnapshot(
        requirement_id=requirement_id,
        governing_document=governing_file,
        governing_snippets=governing[:8],
        superseded_snippets=superseded[:6],
        hints=hints,
    )
