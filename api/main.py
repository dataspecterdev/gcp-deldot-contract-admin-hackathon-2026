"""Cloud Run demo API around the same clause-flagging engine as the CLI."""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from ccrf.ingest import discover_packages
from ccrf.pipeline import review_package
from ccrf.review import get_client

app = FastAPI(
    title="GCP DelDOT Contract Clause Risk Flagging",
    description=(
        "Flags missing, modified, conflicting, or non-standard contract clauses "
        "(CC-01..CC-18) for human review. Decision support only — not legal advice."
    ),
    version="0.1.0",
)


@app.get("/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/packages/review")
async def review_zip(file: UploadFile = File(...)) -> JSONResponse:
    """Accept a zip of one challenge package (Project_Metadata.json + Docs/)."""
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Upload a .zip of one contract package")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty upload")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "pkg"
        root.mkdir()
        zip_path = Path(tmp) / "upload.zip"
        zip_path.write_bytes(raw)
        try:
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(root)
        except zipfile.BadZipFile as exc:
            raise HTTPException(status_code=400, detail="Not a valid zip file") from exc
        packages = discover_packages(root)
        if not packages:
            raise HTTPException(
                status_code=400,
                detail="Zip must contain a folder with Project_Metadata.json and Docs/",
            )
        client = get_client()
        findings = review_package(packages[0], client=client)
        return JSONResponse(
            {
                "document_id": findings[0].document_id if findings else "",
                "findings": [f.as_row() for f in findings],
            }
        )
