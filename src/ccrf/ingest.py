from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterator

from ccrf.models import ChecklistRow, DocumentRef


def discover_packages(root: Path) -> list[Path]:
    packages: list[Path] = []
    for meta in sorted(root.rglob("Project_Metadata.json")):
        packages.append(meta.parent)
    return packages


def load_metadata(package_dir: Path) -> dict:
    path = package_dir / "Project_Metadata.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_document_index(package_dir: Path) -> list[DocumentRef]:
    index_path = package_dir / "Document_Index.csv"
    docs: list[DocumentRef] = []
    with index_path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            file_name = (row.get("File_Name") or "").strip()
            docs.append(
                DocumentRef(
                    file_name=file_name,
                    document_type=(row.get("Document_Type") or "").strip(),
                    package_status=(row.get("Package_Status") or "").strip(),
                    path=package_dir / "Docs" / file_name,
                )
            )
    return docs


def load_checklist(path: Path) -> dict[str, ChecklistRow]:
    rows: dict[str, ChecklistRow] = {}
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rid = row["Requirement_ID"].strip()
            rows[rid] = ChecklistRow(
                requirement_id=rid,
                name=row.get("Requirement_Name", "").strip(),
                reference_source=row.get("Reference_Source", "").strip(),
                section=row.get("Section", "").strip(),
                applicability_rule=row.get("Applicability_Rule", "").strip(),
                review_expectation=row.get("Review_Expectation", "").strip(),
                severity_guidance=row.get("Severity_Guidance", "").strip(),
                challenge_reference_rule=row.get("Challenge_Reference_Rule", "").strip(),
            )
    return rows


def load_severity_guidance(path: Path) -> str:
    lines = []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            lines.append(
                f"{row.get('level', '')}: {row.get('working_definition', '')}"
            )
    return "\n".join(lines)


def iter_label_rows(path: Path) -> Iterator[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        yield from csv.DictReader(fh)
