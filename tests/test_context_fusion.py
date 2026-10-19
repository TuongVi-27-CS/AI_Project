"""Behavior tests with the real tokenizer; no LLM or database dependencies."""

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

import tiktoken

from examples.context_fusion import build_demo_contexts
from src.engine.fusion_chain import fuse_contexts
from src.engine.schema import ContextResult


class ContextFusionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.encoding = tiktoken.get_encoding("o200k_base")

    def setUp(self):
        self.vector, self.graph = build_demo_contexts()

    def stats(self, result):
        return result.raw_data["fusion"]

    def tokens(self, text):
        return len(self.encoding.encode_ordinary(text))

    def assert_budget(self, result, budget):
        self.assertEqual(self.stats(result)["token_count"], self.tokens(result.content))
        self.assertLessEqual(self.tokens(result.content), budget)
        for citation in result.citations:
            self.assertIn(citation, result.content)
            self.assertIn(citation.split(" ", 1)[0], self.stats(result)["selected_ids"])

    def test_both_branches_preserve_sources_and_order(self):
        result = fuse_contexts(self.vector, self.graph)
        self.assertEqual(result.branch_name, "Context_Fusion")
        self.assertEqual(self.stats(result)["selected_ids"], ["[V1]", "[G1]", "[G2]"])
        self.assertLess(result.content.index("[Vector Data]"), result.content.index("[Graph Data]"))
        self.assertIn(self.vector.raw_data["results"][0]["text"], result.content)
        self.assertIn(self.vector.citations[0], result.citations)
        self.assertIn("demo-v1", result.content)
        self.assertEqual(self.stats(result)["verification_status"], "not_verified")
        self.assert_budget(result, 4096)

    def test_path_keeps_direction_types_and_edge_provenance(self):
        path = self.graph.raw_data["chains"]["DEMO3001"][0]
        path["relationships"][1]["type"] = "CO_REQUISITE_FOR"
        result = fuse_contexts(None, self.graph)
        self.assertIn("DEMO1001 -[PREREQUISITE_FOR]-> DEMO1002 -[CO_REQUISITE_FOR]-> DEMO3001", result.content)
        self.assertIn("[G2] demo/requirements.json#/A_to_B", result.citations)
        self.assertIn("[G2] demo/requirements.json#/B_to_C", result.citations)
        # The course block must not claim citations belonging only to the path.
        self.assertNotIn("[G1] demo/requirements.json#/A_to_B", result.citations)
        self.graph.citations.append("unrelated-global-source")
        self.assertNotIn("unrelated-global-source", fuse_contexts(None, self.graph).content)

    def test_no_mutation_or_shared_snapshot_references(self):
        before = (self.vector.model_dump(), self.graph.model_dump())
        result = fuse_contexts(self.vector, self.graph)
        self.assertEqual(before, (self.vector.model_dump(), self.graph.model_dump()))
        self.assertEqual(result.raw_data["graph"], before[1])
        result.raw_data["graph"]["raw_data"]["courses"]["DEMO3001"]["name"] = "changed"
        result.raw_data["vector"]["raw_data"]["results"][0]["document"]["title"] = "changed"
        self.assertEqual(before, (self.vector.model_dump(), self.graph.model_dump()))

    def test_exact_duplicates_removed_but_labels_not_renumbered(self):
        match = self.vector.raw_data["results"][0]
        duplicate = deepcopy(match)
        duplicate["distance"] = 0.3  # Retrieval score is not evidence identity.
        revised = deepcopy(match)
        revised["document"]["version"] = "demo-v2"
        self.vector.raw_data["results"] += [duplicate, revised]
        path = self.graph.raw_data["chains"]["DEMO3001"][0]
        self.graph.raw_data["chains"]["DEMO3001"].append(deepcopy(path))
        result = fuse_contexts(self.vector, self.graph, max_tokens=10000)
        self.assertEqual(self.stats(result)["selected_ids"], ["[V1]", "[V3]", "[G1]", "[G2]"])
        self.assertIn({"id": "[V2]", "reason": "duplicate", "duplicate_of": "[V1]"}, self.stats(result)["dropped"])
        self.assertIn({"id": "[G3]", "reason": "duplicate", "duplicate_of": "[G2]"}, self.stats(result)["dropped"])
        self.assertFalse(any(c.startswith("[V2]") or c.startswith("[G3]") for c in result.citations))

    def test_same_text_different_source_or_scope_is_retained(self):
        match = self.vector.raw_data["results"][0]
        other_source, other_scope = deepcopy(match), deepcopy(match)
        other_source["document"]["source_file"] = "other.json"
        other_scope["document"]["scope"]["cohorts"] = ["2025"]
        self.vector.raw_data["results"] += [other_source, other_scope]
        result = fuse_contexts(self.vector, None)
        self.assertEqual(self.stats(result)["selected_ids"], ["[V1]", "[V2]", "[V3]"])
        self.assertEqual(self.stats(result)["dropped"], [])

    def test_same_path_different_edge_source_is_retained(self):
        paths = self.graph.raw_data["chains"]["DEMO3001"]
        other = deepcopy(paths[0])
        other["relationships"][0]["source_locator"] = "another-version.json"
        paths.append(other)
        result = fuse_contexts(None, self.graph)
        self.assertEqual(self.stats(result)["selected_ids"], ["[G1]", "[G2]", "[G3]"])

    def test_citations_deduplicated_per_label(self):
        passages = self.vector.raw_data["results"][0]["passages"]
        passages.append(deepcopy(passages[0]))
        second = deepcopy(passages[0])
        second["passage_id"] = "demo_passage_2"
        second["source_locator"] = {"section": "Ngoại lệ"}
        passages.append(second)
        result = fuse_contexts(self.vector, None)
        self.assertEqual(len(result.citations), 2)
        self.assertEqual([json.loads(c.split(" ", 1)[1])["passage_id"] for c in result.citations],
                         ["demo_passage_1", "demo_passage_2"])

    def test_single_branch_borrows_entire_budget(self):
        for vector, graph, expected in ((self.vector, None, ["[V1]"]),
                                        (None, self.graph, ["[G1]", "[G2]"])):
            with self.subTest(expected=expected):
                full = fuse_contexts(vector, graph)
                budget = self.tokens(full.content)
                for ratio in (0, 0.5, 1):
                    result = fuse_contexts(vector, graph, max_tokens=budget, graph_ratio=ratio)
                    self.assertEqual(self.stats(result)["selected_ids"], expected)
                    self.assert_budget(result, budget)

    def test_exact_budget_and_one_token_short_do_not_cut_block(self):
        full = fuse_contexts(self.vector, None)
        budget = self.tokens(full.content)
        exact = fuse_contexts(self.vector, None, max_tokens=budget)
        short = fuse_contexts(self.vector, None, max_tokens=budget - 1)
        self.assertEqual(exact.content, full.content)
        self.assertEqual(short.content, "")
        self.assertEqual(short.citations, [])
        self.assertIn({"id": "[V1]", "reason": "token_budget"}, self.stats(short)["dropped"])

    def test_oversized_chunk_is_skipped_and_later_chunk_is_used_whole(self):
        original = deepcopy(self.vector.raw_data["results"][0])
        self.vector.raw_data["results"][0]["text"] = "Điều kiện và ngoại lệ. " * 2000
        original["chunk_id"] = "later_chunk"
        self.vector.raw_data["results"].append(original)
        result = fuse_contexts(self.vector, self.graph, max_tokens=700)
        self.assertNotIn("[V1]", self.stats(result)["selected_ids"])
        self.assertIn("[V2]", self.stats(result)["selected_ids"])
        self.assertIn(original["text"], result.content)
        self.assertFalse(any(c.startswith("[V1]") for c in result.citations))
        self.assertIn("context_truncated: whole evidence blocks omitted", self.stats(result)["warnings"])
        self.assert_budget(result, 700)

    def test_whole_course_and_path_at_every_budget(self):
        path_only = self.graph.model_copy(deep=True)
        path_only.raw_data["courses"] = {}
        full_path = fuse_contexts(None, path_only).content
        path_body = full_path.split("[G1]\n", 1)[1].split("\nNguồn:\n", 1)[0]
        for budget in (1, 100, 300, 500, 800, 1200, 2000, 4096):
            with self.subTest(budget=budget):
                result = fuse_contexts(self.vector, self.graph, max_tokens=budget)
                self.assert_budget(result, budget)
                if "[G2]" in self.stats(result)["selected_ids"]:
                    self.assertIn(path_body, result.content)
                else:
                    self.assertNotIn("Đường đi đến DEMO3001:", result.content)
                if "[G1]" in self.stats(result)["selected_ids"]:
                    self.assertIn(json.dumps(self.graph.raw_data["courses"]["DEMO3001"],
                                             ensure_ascii=False, sort_keys=True), result.content)

    def test_soft_quotas_then_leftover_vector_first(self):
        # Equal-sized, opaque evidence permits exactly one of the two blocks.
        v = ContextResult(branch_name="Vector_Retrieval", content="evidence " * 50, citations=["source"])
        g = ContextResult(branch_name="Graph_Traversal", content=v.content, citations=v.citations)
        budget = max(self.tokens(fuse_contexts(v, None).content), self.tokens(fuse_contexts(None, g).content))
        self.assertEqual(self.stats(fuse_contexts(v, g, max_tokens=budget))["selected_ids"], ["[V1]"])
        self.assertEqual(self.stats(fuse_contexts(v, g, max_tokens=budget, graph_ratio=1))["selected_ids"], ["[G1]"])

    def test_empty_inputs_and_graph_no_result_shapes(self):
        shapes = [None, {}, {"courses": {}, "chains": {}},
                  {"target_entities": [], "nodes": [], "edges": [], "tier_used": "test"},
                  {"lecturers": ["unknown"], "pyvis": {"nodes": [], "edges": []}},
                  {"blocks": ["unknown"], "pyvis": {"nodes": [], "edges": []}}]
        for shape in shapes:
            with self.subTest(shape=shape):
                graph = None if shape is None else ContextResult(
                    branch_name="Graph_Traversal", content="Không tìm thấy" if shape else "", raw_data=shape)
                result = fuse_contexts(None, graph)
                self.assertEqual(result.content, "")
                self.assertEqual(result.citations, [])
                self.assertEqual(self.stats(result)["token_count"], 0)
                self.assertIn("no_evidence_selected", self.stats(result)["warnings"])
        empty_vector = ContextResult(branch_name="Vector_Retrieval", content="", raw_data={"results": []})
        self.assertEqual(fuse_contexts(empty_vector, self.graph).content, fuse_contexts(None, self.graph).content)

    def test_opaque_lecturer_block_and_text_contexts_are_atomic(self):
        for raw in (None, {"lecturers": ["GV Demo"], "pyvis": {"nodes": [{"id": "L1"}]}},
                    {"blocks": ["B1"], "pyvis": {"nodes": [{"id": "B1"}]}}):
            with self.subTest(raw=raw):
                context = ContextResult(branch_name="Graph_Traversal", content="Nội dung đầy đủ\nĐiều kiện và ngoại lệ.",
                                        citations=["source1", "source1", "source2"], raw_data=raw)
                full = fuse_contexts(None, context)
                self.assertIn(context.content, full.content)
                self.assertEqual(full.citations, ["[G1] source1", "[G1] source2"])
                self.assertEqual(fuse_contexts(None, context, max_tokens=self.tokens(full.content) - 1).content, "")

    def test_missing_provenance_warns_without_inventing_sources(self):
        self.vector.raw_data["results"][0]["passages"][0]["source_locator"] = None
        self.graph.raw_data["courses"] = {}
        path = self.graph.raw_data["chains"]["DEMO3001"][0]
        for record in path["nodes"] + path["relationships"]:
            record["source_locator"] = None
        result = fuse_contexts(self.vector, self.graph)
        for warning in ("missing_source: [V1]", "missing_source: [G1]", "missing_edge_source: [G1]"):
            self.assertIn(warning, self.stats(result)["warnings"])
        self.assertFalse(any(c.startswith("[G1]") for c in result.citations))
        self.assertIn("demo_data_only", " ".join(self.stats(result)["warnings"]))

    def test_unicode_special_token_spelling_and_determinism(self):
        self.vector.raw_data["results"][0]["text"] += "\n<|endoftext|> GPA ≥ 2,0; tín chỉ 😀"
        first = fuse_contexts(self.vector, self.graph)
        second = fuse_contexts(self.vector, self.graph)
        self.assertEqual(first.model_dump(), second.model_dump())
        self.assertIn("<|endoftext|>", first.content)
        self.assert_budget(first, 4096)

    def test_invalid_configuration(self):
        cases = [{"max_tokens": value} for value in (0, -1, True, 1.5, "100")]
        cases += [{"graph_ratio": value} for value in (-0.1, 1.1, True, float("nan"), float("inf"), "0.5")]
        cases += [{"encoding_name": value} for value in ("", " ", "not-a-tokenizer", None)]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                fuse_contexts(self.vector, self.graph, **kwargs)
        with self.assertRaises(ValueError):
            fuse_contexts({}, None)

    def test_malformed_recognized_data_is_not_silently_rendered_as_text(self):
        for raw in ({"results": None}, {"results": [{}]}, {"results": "bad"}):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                fuse_contexts(ContextResult(branch_name="Vector_Retrieval", content="fallback", raw_data=raw), None)
        for field, value in (("depth", 99), ("relationships", []), ("nodes", [])):
            graph = self.graph.model_copy(deep=True)
            graph.raw_data["chains"]["DEMO3001"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                fuse_contexts(None, graph)
        graph = self.graph.model_copy(deep=True)
        graph.raw_data["courses"] = []
        with self.assertRaises(ValueError):
            fuse_contexts(None, graph)

    def test_tokenizer_unavailable_has_no_character_count_fallback(self):
        with patch.dict("sys.modules", {"tiktoken": None}), self.assertRaisesRegex(RuntimeError, "requires tiktoken"):
            fuse_contexts(self.vector, None)
        with patch("tiktoken.get_encoding", side_effect=OSError("unavailable")):
            with self.assertRaisesRegex(RuntimeError, "TIKTOKEN_CACHE_DIR"):
                fuse_contexts(self.vector, None)


if __name__ == "__main__":
    unittest.main()
