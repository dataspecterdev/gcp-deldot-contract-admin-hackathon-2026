"""Vertex AI RAG Engine — Google analogue of Azure AI Search / AWS Bedrock Knowledge Bases.

Retrieves contract-package chunks per requirement. Keyword/pypdf snippets remain
the fallback so scoring still works if RAG is not indexed.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ccrf.config import CACHE_DIR, GCP_LOCATION, GCP_PROJECT, REPO_ROOT
from ccrf.ingest import discover_packages, load_document_index, load_metadata
from ccrf.models import PackageCorpus, Snippet
from ccrf.precedence import REQUIREMENT_KEYWORDS

INDEX_PATH = Path(os.environ.get("CCRF_RAG_INDEX", REPO_ROOT / ".cache" / "rag_index.json"))


def rag_enabled() -> bool:
    flag = os.environ.get("CCRF_USE_RAG", "").strip().lower()
    if flag in {"0", "false", "no"}:
        return False
    if flag in {"1", "true", "yes"}:
        return True
    return INDEX_PATH.exists()


def _save_index(data: dict) -> None:
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _load_index() -> dict:
    if not INDEX_PATH.exists():
        return {}
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


_SERVERLESS_READY = False


def _rag():
    # Preview SDK is required for Serverless mode in us-central1 (Spanner is allowlisted).
    from vertexai.preview import rag

    return rag


def _init_vertex():
    import vertexai

    vertexai.init(project=GCP_PROJECT, location=GCP_LOCATION)


def _engine_mode_name() -> str | None:
    rag = _rag()
    name = f"projects/{GCP_PROJECT}/locations/{GCP_LOCATION}/ragEngineConfig"
    cfg = rag.get_rag_engine_config(name=name)
    mode = getattr(getattr(cfg, "rag_managed_db_config", None), "mode", None)
    return type(mode).__name__ if mode is not None else None


def _patch_engine_serverless() -> str:
    """PATCH RagEngineConfig to serverless (v1beta1); returns raw response body."""
    import google.auth
    import google.auth.transport.requests
    import urllib.request

    creds, _ = google.auth.default()
    creds.refresh(google.auth.transport.requests.Request())
    url = (
        f"https://{GCP_LOCATION}-aiplatform.googleapis.com/v1beta1/"
        f"projects/{GCP_PROJECT}/locations/{GCP_LOCATION}/ragEngineConfig"
    )
    body = b'{"ragManagedDbConfig": {"serverless": {}}}'
    req = urllib.request.Request(
        url,
        data=body,
        method="PATCH",
        headers={
            "Authorization": f"Bearer {creds.token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = resp.read().decode("utf-8")
        print(f"RAG Engine PATCH serverless HTTP {resp.status}: {payload[:800]}")
        return payload


def ensure_serverless_rag_engine() -> None:
    """Hackathon GCP projects are blocked from Spanner RAG in us-central1; use serverless."""
    global _SERVERLESS_READY
    if _SERVERLESS_READY:
        return
    import time

    _init_vertex()
    try:
        mode = _engine_mode_name()
        print(f"RAG engine current mode={mode}")
        if mode == "Serverless":
            _SERVERLESS_READY = True
            return
    except Exception as exc:
        print(f"RAG get_rag_engine_config warning: {exc}")

    patch_err = None
    try:
        _patch_engine_serverless()
    except Exception as exc:
        patch_err = exc
        print(f"RAG REST serverless PATCH failed: {exc}")
        rag = _rag()
        name = f"projects/{GCP_PROJECT}/locations/{GCP_LOCATION}/ragEngineConfig"
        print("RAG trying SDK update_rag_engine_config(Serverless)")
        rag.update_rag_engine_config(
            rag_engine_config=rag.RagEngineConfig(
                name=name,
                rag_managed_db_config=rag.RagManagedDbConfig(mode=rag.Serverless()),
            )
        )

    last_mode = None
    for attempt in range(12):
        try:
            last_mode = _engine_mode_name()
            print(f"RAG engine mode after switch attempt {attempt + 1}: {last_mode}")
            if last_mode == "Serverless":
                _SERVERLESS_READY = True
                return
        except Exception as exc:
            print(f"RAG poll mode warning: {exc}")
        time.sleep(5)

    raise RuntimeError(
        f"RAG Engine did not enter Serverless mode (last={last_mode}). "
        f"REST PATCH error: {patch_err}"
    )


def _corpus_display_name(package_id: str) -> str:
    return f"ccrf-{package_id}".lower().replace("_", "-")[:63]


def get_or_create_corpus(package_id: str) -> str:
    rag = _rag()
    _init_vertex()
    ensure_serverless_rag_engine()
    wanted = _corpus_display_name(package_id)
    index = _load_index()
    cached = (index.get(package_id) or {}).get("corpus_name")
    if cached:
        return cached
    try:
        for corpus in rag.list_corpora():
            if getattr(corpus, "display_name", "") == wanted:
                index[package_id] = {
                    **(index.get(package_id) or {}),
                    "corpus_name": corpus.name,
                }
                _save_index(index)
                return corpus.name
    except Exception as exc:
        print(f"RAG list_corpora warning: {exc}")
    created = rag.create_corpus(display_name=wanted, description=f"CCRF package {package_id}")
    index[package_id] = {"corpus_name": created.name, "files": []}
    _save_index(index)
    return created.name


def index_package(package_dir: Path, *, force: bool = False) -> str:
    rag = _rag()

    metadata = load_metadata(package_dir)
    package_id = metadata["package_id"]
    corpus_name = get_or_create_corpus(package_id)
    existing: set[str] = set()
    try:
        rag_files = list(rag.list_files(corpus_name=corpus_name))
        if force:
            for rag_file in rag_files:
                print(f"RAG delete {getattr(rag_file, 'display_name', rag_file.name)}")
                rag.delete_file(name=rag_file.name, corpus_name=corpus_name)
            rag_files = []
        existing = {getattr(f, "display_name", "") or "" for f in rag_files}
    except Exception as exc:
        print(f"RAG list_files warning: {exc}")

    uploaded: list[str] = []
    for ref in load_document_index(package_dir):
        if not ref.path.exists():
            continue
        display = f"{package_id}__{ref.file_name}"
        if display in existing or ref.file_name in existing:
            continue
        print(f"RAG upload {display}")
        try:
            rag.upload_file(
                corpus_name=corpus_name,
                path=str(ref.path),
                display_name=display,
                description=ref.document_type,
                transformation_config=rag.TransformationConfig(
                    chunking_config=rag.ChunkingConfig(chunk_size=1024, chunk_overlap=150)
                ),
            )
            uploaded.append(display)
        except Exception as exc:
            print(f"RAG upload failed {display}: {exc}")

    index = _load_index()
    prior = index.get(package_id) or {}
    files = sorted(set(prior.get("files") or []) | existing | set(uploaded))
    index[package_id] = {"corpus_name": corpus_name, "files": files}
    _save_index(index)
    print(f"RAG indexed {package_id}: corpus={corpus_name} files={len(files)}")
    return corpus_name


def index_root(root: Path, *, force: bool = False) -> None:
    ensure_serverless_rag_engine()
    for package_dir in discover_packages(root):
        try:
            index_package(package_dir, force=force)
        except Exception as exc:
            print(f"RAG index failed for {package_dir}: {exc}")


def _retrieval_query(corpus_name: str, text: str, top_k: int) -> list[Any]:
    rag = _rag()
    _init_vertex()
    resource = rag.RagResource(rag_corpus=corpus_name)
    response = rag.retrieval_query(
        text=text,
        rag_resources=[resource],
        rag_retrieval_config=rag.RagRetrievalConfig(top_k=top_k),
    )
    contexts = getattr(response, "contexts", None)
    if contexts is None:
        return []
    inner = getattr(contexts, "contexts", contexts)
    return list(inner or [])


_HEADER_MARKERS = (
    "sample contract document",
    "sample material - not an executed",
    "for evaluation use only",
    "contract clause risk flagging",
    "sample attachment for contract-package evaluation",
)


def strip_boilerplate(text: str) -> str:
    """Drop challenge cover-page lines so retrieval is judged on clause text."""
    kept: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        low = line.lower()
        if any(marker in low for marker in _HEADER_MARKERS):
            continue
        if low.startswith("dev-") and "page" in low:
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def snippet_relevant(text: str, requirement_id: str) -> bool:
    keys = REQUIREMENT_KEYWORDS.get(requirement_id, [])
    if not keys:
        return len(text) >= 80
    hay = " ".join((text or "").lower().split())
    hay = hay.replace("percent", "%").replace("per cent", "%")
    for key in keys:
        needle = " ".join(key.lower().split()).replace("percent", "%").replace("per cent", "%")
        if needle and needle in hay:
            return True
        compact = needle.replace(" ", "")
        if compact and compact in hay.replace(" ", ""):
            return True
    return False


def build_retrieval_query(
    requirement_id: str,
    checklist_name: str = "",
    challenge_rule: str = "",
) -> str:
    keys = REQUIREMENT_KEYWORDS.get(requirement_id, [])
    rule = " ".join((challenge_rule or "").split())[:240]
    parts = [requirement_id, checklist_name, *keys[:10], rule]
    return " ".join(p for p in parts if p).strip()


def retrieve_snippets(
    package_id: str,
    requirement_id: str,
    checklist_name: str = "",
    *,
    challenge_rule: str = "",
    top_k: int = 4,
    fetch_k: int = 12,
) -> list[Snippet]:
    index = _load_index()
    corpus_name = (index.get(package_id) or {}).get("corpus_name")
    if not corpus_name:
        return []
    query = build_retrieval_query(requirement_id, checklist_name, challenge_rule)
    try:
        contexts = _retrieval_query(corpus_name, query, fetch_k)
    except Exception as exc:
        print(f"RAG retrieve failed for {package_id} {requirement_id}: {exc}")
        return []

    snippets: list[Snippet] = []
    for ctx in contexts:
        raw = (getattr(ctx, "text", None) or getattr(ctx, "content", None) or "").strip()
        text = strip_boilerplate(raw) or raw
        if len(text) < 40:
            continue
        if not snippet_relevant(text, requirement_id):
            continue
        source = (
            getattr(ctx, "source_display_name", None)
            or getattr(ctx, "source_uri", None)
            or "vertex_rag"
        )
        file_name = Path(str(source)).name
        if "__" in file_name:
            file_name = file_name.split("__", 1)[-1]
        snippets.append(
            Snippet(
                file_name=file_name,
                document_type="Vertex RAG",
                page=0,
                text=text[:1800],
                is_revision=False,
            )
        )
        if len(snippets) >= top_k:
            break
    return snippets


def _norm_snippet_text(text: str) -> str:
    return " ".join((text or "").lower().split())


def _snippets_overlap(left: str, right: str, *, min_prefix: int = 80) -> bool:
    """True when texts match, one contains the other, or they share a long prefix."""
    if not left or not right:
        return False
    if left == right or left in right or right in left:
        return True
    n = min(len(left), len(right), min_prefix)
    return n >= 40 and left[:n] == right[:n]


def merge_rag_snippets(keyword_snips: list[Snippet], rag_snips: list[Snippet]) -> list[Snippet]:
    merged = list(keyword_snips)
    seen = [_norm_snippet_text(s.text) for s in merged]
    for snip in rag_snips:
        key = _norm_snippet_text(snip.text)
        if any(_snippets_overlap(key, prior) for prior in seen):
            continue
        seen.append(key)
        merged.append(snip)
    return merged
