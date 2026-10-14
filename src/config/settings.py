"""Configuration for Vector module. Relative paths are resolved from the repository root."""

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class QueryUnderstandingSettings:
    api_key: str = field(default="", repr=False)
    model: str = "gpt-4o-mini"
    timeout: float = 30.0
    max_retries: int = 2
    max_history_messages: int = 6
    max_history_chars: int = 12000
    max_question_chars: int = 4000

    def __post_init__(self):
        if not self.model.strip() or not 0 < self.timeout < float("inf"):
            raise ValueError("Query model and finite positive timeout are required")
        if not 0 <= self.max_retries <= 2:
            raise ValueError("QUERY_MAX_RETRIES must be between 0 and 2")
        if min(self.max_history_messages, self.max_history_chars) < 0 or self.max_question_chars < 1:
            raise ValueError("Invalid query/history limits")

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "QueryUnderstandingSettings":
        env_file = env_file or ROOT / ".env"
        if env_file.exists():
            from dotenv import load_dotenv
            load_dotenv(env_file, override=False)
        return cls(
            api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            model=os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini"),
            timeout=float(os.getenv("QUERY_TIMEOUT", "30")),
            max_retries=int(os.getenv("QUERY_MAX_RETRIES", "2")),
            max_history_messages=int(os.getenv("QUERY_MAX_HISTORY_MESSAGES", "6")),
            max_history_chars=int(os.getenv("QUERY_MAX_HISTORY_CHARS", "12000")),
            max_question_chars=int(os.getenv("QUERY_MAX_QUESTION_CHARS", "4000")),
        )


@dataclass(frozen=True)
class VectorModuleSettings:
    processed_path: Path = ROOT / "DATA/processed"
    raw_path: Path = ROOT / "DATA/raw"
    output_path: Path = ROOT / "DATA/vector_artifacts"
    chroma_path: Path = ROOT / "DATA/chromadb_store"
    cache_path: Path = ROOT / "DATA/vector_artifacts/embeddings.sqlite3"
    collection_name: str = "vector_bge_m3"
    api_url: str = ""
    api_key: str = field(default="", repr=False)
    model: str = "BAAI/bge-m3"
    model_revision: str = "unspecified"
    batch_size: int = 16
    timeout: float = 60.0
    max_retries: int = 3
    max_input_chars: int = 16000
    target_words: int = 500

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "VectorModuleSettings":
        env_file = env_file or ROOT / ".env"
        if env_file.exists():
            from dotenv import load_dotenv
            load_dotenv(env_file, override=False)

        def path(key: str, default: str) -> Path:
            value = Path(os.getenv(key, default)).expanduser()
            return value.resolve() if value.is_absolute() else (ROOT / value).resolve()

        result = cls(
            processed_path=path("PROCESSED_DATA_PATH", "DATA/processed"),
            raw_path=path("RAW_DATA_PATH", "DATA/raw"),
            output_path=path("VECTOR_OUTPUT_PATH", "DATA/vector_artifacts"),
            chroma_path=path("CHROMA_PERSIST_DIRECTORY", "DATA/chromadb_store"),
            cache_path=path("EMBEDDING_CACHE_PATH", "DATA/vector_artifacts/embeddings.sqlite3"),
            collection_name=os.getenv("CHROMA_COLLECTION", "vector_bge_m3"),
            api_url=os.getenv("BGE_M3_API_URL", "").strip(),
            api_key=os.getenv("BGE_M3_API_KEY", "").strip(),
            model=os.getenv("BGE_M3_MODEL", "BAAI/bge-m3"),
            model_revision=os.getenv("BGE_M3_REVISION", "unspecified"),
            batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "16")),
            timeout=float(os.getenv("EMBEDDING_TIMEOUT", "60")),
            max_retries=int(os.getenv("EMBEDDING_MAX_RETRIES", "3")),
            max_input_chars=int(os.getenv("EMBEDDING_MAX_INPUT_CHARS", "16000")),
            target_words=int(os.getenv("CHUNK_TARGET_WORDS", "500")),
        )

        if min(result.batch_size, result.timeout, result.max_input_chars, result.target_words) <= 0:
            raise ValueError("Batch size, timeout, input limit and chunk target must be positive.")

        if result.max_retries < 0:
            raise ValueError("EMBEDDING_MAX_RETRIES cannot be negative.")

        return result
