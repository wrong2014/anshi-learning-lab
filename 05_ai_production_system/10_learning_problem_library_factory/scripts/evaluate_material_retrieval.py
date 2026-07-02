from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from learning_problem_factory.embeddings import (
    AliyunTextEmbeddingBackend,
    BgeTransformerEmbedder,
    HashingEmbedder,
)
from learning_problem_factory.env_utils import load_env_file
from learning_problem_factory.material_index import MaterialIndex
from learning_problem_factory.retrieval_models import RetrievalQuery


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run traceable retrieval gold cases")
    parser.add_argument(
        "--index",
        type=Path,
        default=ROOT / "artifacts/retrieval/k9-material-index-v1.sqlite3",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=ROOT / "data/retrieval_gold_cases.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts/retrieval/k9-material-index-v1-evaluation.json",
    )
    parser.add_argument("--device", default=None)
    parser.add_argument("--api-key-env", default="DASHSCOPE_API_KEY")
    return parser.parse_args()


def _metadata(index_path: Path) -> dict[str, str]:
    connection = sqlite3.connect(index_path)
    try:
        return dict(connection.execute("SELECT key, value FROM metadata"))
    finally:
        connection.close()


def _embedder(
    metadata: dict[str, str], device: str | None, api_key_env: str
) -> Any:
    model_id = metadata.get("embedding_model", "")
    if model_id.startswith("aliyun-dashscope/"):
        return AliyunTextEmbeddingBackend.from_model_id(
            model_id, api_key_env=api_key_env
        )
    if model_id.startswith("BAAI/"):
        return BgeTransformerEmbedder(model_id, device=device, local_files_only=True)
    if model_id.startswith("deterministic-char-ngram"):
        return HashingEmbedder(int(metadata["embedding_dimension"]))
    return None


def main() -> None:
    args = parse_args()
    load_env_file(ROOT / ".env")
    metadata = _metadata(args.index)
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = []
    embedder = _embedder(metadata, args.device, args.api_key_env)
    with MaterialIndex(args.index, embedder=embedder) as index:
        for case in cases:
            max_rank = int(case["max_rank"])
            query = RetrievalQuery(
                text=case["query"],
                top_k=max(max_rank, 8),
                include_graph_neighbors=False,
                **case.get("filters", {}),
            )
            response = index.search(query)
            expected = set(case["expected_parent_ids"])
            observed_rank = next(
                (
                    rank
                    for rank, hit in enumerate(response.hits, start=1)
                    if hit.unit.parent_id in expected
                ),
                None,
            )
            passed = observed_rank is not None and observed_rank <= max_rank
            results.append(
                {
                    "id": case["id"],
                    "passed": passed,
                    "observed_rank": observed_rank,
                    "max_rank": max_rank,
                    "expected_parent_ids": sorted(expected),
                    "top_hits": [
                        {
                            "rank": rank,
                            "unit_id": hit.unit.unit_id,
                            "parent_id": hit.unit.parent_id,
                            "title": hit.unit.title,
                            "source_artifact": hit.unit.source_artifact,
                            "source_path": hit.unit.source_path,
                            "matched_by": hit.matched_by,
                            "vector_score": hit.vector_score,
                        }
                        for rank, hit in enumerate(response.hits[:5], start=1)
                    ],
                }
            )

    report = {
        "index": str(args.index.resolve()),
        "embedding_model": metadata.get("embedding_model") or None,
        "case_count": len(results),
        "passed": sum(result["passed"] for result in results),
        "failed": sum(not result["passed"] for result in results),
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
