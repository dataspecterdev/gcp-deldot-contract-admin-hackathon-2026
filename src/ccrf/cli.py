from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from ccrf.apply import decide_applicability
from ccrf.config import GCP_LOCATION, GCP_PROJECT, GEMINI_MODEL, REPO_ROOT
from ccrf.eval import compare, format_report, load_predictions
from ccrf.export import write_submission
from ccrf.extract import extract_package
from ccrf.ingest import discover_packages, iter_label_rows, load_metadata
from ccrf.pipeline import review_root


def _cmd_extract(args: argparse.Namespace) -> int:
    root = Path(args.root)
    for package_dir in discover_packages(root):
        corpus = extract_package(package_dir)
        pages = sum(len(d.pages) for d in corpus.documents)
        print(f"extracted {corpus.package_id}: {len(corpus.documents)} docs, {pages} pages")
    return 0


def _cmd_eval_applicability(args: argparse.Namespace) -> int:
    labels = list(iter_label_rows(Path(args.labels)))
    packages = {load_metadata(p)["package_id"]: load_metadata(p) for p in discover_packages(Path(args.root))}
    ok = 0
    n = 0
    misses = []
    for row in labels:
        n += 1
        meta = packages[row["Package_ID"]]
        decision, reason = decide_applicability(row["Requirement_ID"], meta)
        if decision == row["Expected_Applicability"]:
            ok += 1
        else:
            misses.append(
                f"{row['Package_ID']} {row['Requirement_ID']}: got {decision} "
                f"expected {row['Expected_Applicability']} ({reason})"
            )
    print(f"applicability {ok}/{n} = {ok / n if n else 0:.3f}")
    for line in misses:
        print("  ", line)
    return 0 if ok == n else 1


def _cmd_run(args: argparse.Namespace) -> int:
    from ccrf.review import get_client

    if args.rag:
        os.environ["CCRF_USE_RAG"] = "1"
    print(f"Vertex project={GCP_PROJECT} location={GCP_LOCATION} model={GEMINI_MODEL}")
    client = get_client()
    findings = review_root(Path(args.root), client=client)
    write_submission(Path(args.out), findings)
    print(f"wrote {len(findings)} rows -> {args.out}")
    return 0


def _cmd_rag_index(args: argparse.Namespace) -> int:
    from ccrf.rag import index_root

    os.environ["CCRF_USE_RAG"] = "1"
    print(f"Indexing {args.root} into Vertex RAG Engine (project={GCP_PROJECT})")
    index_root(Path(args.root))
    return 0


def _cmd_eval(args: argparse.Namespace) -> int:
    preds = load_predictions(Path(args.pred))
    labels = list(iter_label_rows(Path(args.labels)))
    stats = compare(preds, labels)
    print(format_report(stats))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(stats, indent=2, default=str), encoding="utf-8")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ccrf")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ex = sub.add_parser("extract", help="pypdf extract + cache package corpora")
    p_ex.add_argument("--root", default=str(REPO_ROOT / "Development"))
    p_ex.set_defaults(func=_cmd_extract)

    p_app = sub.add_parser("eval-applicability", help="score metadata rules vs labels (no Gemini)")
    p_app.add_argument("--root", default=str(REPO_ROOT / "Development"))
    p_app.add_argument("--labels", default=str(REPO_ROOT / "Development" / "Development_Labels.csv"))
    p_app.set_defaults(func=_cmd_eval_applicability)

    p_run = sub.add_parser("run", help="review packages with Vertex Gemini Flash")
    p_run.add_argument("--root", default=str(REPO_ROOT / "Development"))
    p_run.add_argument("--out", default=str(REPO_ROOT / "runs" / "development_results.csv"))
    p_run.add_argument("--rag", action="store_true", help="retrieve extra evidence from Vertex RAG Engine")
    p_run.set_defaults(func=_cmd_run)

    p_rag = sub.add_parser("rag-index", help="upload package PDFs into Vertex RAG Engine (Google RAG)")
    p_rag.add_argument("--root", default=str(REPO_ROOT / "Development"))
    p_rag.set_defaults(func=_cmd_rag_index)

    p_eval = sub.add_parser("eval", help="compare a submission CSV to development labels")
    p_eval.add_argument("--pred", required=True)
    p_eval.add_argument("--labels", default=str(REPO_ROOT / "Development" / "Development_Labels.csv"))
    p_eval.add_argument("--out", default=str(REPO_ROOT / "runs" / "eval_report.json"))
    p_eval.set_defaults(func=_cmd_eval)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
