"""Deterministic, source-preserving context packing; no retrieval or generation.

Only ``result.content`` belongs in the generation prompt. ``result.raw_data``
contains complete retrieval snapshots for inspection, including omitted data.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
import math
from typing import Any

from .schema import ContextResult


_NOTICE = (
    "Trạng thái: not_verified. Ngữ cảnh truy xuất có thể chưa đầy đủ. "
    "Việc không tìm thấy quan hệ hoặc danh sách rỗng không chứng minh rằng không có "
    "điều kiện. Chưa xác định logic AND/OR hay giải quyết mâu thuẫn giữa các nguồn."
)
_EMPTY = "(Không có tài liệu được chọn.)"


def _json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (ValueError, TypeError):
        raise ValueError("Context data must contain finite, JSON-serializable values") from None


def _text(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{location} must be a non-empty string")
    return value


def _mapping(value: Any, location: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be an object")
    return value


def _records(value: Any, location: str) -> list[dict]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{location} must be a list of objects")
    return value


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


@dataclass(frozen=True)
class _Block:
    label: str
    branch: str
    body: str
    sources: tuple[str, ...]
    identity: str

    @property
    def citations(self) -> list[str]:
        return [f"{self.label} {source}" for source in self.sources]

    def render(self) -> str:
        sources = "\n".join(self.citations) or "(Thiếu nguồn truy vết.)"
        return f"{self.label}\n{self.body}\nNguồn:\n{sources}"


def _opaque(context: ContextResult, branch: str, warnings: list[str]) -> list[_Block]:
    if not context.content.strip():
        return []

    label = "[V1]" if branch == "vector" else "[G1]"
    sources = tuple(_unique([source for source in context.citations if source.strip()]))
    warnings.append(f"{branch}_opaque_context: retained as one atomic block")

    if not sources:
        warnings.append(f"missing_source: {label}")

    return [_Block(
        label, branch, context.content, sources,
        _json({"content": context.content, "sources": sorted(sources)})
    )]


def _vector_blocks(context: ContextResult | None, warnings: list[str]) -> list[_Block]:
    if context is None:
        return []

    raw = context.raw_data or {}
    if "results" not in raw:
        return _opaque(context, "vector", warnings)

    blocks = []
    for index, match in enumerate(_records(raw["results"], "vector.results"), 1):
        label = f"[V{index}]"
        chunk_id = _text(match.get("chunk_id"), f"{label}.chunk_id")
        doc_id = _text(match.get("doc_id"), f"{label}.doc_id")
        text = _text(match.get("text"), f"{label}.text")
        document = _mapping(match.get("document"), f"{label}.document")
        passages = _records(match.get("passages"), f"{label}.passages")
        sources = []
        missing_source = not passages

        for passage in passages:
            pid = _text(passage.get("passage_id"), f"{label}.passage_id")
            locator = passage.get("source_locator")
            if locator is not None and not isinstance(locator, (str, dict)):
                raise ValueError(f"{label}.source_locator must be a string, object or null")

            sources.append(_json({
                "chunk_id": chunk_id, "doc_id": doc_id, "passage_id": pid,
                "source_file": document.get("source_file"), "source_locator": locator,
            }))
            missing_source |= not locator or not document.get("source_file")

        upstream_warnings = match.get("warnings", [])
        if not isinstance(upstream_warnings, list) or any(
            not isinstance(warning, str) for warning in upstream_warnings
        ):
            raise ValueError(f"{label}.warnings must be a list of strings")

        warnings.extend(f"{label}: {warning}" for warning in upstream_warnings)
        if missing_source:
            warnings.append(f"missing_source: {label}")

        identity = _json({"chunk_id": chunk_id, "doc_id": doc_id, "text": text,
                          "document": document, "passages": passages})

        blocks.append(_Block(
            label, "vector", f"Tài liệu: {_json(document)}\nNội dung:\n{text}",
            tuple(_unique(sources)), identity,
        ))
    return blocks


def _graph_sources(value: Any) -> list[str]:
    """Collect locators attached to this fact/path, never global citations."""
    sources = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "source_locator":
                if item is not None and not isinstance(item, (str, dict)):
                    raise ValueError("Graph source_locator must be a string, object or null")
                if item:
                    sources.append(item if isinstance(item, str) else _json(item))
            else:
                sources.extend(_graph_sources(item))
    elif isinstance(value, list):
        for item in value:
            sources.extend(_graph_sources(item))

    return _unique(sources)


def _graph_blocks(context: ContextResult | None, warnings: list[str]) -> list[_Block]:
    if context is None:
        return []

    raw = context.raw_data or {}
    if "courses" not in raw and "chains" not in raw:
        # Explicit no-result shapes from GraphRetriever are not graph evidence.
        no_entities = (
            raw.get("target_entities") == []
            and raw.get("nodes") == [] and raw.get("edges") == []
        )

        no_lookup_results = (
            ("lecturers" in raw or "blocks" in raw)
            and isinstance(raw.get("pyvis"), dict)
            and raw["pyvis"].get("nodes") == []
        )

        if no_entities or no_lookup_results:
            return []

        return _opaque(context, "graph", warnings)

    courses = _mapping(raw.get("courses", {}), "graph.courses")
    chains = _mapping(raw.get("chains", {}), "graph.chains")
    blocks = []

    def append(body: str, payload: dict, kind: str):
        label = f"[G{len(blocks) + 1}]"
        sources = _graph_sources(payload)

        if not sources:
            warnings.append(f"missing_source: {label}")

        blocks.append(_Block(
            label, "graph", body, tuple(sources),
            _json({"kind": kind, "payload": payload})
        ))

    for code, details in courses.items():
        _text(code, "graph.courses key")
        _mapping(details, f"graph.courses.{code}")

        if _text(details.get("code"), "course.code") != code:
            raise ValueError("Course code must match its graph.courses key")

        for field in ("prerequisites", "recommended", "corequisites", "prerequisite_for",
                      "lecturers", "assessments", "blocks", "graduation_reqs"):
            if field in details:
                _records(details[field], f"course.{field}")

        # Preserve complete groups and unknown metadata; do not infer AND/OR.
        append(f"Bản ghi môn học {code}:\n{_json(details)}", details, "course")

    for target, paths in chains.items():
        _text(target, "graph.chains key")

        for path in _records(paths, f"graph.chains.{target}"):
            nodes = _records(path.get("nodes"), "path.nodes")
            relationships = _records(path.get("relationships"), "path.relationships")
            depth = path.get("depth")

            if (type(depth) is not int or depth < 1 or depth != len(relationships)
                    or len(nodes) != depth + 1):
                raise ValueError("Graph path requires depth edges and depth + 1 ordered nodes")

            codes = [_text(node.get("code"), "path.node.code") for node in nodes]
            types = [_text(edge.get("type"), "path.relationship.type") for edge in relationships]

            if codes[-1] != target:
                raise ValueError("Graph path must end at its target course")

            route = codes[0] + "".join(
                f" -[{kind}]-> {code}" for kind, code in zip(types, codes[1:])
            )

            # JSON retains edge/node provenance at its original location.
            append(f"Đường đi đến {target}: {route}\nChi tiết: {_json(path)}", path, "path")
            if any(not edge.get("source_locator") for edge in relationships):
                warnings.append(f"missing_edge_source: {blocks[-1].label}")
    return blocks


def _render(blocks: list[_Block], *, empty_text: str = _EMPTY) -> str:
    sections = []
    for branch, heading in (("vector", "Vector Data"), ("graph", "Graph Data")):
        body = "\n\n".join(block.render() for block in blocks if block.branch == branch)
        sections.append(f"[{heading}]\n{body or empty_text}")
    return _NOTICE + "\n\n" + "\n\n".join(sections)


def _tokenizer(encoding_name: str):
    try:
        import tiktoken
    except ImportError:
        raise RuntimeError("Context Fusion requires tiktoken; install tiktoken>=0.7.0") from None
    try:
        return tiktoken.get_encoding(encoding_name)
    except ValueError:
        raise ValueError(f"Unknown tiktoken encoding: {encoding_name}") from None
    except Exception:
        raise RuntimeError("Cannot load tokenizer; check network access or TIKTOKEN_CACHE_DIR") from None


def fuse_contexts(
    vector_context: ContextResult | None,
    graph_context: ContextResult | None,
    *,
    max_tokens: int = 4096,
    graph_ratio: float = 0.5,
    encoding_name: str = "o200k_base",
) -> ContextResult:
    """Pack whole evidence blocks into a shared token budget.

    ``graph_ratio`` is a soft initial allocation, not a filter: remaining budget
    is offered to Vector then Graph. Input order and original labels are retained.
    Tokens include headings and citations, but exclude caller-owned prompts.
    Use ``graph_context=None`` for B1 with the same budget as B2.
    """
    if type(max_tokens) is not int or max_tokens < 1:
        raise ValueError("max_tokens must be a positive integer")

    if (type(graph_ratio) not in (int, float) or not 0 <= graph_ratio <= 1
            or not math.isfinite(graph_ratio)):
        raise ValueError("graph_ratio must be a finite number between 0 and 1")

    _text(encoding_name, "encoding_name")
    for context in (vector_context, graph_context):
        if context is not None and not isinstance(context, ContextResult):
            raise ValueError("Inputs must be ContextResult instances or None")

    warnings: list[str] = []
    blocks = _vector_blocks(vector_context, warnings) + _graph_blocks(graph_context, warnings)
    unique, dropped, seen = [], [], {}
    for block in blocks:
        key = (block.branch, block.identity)
        if key in seen:
            dropped.append({"id": block.label, "reason": "duplicate", "duplicate_of": seen[key]})
        else:
            seen[key] = block.label
            unique.append(block)

    encoding = _tokenizer(encoding_name)

    def count(text: str) -> int:
        # Retrieved special-token spellings remain ordinary, untrusted text.
        return len(encoding.encode_ordinary(text))

    # Empty-branch messages are replaced by evidence, so they are not fixed
    # overhead. Counting them here would underfund even a 100% branch quota.
    available = max(0, max_tokens - count(_render([], empty_text="")))
    quotas = {"graph": int(available * graph_ratio)}
    quotas["vector"] = available - quotas["graph"]
    for branch in quotas:
        if not any(block.branch != branch for block in unique):
            quotas[branch] = available

    selected: set[str] = set()

    def try_add(block: _Block) -> bool:
        candidate = [item for item in unique if item.label in selected or item is block]
        if count(_render(candidate)) <= max_tokens:
            selected.add(block.label)
            return True
        return False

    spent = {"vector": 0, "graph": 0}
    for block in unique:
        cost = count(block.render() + "\n\n")
        if spent[block.branch] + cost <= quotas[block.branch] and try_add(block):
            spent[block.branch] += cost

    # unique is ordered Vector then Graph; revisit blocks skipped by soft quotas.
    for block in unique:
        if block.label not in selected and not try_add(block):
            dropped.append({"id": block.label, "reason": "token_budget"})

    chosen = [block for block in unique if block.label in selected]
    content = _render(chosen) if chosen else ""
    for branch in ("vector", "graph"):
        if not any(block.branch == branch for block in unique):
            warnings.append(f"{branch}_empty")

    if any(item["reason"] == "token_budget" for item in dropped):
        warnings.append("context_truncated: whole evidence blocks omitted")

    if not chosen:
        warnings.append("no_evidence_selected")

    return ContextResult(
        branch_name="Context_Fusion", content=content,
        citations=_unique([source for block in chosen for source in block.citations]),
        raw_data={
            "vector": deepcopy(vector_context.model_dump()) if vector_context is not None else None,
            "graph": deepcopy(graph_context.model_dump()) if graph_context is not None else None,
            "fusion": {
                "max_tokens": max_tokens, "graph_ratio": graph_ratio,
                "encoding_name": encoding_name, "token_count": count(content),
                "selected_ids": [block.label for block in chosen], "dropped": dropped,
                "warnings": _unique(warnings), "verification_status": "not_verified",
            },
        },
    )
