from pathlib import Path

from ccrf.apply import decide_applicability
from ccrf.config import REQUIREMENT_IDS, REPO_ROOT
from ccrf.ingest import discover_packages, iter_label_rows, load_metadata


def test_eighteen_requirement_ids():
    assert REQUIREMENT_IDS == [f"CC-{i:02d}" for i in range(1, 19)]


def test_applicability_matches_development_labels():
    labels = list(iter_label_rows(REPO_ROOT / "Development" / "Development_Labels.csv"))
    packages = {}
    for path in discover_packages(REPO_ROOT / "Development"):
        meta = load_metadata(path)
        packages[meta["package_id"]] = meta
    assert len(packages) == 6
    misses = []
    for row in labels:
        decision, _reason = decide_applicability(row["Requirement_ID"], packages[row["Package_ID"]])
        if decision != row["Expected_Applicability"]:
            misses.append((row["Package_ID"], row["Requirement_ID"], decision, row["Expected_Applicability"]))
    assert not misses, misses
    assert len(labels) == 6 * 18
