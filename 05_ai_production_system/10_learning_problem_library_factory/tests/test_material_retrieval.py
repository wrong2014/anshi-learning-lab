from __future__ import annotations

from learning_problem_factory.embeddings import HashingEmbedder
from learning_problem_factory.material_index import MaterialIndex, build_material_index
from learning_problem_factory.retrieval_models import (
    CorpusManifest,
    NormalizedCorpus,
    RetrievalEdge,
    RetrievalQuery,
    RetrievalUnit,
)


def make_corpus() -> NormalizedCorpus:
    return NormalizedCorpus(
        manifest=CorpusManifest(
            source_digests={"knowledge_graph": "a", "core_thinking": "b", "psychology_cognition": "c"},
            source_versions={"knowledge_graph": "v1", "core_thinking": "v1", "psychology_cognition": "v1"},
            unit_counts={"knowledge_graph": 2, "core_thinking": 1, "psychology_cognition": 1},
            edge_counts={"knowledge_graph": 1},
        ),
        units=[
            RetrievalUnit(
                unit_id="kg::force::overview",
                layer="knowledge_graph",
                unit_type="knowledge_point_overview",
                source_id="physics.force",
                parent_id="physics.force",
                source_artifact="release.json",
                source_path="network.points[0]",
                material_version="v1",
                approval_scope="published",
                title="受力分析",
                text="识别研究对象受到的力，画出力的示意图，并分析方向。",
                subject="physics",
                grade_min=8,
                grade_max=8,
            ),
            RetrievalUnit(
                unit_id="kg::newton::overview",
                layer="knowledge_graph",
                unit_type="knowledge_point_overview",
                source_id="physics.newton",
                parent_id="physics.newton",
                source_artifact="release.json",
                source_path="network.points[1]",
                material_version="v1",
                approval_scope="published",
                title="力与运动关系",
                text="分析力如何改变物体的运动状态。",
                subject="physics",
                grade_min=8,
                grade_max=8,
            ),
            RetrievalUnit(
                unit_id="core::model::signal::0",
                layer="core_thinking",
                unit_type="thinking_observable_signal",
                source_id="physics.model.signal.0",
                parent_id="physics.model",
                source_artifact="core.json",
                source_path="subjects.physics.artifacts[0].dimensions[0].observable_deficits[0]",
                material_version="v1",
                approval_scope="internal_conditionally_approved",
                title="物理模型：学生可观察表现",
                text="例题会做，换一个情境就不知道选哪个公式，也说不清各物理量之间的关系。",
                subject="physics",
                grade_min=7,
                grade_max=9,
                actor="learner",
            ),
            RetrievalUnit(
                unit_id="psy::anxiety::referral::0",
                layer="psychology_cognition",
                unit_type="professional_referral_condition",
                source_id="psychology.test-anxiety.referral.0",
                parent_id="psychology.test-anxiety",
                source_artifact="psychology.json",
                source_path="artifacts[0].dimensions[0].referral_conditions[0]",
                material_version="v1",
                approval_scope="internal_conditionally_approved",
                safety_level="referral",
                title="考试焦虑：专业转介条件",
                text="持续数周并显著影响上学、睡眠或日常功能时，应寻求合格专业支持。",
                grade_min=1,
                grade_max=9,
                actor="system",
            ),
        ],
        edges=[
            RetrievalEdge(
                source_id="physics.force",
                target_id="physics.newton",
                relation_type="supports",
                layer="knowledge_graph",
                source_artifact="release.json",
                source_path="network.relations[0]",
            )
        ],
    )


def test_hybrid_search_keeps_traceability_and_filters(tmp_path) -> None:
    embedder = HashingEmbedder(128)
    path = build_material_index(make_corpus(), tmp_path / "index.db", embedder=embedder)
    with MaterialIndex(path, embedder=embedder) as index:
        response = index.search(
            RetrievalQuery(text="孩子遇到新情境就不知道选什么公式", subjects=["physics"], grade=8)
        )

    assert response.hits
    assert response.hits[0].unit.source_artifact
    assert response.hits[0].unit.source_path
    assert all(hit.unit.subject == "physics" for hit in response.hits)


def test_exact_knowledge_title_and_graph_neighbor(tmp_path) -> None:
    path = build_material_index(make_corpus(), tmp_path / "index.db", embedder=None)
    with MaterialIndex(path) as index:
        response = index.search(
            RetrievalQuery(text="受力分析", subjects=["physics"], include_graph_neighbors=True)
        )

    assert response.hits[0].unit.source_id == "physics.force"
    assert any(
        hit.unit.source_id == "physics.newton" and "graph" in hit.matched_by
        for hit in response.hits
    )


def test_referral_channel_cannot_be_hidden_by_standard_content(tmp_path) -> None:
    path = build_material_index(make_corpus(), tmp_path / "index.db", embedder=None)
    with MaterialIndex(path) as index:
        response = index.search(
            RetrievalQuery(text="持续数周影响上学和睡眠", safety_levels=["referral"])
        )

    assert response.hits
    assert all(hit.unit.safety_level == "referral" for hit in response.hits)
    assert response.hits[0].unit.unit_type == "professional_referral_condition"


def test_index_rejects_query_embedding_model_mismatch(tmp_path) -> None:
    path = build_material_index(
        make_corpus(), tmp_path / "index.db", embedder=HashingEmbedder(128)
    )
    try:
        MaterialIndex(path, embedder=HashingEmbedder(256))
    except ValueError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("embedding model mismatch should fail")


def test_failed_rebuild_preserves_previous_index(tmp_path) -> None:
    class FailingEmbedder:
        model_id = "failing-test-backend"
        dimension = 64

        def embed_documents(self, texts):
            raise RuntimeError("simulated provider failure")

        def embed_query(self, text):
            raise RuntimeError("simulated provider failure")

    path = tmp_path / "index.db"
    path.write_bytes(b"previous-good-index")

    try:
        build_material_index(make_corpus(), path, embedder=FailingEmbedder())
    except RuntimeError as exc:
        assert "simulated provider failure" in str(exc)
    else:
        raise AssertionError("provider failure should stop the rebuild")

    assert path.read_bytes() == b"previous-good-index"
    assert not (tmp_path / "index.db.building").exists()
