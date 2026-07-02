from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

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
    parser = argparse.ArgumentParser(description="Query the unified material index")
    parser.add_argument("query")
    parser.add_argument(
        "--index",
        type=Path,
        default=ROOT / "artifacts/retrieval/k9-material-index-v1.sqlite3",
    )
    parser.add_argument("--subject", action="append", default=[])
    parser.add_argument("--layer", action="append", default=[])
    parser.add_argument("--unit-type", action="append", default=[])
    parser.add_argument("--actor", action="append", default=[])
    parser.add_argument("--safety-level", action="append", default=[])
    parser.add_argument("--grade", type=int)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--lexical-only", action="store_true")
    parser.add_argument("--api-key-env", default="DASHSCOPE_API_KEY")
    parser.add_argument("--device", default=None)
    return parser.parse_args()


def _metadata(index_path: Path) -> dict[str, str]:
    connection = sqlite3.connect(index_path)
    try:
        return dict(connection.execute("SELECT key, value FROM metadata"))
    finally:
        connection.close()


def main() -> None:
    args = parse_args()
    load_env_file(ROOT / ".env")
    metadata = _metadata(args.index)
    model_id = metadata.get("embedding_model", "")
    embedder = None
    if not args.lexical_only and model_id.startswith("aliyun-dashscope/"):
        embedder = AliyunTextEmbeddingBackend.from_model_id(
            model_id, api_key_env=args.api_key_env
        )
    elif not args.lexical_only and model_id.startswith("BAAI/"):
        embedder = BgeTransformerEmbedder(model_id, device=args.device, local_files_only=True)
    elif not args.lexical_only and model_id.startswith("deterministic-char-ngram"):
        embedder = HashingEmbedder(int(metadata["embedding_dimension"]))

    query = RetrievalQuery(
        text=args.query,
        subjects=args.subject,
        grade=args.grade,
        layers=args.layer,
        unit_types=args.unit_type,
        actors=args.actor,
        safety_levels=args.safety_level,
        top_k=args.top_k,
    )
    with MaterialIndex(args.index, embedder=embedder) as index:
        response = index.search(query)
    print(response.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
