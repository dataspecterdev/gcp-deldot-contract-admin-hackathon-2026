from __future__ import annotations

import csv
from pathlib import Path

from ccrf.config import SUBMISSION_FIELDS
from ccrf.models import Finding


def write_submission(path: Path, findings: list[Finding]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=SUBMISSION_FIELDS)
        writer.writeheader()
        for finding in findings:
            writer.writerow(finding.as_row())
