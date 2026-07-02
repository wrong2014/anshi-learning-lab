from __future__ import annotations

import math

import pytest

from learning_problem_factory.embeddings import AliyunTextEmbeddingBackend


class FakeResponse:
    def __init__(self, status_code: int, payload: dict, headers: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def json(self) -> dict:
        return self._payload


class FakeDashScopeClient:
    def __init__(self, dimension: int, queued_statuses: list[int] | None = None) -> None:
        self.dimension = dimension
        self.queued_statuses = list(queued_statuses or [])
        self.calls: list[dict] = []

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        if self.queued_statuses:
            status = self.queued_statuses.pop(0)
            if status >= 400:
                return FakeResponse(status, {"message": "retry"}, {"Retry-After": "0"})
        texts = kwargs["json"]["input"]["texts"]  # type: ignore[index]
        embeddings = []
        for index, _ in enumerate(texts):
            vector = [0.0] * self.dimension
            vector[0] = float(index + 1)
            vector[1] = 1.0
            embeddings.append({"text_index": index, "embedding": vector})
        return FakeResponse(200, {"output": {"embeddings": embeddings}})


def test_aliyun_backend_keeps_key_empty_until_actual_call(monkeypatch) -> None:
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    backend = AliyunTextEmbeddingBackend(dimension=64)

    assert not backend.configured
    assert backend.model_id == "aliyun-dashscope/text-embedding-v4@64"
    with pytest.raises(RuntimeError, match="DASHSCOPE_API_KEY is empty"):
        backend.embed_query("测试查询")


def test_aliyun_backend_batches_and_distinguishes_document_from_query() -> None:
    client = FakeDashScopeClient(64)
    backend = AliyunTextEmbeddingBackend(
        api_key="test-only-key",
        dimension=64,
        batch_size=10,
        query_instruct="Retrieve relevant educational evidence.",
        client=client,
        sleep=lambda _: None,
    )

    document_vectors = backend.embed_documents([f"文档 {index}" for index in range(23)])
    query_vector = backend.embed_query("孩子不会把题目画成图")

    assert len(document_vectors) == 23
    assert len(client.calls) == 4
    assert [len(call["json"]["input"]["texts"]) for call in client.calls] == [10, 10, 3, 1]  # type: ignore[index]
    for call in client.calls[:3]:
        assert call["json"]["parameters"]["text_type"] == "document"  # type: ignore[index]
        assert "instruct" not in call["json"]["parameters"]  # type: ignore[index]
    assert client.calls[3]["json"]["parameters"]["text_type"] == "query"  # type: ignore[index]
    assert client.calls[3]["json"]["parameters"]["instruct"]  # type: ignore[index]
    assert math.isclose(sum(value * value for value in query_vector), 1.0, rel_tol=1e-6)


def test_aliyun_backend_retries_rate_limit_without_exposing_key() -> None:
    client = FakeDashScopeClient(64, queued_statuses=[429, 200])
    sleeps: list[float] = []
    backend = AliyunTextEmbeddingBackend(
        api_key="secret-not-for-output",
        dimension=64,
        client=client,
        sleep=sleeps.append,
    )

    vector = backend.embed_query("查询")

    assert len(vector) == 64
    assert len(client.calls) == 2
    assert sleeps == [0.0]


def test_aliyun_backend_rejects_wrong_response_dimension() -> None:
    client = FakeDashScopeClient(128)
    backend = AliyunTextEmbeddingBackend(
        api_key="test-only-key", dimension=64, client=client, sleep=lambda _: None
    )

    with pytest.raises(RuntimeError, match="returned dimension 128"):
        backend.embed_query("查询")
