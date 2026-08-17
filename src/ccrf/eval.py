from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


def load_predictions(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def compare(
    predictions: list[dict[str, str]],
    labels: list[dict[str, str]],
) -> dict:
    label_map = {
        (r["Package_ID"], r["Requirement_ID"]): r for r in labels
    }
    pred_map = {
        (r["document_id"], r["requirement_id"]): r for r in predictions
    }

    applicability_ok = 0
    applicability_n = 0
    tp = fp = fn = tn = 0
    severity_ok = 0
    severity_n = 0
    mismatches: list[dict[str, str]] = []

    keys = sorted(set(label_map) | set(pred_map))
    missing_pred = [k for k in label_map if k not in pred_map]
    extra_pred = [k for k in pred_map if k not in label_map]

    for key in sorted(label_map):
        lab = label_map[key]
        pred = pred_map.get(key)
        if pred is None:
            mismatches.append(
                {
                    "package_id": key[0],
                    "requirement_id": key[1],
                    "issue": "missing_prediction",
                }
            )
            continue
        applicability_n += 1
        if pred["applicability_decision"] == lab["Expected_Applicability"]:
            applicability_ok += 1
        gold_flag = lab["Expected_Label"] == "FLAG"
        pred_flag = pred["predicted_label"] == "FLAG"
        if gold_flag and pred_flag:
            tp += 1
        elif pred_flag and not gold_flag:
            fp += 1
        elif gold_flag and not pred_flag:
            fn += 1
        else:
            tn += 1
        severity_n += 1
        if pred["severity"] == lab["Expected_Severity"]:
            severity_ok += 1
        if (
            pred["applicability_decision"] != lab["Expected_Applicability"]
            or pred["predicted_label"] != lab["Expected_Label"]
            or pred["severity"] != lab["Expected_Severity"]
        ):
            mismatches.append(
                {
                    "package_id": key[0],
                    "requirement_id": key[1],
                    "expected_applicability": lab["Expected_Applicability"],
                    "got_applicability": pred["applicability_decision"],
                    "expected_label": lab["Expected_Label"],
                    "got_label": pred["predicted_label"],
                    "expected_severity": lab["Expected_Severity"],
                    "got_severity": pred["severity"],
                    "rationale": lab.get("Rationale", ""),
                    "explanation": pred.get("explanation", ""),
                }
            )

    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    return {
        "n_labels": len(label_map),
        "n_predictions": len(pred_map),
        "missing_predictions": missing_pred,
        "extra_predictions": extra_pred,
        "applicability_accuracy": applicability_ok / applicability_n if applicability_n else 0.0,
        "flag_precision": precision,
        "flag_recall": recall,
        "severity_agreement": severity_ok / severity_n if severity_n else 0.0,
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "mismatches": mismatches,
    }


def format_report(stats: dict) -> str:
    lines = [
        f"labels={stats['n_labels']} predictions={stats['n_predictions']}",
        f"applicability_accuracy={stats['applicability_accuracy']:.3f}",
        f"flag_precision={stats['flag_precision']:.3f} flag_recall={stats['flag_recall']:.3f}",
        f"severity_agreement={stats['severity_agreement']:.3f}",
        f"confusion={stats['confusion']}",
    ]
    if stats["missing_predictions"]:
        lines.append(f"missing_predictions={stats['missing_predictions']}")
    mismatches = stats["mismatches"]
    by_pkg: dict[str, int] = defaultdict(int)
    for row in mismatches:
        by_pkg[row["package_id"]] += 1
    lines.append(f"mismatch_count={len(mismatches)} by_package={dict(by_pkg)}")
    for row in mismatches[:40]:
        lines.append(
            f"  {row.get('package_id')} {row.get('requirement_id')}: "
            f"app {row.get('got_applicability')} vs {row.get('expected_applicability')}; "
            f"label {row.get('got_label')} vs {row.get('expected_label')}; "
            f"sev {row.get('got_severity')} vs {row.get('expected_severity')} "
            f"| {row.get('rationale', row.get('issue', ''))}"
        )
    if len(mismatches) > 40:
        lines.append(f"  ... {len(mismatches) - 40} more")
    return "\n".join(lines)
