from __future__ import annotations

import hashlib
import math
import os
import re
import time
import unicodedata
from typing import Any, Callable, Protocol, Sequence


class EmbeddingBackend(Protocol):
    @property
    def model_id(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class HashingEmbedder:
    """Dependency-free deterministic test backend; not a production semantic model."""

    def __init__(self, dimension: int = 256) -> None:
        if dimension < 32:
            raise ValueError("hashing embedding dimension must be at least 32")
        self._dimension = dimension

    @property
    def model_id(self) -> str:
        return f"deterministic-char-ngram-v1-{self.dimension}"

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        normalized = unicodedata.normalize("NFKC", text).lower()
        compact = re.sub(r"\s+", "", normalized)
        features = [compact[index : index + 2] for index in range(max(0, len(compact) - 1))]
        features.extend(re.findall(r"[a-z0-9_+\-./]+", normalized))
        vector = [0.0] * self.dimension
        for feature in features or [compact]:
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "little")
            bucket = value % self.dimension
            sign = 1.0 if (value >> 63) == 0 else -1.0
            vector[bucket] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class AliyunTextEmbeddingBackend:
    """Alibaba Cloud Model Studio text embeddings through the native DashScope API."""

    DEFAULT_ENDPOINT = (
        "https://dashscope.aliyuncs.com/api/v1/services/embeddings/"
        "text-embedding/text-embedding"
    )
    DEFAULT_MODEL = "text-embedding-v4"
    VALID_DIMENSIONS = {64, 128, 256, 512, 768, 1024, 1536, 2048}

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_key_env: str = "DASHSCOPE_API_KEY",
        endpoint: str | None = None,
        model_name: str = DEFAULT_MODEL,
        dimension: int = 1024,
        batch_size: int = 10,
        query_instruct: str | None = None,
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
        client: Any | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if dimension not in self.VALID_DIMENSIONS:
            raise ValueError(
                f"unsupported Aliyun embedding dimension {dimension}; "
                f"choose one of {sorted(self.VALID_DIMENSIONS)}"
            )
        if model_name != "text-embedding-v4" and dimension in {1536, 2048}:
            raise ValueError("1536 and 2048 dimensions require text-embedding-v4")
        if not 1 <= batch_size <= 10:
            raise ValueError("text-embedding-v4 batch_size must be between 1 and 10")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")

        self._api_key_env = api_key_env
        self._api_key = (api_key or os.getenv(api_key_env, "")).strip()
        self._endpoint = (
            endpoint
            or os.getenv("DASHSCOPE_EMBEDDING_ENDPOINT")
            or self.DEFAULT_ENDPOINT
        ).rstrip("/")
        self._model_name = model_name
        self._dimension = dimension
        self._batch_size = batch_size
        self._query_instruct = query_instruct or os.getenv(
            "DASHSCOPE_EMBEDDING_INSTRUCT", ""
        ).strip()
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._client = client
        self._sleep = sleep

    @property
    def model_id(self) -> str:
        return f"aliyun-dashscope/{self._model_name}@{self.dimension}"

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    @classmethod
    def from_model_id(cls, model_id: str, **kwargs: Any) -> "AliyunTextEmbeddingBackend":
        prefix = "aliyun-dashscope/"
        if not model_id.startswith(prefix) or "@" not in model_id:
            raise ValueError(f"invalid Aliyun embedding model id: {model_id}")
        model_name, raw_dimension = model_id[len(prefix) :].rsplit("@", 1)
        return cls(model_name=model_name, dimension=int(raw_dimension), **kwargs)

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._encode(list(texts), text_type="document")

    def embed_query(self, text: str) -> list[float]:
        return self._encode([text], text_type="query")[0]

    def _encode(self, texts: list[str], *, text_type: str) -> list[list[float]]:
        if not texts:
            return []
        if not self._api_key:
            raise RuntimeError(
                f"Aliyun embedding is selected but {self._api_key_env} is empty"
            )
        result: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            result.extend(self._request_batch(batch, text_type=text_type))
        return result

    def _request_batch(self, texts: list[str], *, text_type: str) -> list[list[float]]:
        parameters: dict[str, Any] = {
            "dimension": self.dimension,
            "output_type": "dense",
            "text_type": text_type,
        }
        if text_type == "query" and self._query_instruct:
            parameters["instruct"] = self._query_instruct
        payload = {
            "model": self._model_name,
            "input": {"texts": texts},
            "parameters": parameters,
        }
        response = self._post_with_retry(payload)
        try:
            raw_embeddings = response["output"]["embeddings"]
        except (KeyError, TypeError) as exc:
            raise RuntimeError("Aliyun embedding response is missing output.embeddings") from exc
        if len(raw_embeddings) != len(texts):
            raise RuntimeError(
                "Aliyun embedding response count does not match the request batch"
            )
        ordered = sorted(
            enumerate(raw_embeddings),
            key=lambda item: int(item[1].get("text_index", item[0])),
        )
        vectors = [item["embedding"] for _, item in ordered]
        return [self._normalize_vector(vector) for vector in vectors]

    def _post_with_retry(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "Aliyun embedding backend requires httpx; install retrieval dependencies"
            ) from exc

        client = self._client or httpx
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        for attempt in range(self._max_retries + 1):
            try:
                response = client.post(
                    self._endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self._timeout_seconds,
                )
            except Exception as exc:
                if attempt >= self._max_retries:
                    raise RuntimeError("Aliyun embedding request failed after retries") from exc
                self._sleep(min(2**attempt, 5))
                continue

            if response.status_code < 400:
                try:
                    return response.json()
                except Exception as exc:
                    raise RuntimeError("Aliyun embedding response is not valid JSON") from exc

            retryable = response.status_code == 429 or response.status_code >= 500
            if retryable and attempt < self._max_retries:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else min(2**attempt, 5)
                self._sleep(min(delay, 10))
                continue
            request_id = response.headers.get("x-request-id", "unknown")
            raise RuntimeError(
                f"Aliyun embedding request failed with HTTP {response.status_code}; "
                f"request_id={request_id}"
            )
        raise AssertionError("unreachable")

    def _normalize_vector(self, vector: Sequence[float]) -> list[float]:
        if len(vector) != self.dimension:
            raise RuntimeError(
                f"Aliyun returned dimension {len(vector)}, expected {self.dimension}"
            )
        values = [float(value) for value in vector]
        if not all(math.isfinite(value) for value in values):
            raise RuntimeError("Aliyun returned a non-finite embedding value")
        norm = math.sqrt(sum(value * value for value in values))
        if norm == 0:
            raise RuntimeError("Aliyun returned a zero embedding vector")
        return [value / norm for value in values]


