from __future__ import annotations

import json
from pathlib import Path

from pypdf import PdfReader

from ccrf.config import CACHE_DIR
from ccrf.ingest import load_document_index, load_metadata
from ccrf.models import ExtractedDocument, PackageCorpus, PageText


def extract_pdf(path: Path) -> list[PageText]:
    reader = PdfReader(str(path))
    pages: list[PageText] = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(PageText(page=i, text=text.strip()))
    return pages


def extract_package(package_dir: Path, *, cache_dir: Path | None = None) -> PackageCorpus:
    cache_dir = cache_dir or CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    metadata = load_metadata(package_dir)
    package_id = metadata["package_id"]
    cache_path = cache_dir / f"{package_id}.json"
    if cache_path.exists():
        return corpus_from_json(cache_path)

    documents: list[ExtractedDocument] = []
    for ref in load_document_index(package_dir):
        if not ref.path.exists():
            raise FileNotFoundError(f"Missing PDF {ref.path}")
        documents.append(
            ExtractedDocument(
                file_name=ref.file_name,
                document_type=ref.document_type,
                package_status=ref.package_status,
                pages=extract_pdf(ref.path),
            )
        )
    corpus = PackageCorpus(package_id=package_id, metadata=metadata, documents=documents)
    cache_path.write_text(json.dumps(corpus_to_json(corpus), indent=2), encoding="utf-8")
    return corpus


def corpus_to_json(corpus: PackageCorpus) -> dict:
    return {
        "package_id": corpus.package_id,
        "metadata": corpus.metadata,
        "documents": [
            {
                "file_name": doc.file_name,
                "document_type": doc.document_type,
                "package_status": doc.package_status,
                "pages": [{"page": p.page, "text": p.text} for p in doc.pages],
            }
            for doc in corpus.documents
        ],
    }


def corpus_from_json(path: Path) -> PackageCorpus:
    raw = json.loads(path.read_text(encoding="utf-8"))
    documents = [
        ExtractedDocument(
            file_name=d["file_name"],
            document_type=d["document_type"],
            package_status=d["package_status"],
            pages=[PageText(page=p["page"], text=p["text"]) for p in d["pages"]],
        )
        for d in raw["documents"]
    ]
    return PackageCorpus(
        package_id=raw["package_id"],
        metadata=raw["metadata"],
        documents=documents,
    )
