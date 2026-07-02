from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from learning_problem_factory.embeddings import (
    AliyunTextEmbeddingBackend,
    BgeTransformerEmbedder,
    HashingEmbedder,
)
from learning_problem_factory.env_utils import load_env_file
from learning_problem_factory.material_index import build_material_index
from learning_problem_factory.material_normalizer import normalize_materials


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the unified three-layer material index")
    parser.add_argument(
        "--knowledge",
        type=Path,
        default=ROOT / "artifacts/releases/curriculum-k9-stem-2022-v1.0.0.json",
    )
    parser.add_argument(
        "--core-thinking",
        type=Path,
        default=ROOT / "artifacts/reviews/core-thinking-k9-v1.0.0-ai-reviewed.json",
    )
    parser.add_argument(
        "--psychology",
        type=Path,
        default=ROOT / "artifacts/reviews/psychology-cognition-k9-v1.0.0-ai-reviewed.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts/retrieval/k9-material-index-v1.sqlite3",
    )
    parser.add_argument(
        "--embedding", choices=("aliyun", "bge", "hashing", "none"), default="aliyun"
    )
    parser.add_argument("--model", default=None)
    parser.add_argument("--dimension", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--api-key-env", default="DASHSCOPE_API_KEY")
    parser.add_argument("--device", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_env_file(ROOT / ".env")
    corpus = normalize_materials(args.knowledge, args.core_thinking, args.psychology)
    if args.embedding == "aliyun":
        model_name = args.model or os.getenv(
            "DASHSCOPE_EMBEDDING_MODEL", AliyunTextEmbeddingBackend.DEFAULT_MODEL
        )
        dimension = args.dimension or int(
            os.getenv("DASHSCOPE_EMBEDDING_DIMENSION", "1024")
        )
        embedder = AliyunTextEmbeddingBackend(
            api_key_env=args.api_key_env,
            model_name=model_name,
            dimension=dimension,
            batch_size=args.batch_size or 10,
        )
    elif args.embedding == "bge":
        embedder = BgeTransformerEmbedder(
            args.model or "BAAI/bge-small-zh-v1.5",
            batch_size=args.batch_size or 32,
            device=args.device,
        )
    elif args.embedding == "hashing":
        embedder = HashingEmbedder()
    else:
        embedder = None
    output = build_material_index(corpus, args.output, embedder=embedder)
    print(
        json.dumps(
            {
                "output": str(output),
                "units": len(corpus.units),
                "edges": len(corpus.edges),
                "unit_counts": corpus.manifest.unit_counts,
                "edge_counts": corpus.manifest.edge_counts,
                "embedding_model": embedder.model_id if embedder else None,
                "embedding_dimension": embedder.dimension if embedder else 0,
                "embedding_configured": (
                    embedder.configured
                    if isinstance(embedder, AliyunTextEmbeddingBackend)
                    else True
                ),
                "warnings": corpus.manifest.warnings,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
