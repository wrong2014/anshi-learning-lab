from __future__ import annotations

import json
import math
import re
import sqlite3
import unicodedata
from array import array
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .embeddings import EmbeddingBackend
from .retrieval_models import (
    NormalizedCorpus,
    RetrievalHit,
    RetrievalQuery,
    RetrievalResponse,
    RetrievalUnit,
)


INDEX_SCHEMA_VERSION = "1.0"
RRF_K = 60


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tokens(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).lower()
    result: set[str] = set(re.findall(r"[a-z0-9_+\-./]+", normalized))
    for chunk in re.findall(r"[\u3400-\u9fff]+", normalized):
        if len(chunk) == 1:
            result.add(chunk)
        else:
            result.update(chunk[index : index + 2] for index in range(len(chunk) - 1))
    return sorted(token for token in result if token)


def _fts_query(text: str) -> str:
    escaped = [token.replace('"', '""') for token in _tokens(text)]
    return " OR ".join(f'"{token}"' for token in escaped)


def _vector_blob(vector: list[float]) -> bytes:
    return array("f", vector).tobytes()


def _blob_vector(blob: bytes) -> array:
    result = array("f")
    result.frombytes(blob)
    return result


def _dot(left: Iterable[float], right: Iterable[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def build_material_index(
    corpus: NormalizedCorpus,
    output_path: str | Path,
    *,
    embedder: EmbeddingBackend | None = None,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    building_path = output_path.with_name(f"{output_path.name}.building")
    if building_path.exists():
        building_path.unlink()

    build_succeeded = False
    connection = sqlite3.connect(building_path)
    try:
        connection.executescript(
            """
            PRAGMA journal_mode=DELETE;
            CREATE TABLE metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE units (
                unit_id TEXT PRIMARY KEY,
                layer TEXT NOT NULL,
                unit_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                parent_id TEXT NOT NULL,
                source_artifact TEXT NOT NULL,
                source_path TEXT NOT NULL,
                material_version TEXT NOT NULL,
                approval_scope TEXT NOT NULL,
                safety_level TEXT NOT NULL,
                title TEXT NOT NULL,
                text TEXT NOT NULL,
                subject TEXT,
                grade_min INTEGER,
                grade_max INTEGER,
                actor TEXT,
                citations_json TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                embedding BLOB
            );
            CREATE INDEX idx_units_filters ON units(layer, subject, grade_min, grade_max, approval_scope, safety_level);
            CREATE INDEX idx_units_source ON units(source_id, parent_id);
            CREATE VIRTUAL TABLE unit_fts USING fts5(
                unit_id UNINDEXED,
                title,
                text,
                lexemes,
                tokenize='unicode61'
            );
            CREATE TABLE graph_edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                rationale TEXT NOT NULL,
                layer TEXT NOT NULL,
                source_artifact TEXT NOT NULL,
                source_path TEXT NOT NULL
            );
            CREATE INDEX idx_edges_source ON graph_edges(source_id);
            CREATE INDEX idx_edges_target ON graph_edges(target_id);
            """
        )

        vectors: list[list[float] | None]
        if embedder is None:
            vectors = [None] * len(corpus.units)
        else:
            vectors = embedder.embed_documents(
                [f"{unit.title}\n{unit.text}" for unit in corpus.units]
            )
            if len(vectors) != len(corpus.units):
                raise ValueError("embedding backend returned the wrong vector count")
            if any(len(vector) != embedder.dimension for vector in vectors):
                raise ValueError("embedding backend returned an unexpected dimension")

        for unit, vector in zip(corpus.units, vectors):
            connection.execute(
                """
                INSERT INTO units VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    unit.unit_id,
                    unit.layer,
                    unit.unit_type,
                    unit.source_id,
                    unit.parent_id,
                    unit.source_artifact,
                    unit.source_path,
                    unit.material_version,
                    unit.approval_scope,
                    unit.safety_level,
                    unit.title,
                    unit.text,
                    unit.subject,
                    unit.grade_min,
                    unit.grade_max,
                    unit.actor,
                    json.dumps(unit.citations, ensure_ascii=False, sort_keys=True),
                    json.dumps(unit.metadata, ensure_ascii=False, sort_keys=True),
                    _vector_blob(vector) if vector is not None else None,
                ),
            )
            connection.execute(
                "INSERT INTO unit_fts(unit_id, title, text, lexemes) VALUES (?, ?, ?, ?)",
                (
                    unit.unit_id,
                    unit.title,
                    unit.text,
                    " ".join(_tokens(f"{unit.title}\n{unit.text}")),
                ),
            )

        connection.executemany(
            """
            INSERT INTO graph_edges(source_id, target_id, relation_type, rationale, layer, source_artifact, source_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    edge.source_id,
                    edge.target_id,
                    edge.relation_type,
                    edge.rationale,
                    edge.layer,
                    edge.source_artifact,
                    edge.source_path,
                )
                for edge in corpus.edges
            ],
        )

        metadata = {
            "index_schema_version": INDEX_SCHEMA_VERSION,
            "built_at": _utc_now(),
            "embedding_model": embedder.model_id if embedder else "",
            "embedding_dimension": str(embedder.dimension if embedder else 0),
            "corpus_manifest": corpus.manifest.model_dump_json(),
            "unit_count": str(len(corpus.units)),
            "edge_count": str(len(corpus.edges)),
        }
        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)", metadata.items()
        )
        connection.commit()
        build_succeeded = True
    finally:
        connection.close()
        if not build_succeeded and building_path.exists():
            building_path.unlink()
    building_path.replace(output_path)
    return output_path.resolve()


