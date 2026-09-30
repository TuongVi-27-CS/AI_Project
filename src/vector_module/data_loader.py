"""Read Dataset without rewriting, repairing, or inferring source facts."""

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass
class Corpus:
    documents: dict[str, dict] = field(default_factory=dict)
    passages: dict[str, list[dict]] = field(default_factory=dict)
    issues: list[dict] = field(default_factory=list)

    def issue(self, severity: str, code: str, record: str, detail: str) -> None:
        self.issues.append({
            "severity": severity,
            "code": code,
            "record": record,
            "detail": detail
        })

    def report(self) -> dict:
        return {
            "documents": len(self.documents),
            "passages": sum(map(len, self.passages.values())),

            "review_statuses": dict(Counter(
                p.get("review_status", "unknown")
                for ps in self.passages.values() for p in ps
            )),

            "issue_counts": dict(Counter(i["code"] for i in self.issues)),
            "errors": sum(i["severity"] == "error" for i in self.issues),
            "issues": self.issues,
        }


def load_corpus(processed_path: Path, raw_path: Path) -> Corpus:
    corpus = Corpus()
    raw_path = raw_path.resolve()
    doc_files = sorted(processed_path.glob("**/documents/*.json"))

    if not doc_files:
        raise ValueError(f"No documents/*.json found under {processed_path}")

    pairs: list[tuple[dict, Path]] = []
    seen_passages: set[str] = set()

    def read(path: Path):
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            corpus.issue("error", "invalid_json", str(path), type(exc).__name__)
            return None

    for file in doc_files:
        doc = read(file)
        if (
            not isinstance(doc, dict)
            or not all(
                isinstance(doc.get(k), str)
                and doc[k].strip()
                for k in ("doc_id", "title", "source_file")
            )
        ):
            corpus.issue("error", "invalid_document", str(file), "doc_id, title, source_file required")
            continue

        did = doc["doc_id"]
        if did in corpus.documents:
            corpus.issue("error", "duplicate_doc_id", did, str(file))
            continue

        scope = doc.get("scope", {})
        if (
            not isinstance(scope, dict)
            or not isinstance(scope.get("cohorts", []), list)
            or not all(isinstance(c, str) for c in scope.get("cohorts", []))
        ):
            corpus.issue("error", "invalid_scope", did, "scope must be an object; cohorts must be an array of strings")
            continue

        corpus.documents[did] = doc
        pairs.append((doc, file.parent.parent / "passages" / file.name))
        for key in ("source_url", "effective_date"):
            if not doc.get(key):
                corpus.issue("warning", f"missing_{key}", did, "Unknown; not inferred")

        if not scope.get("program") or not scope.get("study_mode"):
            corpus.issue("warning", "incomplete_scope", did, "Program or study level missing")

        if any(re.fullmatch(r"HK\d+", str(c)) for c in scope.get("cohorts", [])):
            corpus.issue("warning", "semester_in_cohorts", did, "Source metadata retained unchanged")

    expected_files = {f.resolve() for _, f in pairs}
    for file in sorted(processed_path.glob("**/passages/*.json")):
        if file.resolve() not in expected_files:
            corpus.issue("error", "unpaired_passage_file", str(file), "No matching document file")

    for doc, file in pairs:
        did = doc["doc_id"]
        data = read(file)

        if not isinstance(data, list):
            corpus.issue("error", "invalid_passages", did, "Passage file must contain an array")
            continue

        source: Path = (raw_path / doc["source_file"]).resolve()
        raw = None
        if not source.is_relative_to(raw_path):
            corpus.issue("error", "unsafe_source_path", did, "Source path escapes RAW_DATA_PATH")

        elif not source.is_file():
            corpus.issue("warning", "missing_source_file", did, doc["source_file"])

        else:
            try:
                text = source.read_text(encoding="utf-8-sig")
                raw = json.loads(text) if source.suffix.lower() == ".json" else text.splitlines()
            except (OSError, ValueError):
                corpus.issue("warning", "unreadable_source", did, doc["source_file"])

        orders: set[int] = set()
        corpus.passages[did] = []
        for p in data:
            if not isinstance(p, dict):
                corpus.issue("error", "invalid_passage", did, "Passage must be an object")
                continue

            pid = p.get("passage_id")
            if (
                not isinstance(pid, str)
                or not pid.strip()
                or p.get("doc_id") != did
                or not isinstance(p.get("text"), str)
                or not p["text"].strip()
                or type(p.get("order")) is not int
                or p["order"] < 1
                or not isinstance(p.get("section_path"), list)
                or not all(isinstance(s, str) for s in p["section_path"])
                or not isinstance(p.get("source_locator"), (dict, str))
            ):
                corpus.issue("error", "invalid_passage", str(pid or did), "Invalid required fields")
                continue

            if pid in seen_passages or p["order"] in orders:
                corpus.issue("error", "duplicate_passage", pid, "Duplicate ID or order in document")
                continue

            seen_passages.add(pid)
            orders.add(p["order"])
            corpus.passages[did].append(p)

            if p.get("review_status") != "approved":
                corpus.issue("warning", "unreviewed", pid, str(p.get("review_status", "unknown")))

            locator = p["source_locator"]
            if raw is not None:
                try:
                    if isinstance(locator, dict) and locator.get("type") == "json_field":
                        current = raw
                        parts = re.findall(r"[^.\[\]]+", locator["path"])

                        if not parts:
                            raise ValueError("Empty locator")

                        for part in parts:
                            current = current[int(part)] if isinstance(current, list) else current[part]

                    elif isinstance(locator, str) and re.fullmatch(r"line_[1-9]\d*", locator):
                        if not isinstance(raw, list) or int(locator[5:]) > len(raw):
                            raise ValueError("Line out of range")

                    else:
                        raise ValueError("Unsupported locator")
                except (KeyError, IndexError, TypeError, ValueError):
                    corpus.issue("warning", "unresolved_locator", pid, canonical(locator))

        corpus.passages[did].sort(key=lambda p: p["order"])

        if not corpus.passages[did]:
            corpus.issue("error", "empty_document", did, "No usable passages")

    return corpus