class BgeTransformerEmbedder:
    """Local BGE embedding backend using the model card's CLS pooling recipe."""

    QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-zh-v1.5",
        *,
        batch_size: int = 32,
        device: str | None = None,
        max_length: int = 512,
        local_files_only: bool = False,
    ) -> None:
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:  # pragma: no cover - depends on optional packages
            raise RuntimeError(
                "BGE backend requires torch and transformers; install the retrieval optional dependencies"
            ) from exc

        self._torch = torch
        self._model_name = model_name
        self._batch_size = batch_size
        self._max_length = max_length
        self._device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._tokenizer = AutoTokenizer.from_pretrained(
            model_name, local_files_only=local_files_only
        )
        self._model = AutoModel.from_pretrained(
            model_name, local_files_only=local_files_only
        )
        self._model.to(self._device)
        self._model.eval()
        self._dimension = int(self._model.config.hidden_size)

    @property
    def model_id(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._encode(list(texts), is_query=False)

    def embed_query(self, text: str) -> list[float]:
        return self._encode([text], is_query=True)[0]

    def _encode(self, texts: list[str], *, is_query: bool) -> list[list[float]]:
        torch = self._torch
        prepared = (
            [self.QUERY_INSTRUCTION + text for text in texts] if is_query else texts
        )
        result: list[list[float]] = []
        for start in range(0, len(prepared), self._batch_size):
            batch = prepared[start : start + self._batch_size]
            encoded = self._tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=self._max_length,
                return_tensors="pt",
            )
            encoded = {key: value.to(self._device) for key, value in encoded.items()}
            with torch.inference_mode():
                output = self._model(**encoded)
                vectors = output.last_hidden_state[:, 0]
                vectors = torch.nn.functional.normalize(vectors, p=2, dim=1)
            result.extend(vectors.detach().cpu().float().tolist())
        return result