class MaterialIndex:
    def __init__(
        self,
        index_path: str | Path,
        *,
        embedder: EmbeddingBackend | None = None,
    ) -> None:
        self.index_path = Path(index_path)
        self.embedder = embedder
        self.connection = sqlite3.connect(self.index_path)
        self.connection.row_factory = sqlite3.Row
        self.metadata = {
            row["key"]: row["value"]
            for row in self.connection.execute("SELECT key, value FROM metadata")
        }
        index_model = self.metadata.get("embedding_model") or None
        if embedder and index_model and embedder.model_id != index_model:
            raise ValueError(
                f"query embedder {embedder.model_id} does not match index model {index_model}"
            )

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "MaterialIndex":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def search(self, query: RetrievalQuery) -> RetrievalResponse:
        where_sql, params = self._filters(query)
        warnings: list[str] = []
        lexical = self._lexical(query.text, where_sql, params, max(query.top_k * 6, 40))
        vector: list[tuple[str, float]] = []
        index_model = self.metadata.get("embedding_model") or None
        if index_model and self.embedder:
            vector = self._vector(query.text, where_sql, params, max(query.top_k * 6, 40))
        elif index_model and not self.embedder:
            warnings.append("索引含语义向量，但本次未加载同版本 embedding 模型；已降级为文本检索。")

        combined: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"score": 0.0, "lexical": None, "vector": None, "matched_by": []}
        )
        for rank, (unit_id, score) in enumerate(lexical, start=1):
            combined[unit_id]["score"] += 0.45 / (RRF_K + rank)
            combined[unit_id]["lexical"] = score
            combined[unit_id]["matched_by"].append("lexical")
        for rank, (unit_id, score) in enumerate(vector, start=1):
            combined[unit_id]["score"] += 0.55 / (RRF_K + rank)
            combined[unit_id]["vector"] = score
            combined[unit_id]["matched_by"].append("vector")

        normalized_query = unicodedata.normalize("NFKC", query.text).lower().strip()
        if normalized_query:
            exact_rows = self.connection.execute(
                f"SELECT unit_id FROM units WHERE lower(title) = ? {where_sql}",
                [normalized_query, *params],
            ).fetchall()
            for row in exact_rows:
                combined[row["unit_id"]]["score"] += 0.02
                combined[row["unit_id"]]["matched_by"].append("exact")

        ranked_ids = sorted(
            combined, key=lambda unit_id: combined[unit_id]["score"], reverse=True
        )
        hits = [self._make_hit(unit_id, combined[unit_id]) for unit_id in ranked_ids]
        if query.include_graph_neighbors and query.graph_limit:
            hits = self._expand_graph(hits, query.graph_limit, where_sql, params)

        return RetrievalResponse(
            query=query,
            index_version=self.metadata.get("index_schema_version", "unknown"),
            embedding_model=index_model,
            hits=hits[: query.top_k],
            warnings=warnings,
        )

    def _filters(self, query: RetrievalQuery) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        for field, values in (
            ("subject", query.subjects),
            ("layer", query.layers),
            ("unit_type", query.unit_types),
            ("actor", query.actors),
            ("approval_scope", query.approval_scopes),
            ("safety_level", query.safety_levels),
        ):
            if values:
                clauses.append(f"AND units.{field} IN ({','.join('?' for _ in values)})")
                params.extend(values)
        if query.grade is not None:
            clauses.append("AND units.grade_min <= ? AND units.grade_max >= ?")
            params.extend([query.grade, query.grade])
        return (" " + " ".join(clauses)) if clauses else "", params

    def _lexical(
        self, text: str, where_sql: str, params: list[Any], limit: int
    ) -> list[tuple[str, float]]:
        match = _fts_query(text)
        if not match:
            return []
        rows = self.connection.execute(
            f"""
            SELECT units.unit_id, bm25(unit_fts, 0.0, 8.0, 1.0, 2.0) AS rank
            FROM unit_fts JOIN units ON units.unit_id = unit_fts.unit_id
            WHERE unit_fts MATCH ? {where_sql}
            ORDER BY rank ASC LIMIT ?
            """,
            [match, *params, limit],
        ).fetchall()
        return [(row["unit_id"], float(-row["rank"])) for row in rows]

    def _vector(
        self, text: str, where_sql: str, params: list[Any], limit: int
    ) -> list[tuple[str, float]]:
        if not self.embedder:
            return []
        query_vector = self.embedder.embed_query(text)
        expected = int(self.metadata.get("embedding_dimension", "0"))
        if len(query_vector) != expected:
            raise ValueError("query embedding dimension does not match index")
        rows = self.connection.execute(
            f"SELECT unit_id, embedding FROM units WHERE embedding IS NOT NULL {where_sql}",
            params,
        ).fetchall()
        ranked = [
            (row["unit_id"], _dot(query_vector, _blob_vector(row["embedding"])))
            for row in rows
        ]
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[:limit]

    def _make_hit(self, unit_id: str, scores: dict[str, Any]) -> RetrievalHit:
        row = self.connection.execute(
            "SELECT * FROM units WHERE unit_id = ?", (unit_id,)
        ).fetchone()
        if row is None:
            raise KeyError(unit_id)
        unit = self._row_to_unit(row)
        return RetrievalHit(
            unit=unit,
            score=float(scores["score"]),
            lexical_score=scores.get("lexical"),
            vector_score=scores.get("vector"),
            matched_by=list(dict.fromkeys(scores["matched_by"])),
        )

    def _expand_graph(
        self,
        hits: list[RetrievalHit],
        graph_limit: int,
        where_sql: str,
        params: list[Any],
    ) -> list[RetrievalHit]:
        if not hits:
            return hits
        existing = {hit.unit.unit_id for hit in hits}
        expanded = list(hits)
        added = 0
        for rank, hit in enumerate(hits[:5], start=1):
            if added >= graph_limit:
                break
            parent_id = hit.unit.parent_id
            edges = self.connection.execute(
                """
                SELECT source_id, target_id, relation_type FROM graph_edges
                WHERE source_id = ? OR target_id = ? LIMIT 20
                """,
                (parent_id, parent_id),
            ).fetchall()
            for edge in edges:
                neighbor_id = (
                    edge["target_id"] if edge["source_id"] == parent_id else edge["source_id"]
                )
                row = self.connection.execute(
                    f"""
                    SELECT * FROM units
                    WHERE source_id = ? AND unit_type IN (
                        'knowledge_point_overview',
                        'thinking_dimension_overview',
                        'psychology_dimension_overview'
                    ) {where_sql}
                    LIMIT 1
                    """,
                    [neighbor_id, *params],
                ).fetchone()
                if row is None:
                    continue
                if row["unit_id"] in existing:
                    for existing_hit in expanded:
                        if existing_hit.unit.unit_id == row["unit_id"]:
                            if "graph" not in existing_hit.matched_by:
                                existing_hit.matched_by.append("graph")
                            existing_hit.via_relation = existing_hit.via_relation or edge["relation_type"]
                            break
                    continue
                expanded.append(
                    RetrievalHit(
                        unit=self._row_to_unit(row),
                        score=max(hit.score * 0.55, 1e-8) / math.sqrt(rank),
                        matched_by=["graph"],
                        via_relation=edge["relation_type"],
                    )
                )
                existing.add(row["unit_id"])
                added += 1
                if added >= graph_limit:
                    break
        expanded.sort(key=lambda item: item.score, reverse=True)
        return expanded

    @staticmethod
    def _row_to_unit(row: sqlite3.Row) -> RetrievalUnit:
        return RetrievalUnit(
            unit_id=row["unit_id"],
            layer=row["layer"],
            unit_type=row["unit_type"],
            source_id=row["source_id"],
            parent_id=row["parent_id"],
            source_artifact=row["source_artifact"],
            source_path=row["source_path"],
            material_version=row["material_version"],
            approval_scope=row["approval_scope"],
            safety_level=row["safety_level"],
            title=row["title"],
            text=row["text"],
            subject=row["subject"],
            grade_min=row["grade_min"],
            grade_max=row["grade_max"],
            actor=row["actor"],
            citations=json.loads(row["citations_json"]),
            metadata=json.loads(row["metadata_json"]),
        )
