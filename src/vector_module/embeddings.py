"""BGE-M3 dense embeddings through an OpenAI-compatible HTTP API, with disk cache."""

import hashlib
import json
import logging
import math
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .data_loader import canonical

log = logging.getLogger(__name__)


class EmbeddingError(RuntimeError):
    """A redacted API or validation error; never includes headers or response bodies."""


class BgeM3API:
    def __init__(
        self,
        api_url: str,
        model: str,
        cache_path: Path,
        api_key: str = "",
        revision: str = "unspecified",
        batch_size: int = 16,
        timeout: float = 60,
        max_retries: int = 3,
        max_input_chars: int = 16000,
        dimension: int = 1024,
        transport=None,
        sleep=time.sleep
    ):
        parts = urlsplit(api_url)

        if (
            parts.scheme not in ("http", "https")
            or not parts.netloc
            or parts.username
            or parts.password
            or parts.query
            or parts.fragment
        ):
            raise ValueError("Set BGE_M3_API_URL to the full embeddings endpoint, without credentials/query parameters.")

        if not model.strip() or min(batch_size, timeout, max_input_chars, dimension) <= 0 or max_retries < 0:
            raise ValueError("Invalid embedding model or configuration")

        self.api_url, self.model = api_url.rstrip("/"), model
        self.batch_size, self.max_retries = batch_size, max_retries
        self.max_input_chars, self.dimension = max_input_chars, dimension
        self.sleep = sleep

        # A different provider/model/revision must never share cached vectors or a collection.
        self.identity = {
            "protocol": "openai-compatible-v1",
            "endpoint": self.api_url,
            "model": model,
            "revision": revision,
            "dimension": dimension,
        }
        self.signature = hashlib.sha256(canonical(self.identity).encode("utf-8")).hexdigest()

        self.configuration = {
            **self.identity,
            "batch_size": batch_size,
            "timeout": timeout,
            "max_retries": max_retries,
            "max_input_chars": max_input_chars
        }

        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.client = httpx.Client(
            timeout=timeout,
            headers=headers,
            transport=transport,
            follow_redirects=False
        )

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache = sqlite3.connect(cache_path)
        self.cache.execute("CREATE TABLE IF NOT EXISTS embeddings (namespace TEXT, hash TEXT, vector TEXT, PRIMARY KEY(namespace, hash))")

        self.stats = {
            "api_requests": 0,
            "cache_hits": 0,
            "embedded_texts": 0,
            "reported_tokens": 0
        }

    @classmethod
    def from_settings(cls, settings):
        return cls(
            settings.api_url,
            settings.model,
            settings.cache_path,
            settings.api_key,
            settings.model_revision,
            settings.batch_size,
            settings.timeout,
            settings.max_retries,
            settings.max_input_chars
        )

    def close(self):
        self.client.close()
        self.cache.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


    def _validate_vector(self, vector) -> list[float]:
        if (
            not isinstance(vector, list)
            or len(vector) != self.dimension
            or any(type(x) not in (int, float) or not math.isfinite(x) for x in vector)
        ):
            raise EmbeddingError(f"Expected {self.dimension} finite numeric embedding values")

        norm = math.hypot(*vector)
        if not math.isfinite(norm) or norm == 0:
            raise EmbeddingError("Embedding has invalid or zero norm")

        return [float(x) for x in vector]


    def _request(self, texts: list[str]) -> list[list[float]]:
        for attempt in range(self.max_retries + 1):
            retry_after = 0.0
            self.stats["api_requests"] += 1

            try:
                response = self.client.post(
                    self.api_url, json={
                    "model": self.model,
                    "input": texts,
                    "encoding_format": "float",
                })
            except (httpx.TimeoutException, httpx.NetworkError):
                error = "Embedding API connection/timeout error"
            else:
                if response.status_code != 200:
                    error = f"Embedding API HTTP {response.status_code}"
                    if response.status_code not in (408, 429) and response.status_code < 500:
                        raise EmbeddingError(error + "; check endpoint, credentials, model and input limit")

                    try:
                        retry_after = float(response.headers.get("Retry-After", "0"))
                    except ValueError:
                        pass

                try:
                    body = response.json()
                    entries = body["data"]
                    if (
                        not isinstance(entries, list)
                        or len(entries) != len(texts)
                        or any(
                            not isinstance(e, dict)
                            or type(e.get("index")) is not int
                            for e in entries
                        )
                        or sorted(e["index"] for e in entries) != list(range(len(texts)))
                    ):
                        raise EmbeddingError("Embedding API returned missing or duplicate indices")

                    ordered = sorted(entries, key=lambda e: e["index"])
                    vectors = [self._validate_vector(e["embedding"]) for e in ordered]

                except (ValueError, KeyError, TypeError) as exc:
                    raise EmbeddingError("Malformed embedding response; expected indexed data[].embedding") from exc

                usage = body.get("usage") or {}
                tokens = usage.get("total_tokens", 0) if isinstance(usage, dict) else 0
                if type(tokens) is int and tokens >= 0:
                    self.stats["reported_tokens"] += tokens

                return vectors

            if attempt == self.max_retries:
                raise EmbeddingError(error + "; retries exhausted")

            log.warning("%s; retry %d/%d", error, attempt + 1, self.max_retries)
            self.sleep(min(10.0, max(2.0 ** attempt, retry_after)))

        raise AssertionError("unreachable")


    def embed(self, texts: list[str]) -> list[list[float]]:
        if any(not isinstance(t, str) or not t.strip() for t in texts):
            raise ValueError("Embedding inputs must be non-empty strings")

        if any(len(t) > self.max_input_chars for t in texts):
            raise ValueError("Input exceeds EMBEDDING_MAX_INPUT_CHARS; inspect the chunk. No text was truncated.")

        keys = [hashlib.sha256(t.encode("utf-8")).hexdigest() for t in texts]
        unique = dict(zip(keys, texts))
        vectors, missing = {}, []
        for key, text in unique.items():
            row = self.cache.execute(
                "SELECT vector FROM embeddings WHERE namespace=? AND hash=?",
                (self.signature, key)
            ).fetchone()

            if row:
                vectors[key] = self._validate_vector(json.loads(row[0]))
                self.stats["cache_hits"] += 1
            else:
                missing.append((key, text))

        for start in range(0, len(missing), self.batch_size):
            batch = missing[start:start + self.batch_size]

            try:
                result = self._request([t for _, t in batch])
            except EmbeddingError:
                log.error(
                    "Embedding batch failed at offset %d (%d texts); earlier cache batches retained",
                    start, len(batch)
                )
                raise

            with self.cache:
                for (key, _), vector in zip(batch, result):
                    self.cache.execute(
                        "INSERT OR REPLACE INTO embeddings VALUES (?, ?, ?)",
                        (self.signature, key, canonical(vector))
                    )
                    vectors[key] = vector

            self.stats["embedded_texts"] += len(batch)

        return [vectors[key] for key in keys]
