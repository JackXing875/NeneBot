"""Run deterministic quality checks for the active Nene dataset and retrieval stack."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_REPORT_PATH = PROJECT_ROOT / "data" / "processed" / "nene_quality_report.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate Nene dataset and retrieval quality.")
    parser.add_argument("--dataset", default="")
    parser.add_argument("--baseline-dataset", default="")
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--live", action="store_true")
    return parser


def main() -> None:
    from src.core.config import settings
    from src.evaluation.nene_quality import (
        compare_dataset_summaries,
        evaluate_retrieval,
        render_report,
        run_live_evaluation,
        summarize_dataset,
    )
    from src.infrastructure.vector_store.faiss_impl import FaissVectorStore
    from src.runtime import create_llm_client
    from src.services.embedding_svc import EmbeddingService
    from src.services.rag_pipeline import RAGPipeline

    args = build_parser().parse_args()
    dataset_path = Path(args.dataset or settings.data_path)
    baseline_path = Path(args.baseline_dataset) if args.baseline_dataset else None

    current_summary = summarize_dataset(dataset_path)
    baseline_summary: dict[str, Any] | None = None
    delta_summary: dict[str, Any] | None = None

    embedding_svc = EmbeddingService()
    vector_store = FaissVectorStore(
        dimension=settings.vector_dim,
        index_path=settings.vector_index_path,
        meta_path=settings.knowledge_meta_path,
    )
    rag = RAGPipeline(vector_store=vector_store, embedding_svc=embedding_svc)

    if baseline_path is not None:
        baseline_summary = summarize_dataset(baseline_path)
        delta_summary = compare_dataset_summaries(current_summary, baseline_summary)

    report: dict[str, Any] = {
        "current_dataset": current_summary,
        "retrieval": evaluate_retrieval(rag, top_k=args.top_k),
    }
    if baseline_summary is not None and delta_summary is not None:
        report["baseline_dataset"] = baseline_summary
        report["dataset_delta"] = delta_summary

    if args.live:
        llm = create_llm_client()
        report["live_replies"] = run_live_evaluation(rag, llm, top_k=args.top_k)

    report_text = render_report(report)
    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text + "\n", encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nReport written to: {report_path}")


if __name__ == "__main__":
    main()
