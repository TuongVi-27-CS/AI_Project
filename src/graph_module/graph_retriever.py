"""Graph context retriever executing Cypher queries and path traversals."""
import os
import sys
from pathlib import Path

# Đảm bảo thư mục gốc dự án luôn nằm trong sys.path để import được src
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import re
from neo4j import GraphDatabase
from src.config.settings import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD


class GraphRetriever:
    """Truy vấn đồ thị tri thức (Knowledge Graph) phục vụ suy luận logic và kiểm chứng."""

    def __init__(self, uri=NEO4J_URI, user=NEO4J_USERNAME, password=NEO4J_PASSWORD):
        self.uri = uri
        self.user = user
        self.password = password
        self.driver = None

    def connect(self):
        if not self.driver:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def close(self):
        if self.driver:
            self.driver.close()
            self.driver = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def extract_course_codes_from_text(self, text: str) -> list:
        """
        Trích xuất các mã môn học chuẩn định dạng HCMUT (VD: CO2003, MT1003, PH1003) từ câu hỏi người dùng.
        """
        if not text:
            return []
        pattern = r"\b([A-Z]{2}\d{4})\b"
        return list(dict.fromkeys(re.findall(pattern, text.upper())))

    def get_course_details(self, course_code: str) -> dict:
        """Lấy thông tin chi tiết của môn học bao gồm điều kiện đầu vào và đầu ra."""
        self.connect()
        query = """
        MATCH (c:Course {code: $code})
        OPTIONAL MATCH (prereq:Course)-[r1:PREREQUISITE_FOR]->(c)
        OPTIONAL MATCH (recom:Course)-[r2:RECOMMENDED_FOR]->(c)
        OPTIONAL MATCH (c)-[r3:PREREQUISITE_FOR]->(next_c:Course)
        RETURN c.code AS code,
               c.name AS name,
               c.credits AS credits,
               collect(DISTINCT prereq.code) AS prerequisites,
               collect(DISTINCT recom.code) AS recommended,
               collect(DISTINCT next_c.code) AS prerequisite_for
        """
        with self.driver.session() as session:
            result = session.run(query, code=course_code.upper())
            record = result.single()
            if not record or not record["code"]:
                return None
            return {
                "code": record["code"],
                "name": record["name"],
                "credits": record["credits"],
                "prerequisites": [p for p in record["prerequisites"] if p],
                "recommended": [r for r in record["recommended"] if r],
                "prerequisite_for": [n for n in record["prerequisite_for"] if n],
            }

    def get_prerequisite_chain(self, course_code: str, max_depth: int = 3) -> list:
        """
        Truy vết chuỗi môn học tiên quyết đa bước (Multi-hop prerequisite path).
        Ví dụ: MT1003 -> CO1007 -> CO2003.
        Lưu ý: Không dùng 'WITH nodes(path)...' trung gian để tránh mất biến path khi tính length(path).
        """
        self.connect()
        query = f"""
        MATCH path = (prereq:Course)-[:PREREQUISITE_FOR*1..{max_depth}]->(target:Course {{code: $code}})
        RETURN [node in nodes(path) | {{code: node.code, name: node.name}}] AS path_nodes,
               [rel in relationships(path) | type(rel)] AS path_relationships,
               length(path) AS depth
        ORDER BY depth ASC
        """
        with self.driver.session() as session:
            result = session.run(query, code=course_code.upper())
            paths = []
            for record in result:
                paths.append({
                    "depth": record["depth"],
                    "nodes": record["path_nodes"],
                    "relationships": record["path_relationships"]
                })
            return paths

    def query_graph_for_rag(self, query_text: str) -> dict:
        """
        Hàm tích hợp tự động phân tích query tiếng Việt, trích xuất entity môn học,
        truy vấn quan hệ trong KG và trả về ngữ cảnh cấu trúc phục vụ RAG.
        """
        course_codes = self.extract_course_codes_from_text(query_text)
        graph_context = {
            "found_entities": course_codes,
            "courses": {},
            "chains": {},
            "formatted_text": ""
        }

        if not course_codes:
            return graph_context

        formatted_lines = ["[DỮ LIỆU ĐỒ THỊ TRI THỨC (KNOWLEDGE GRAPH)]:"]

        for code in course_codes:
            details = self.get_course_details(code)
            if details:
                graph_context["courses"][code] = details
                tc_str = f" ({details['credits']} tín chỉ)" if details['credits'] > 0 else ""
                formatted_lines.append(f"- Môn học {details['code']} - {details['name']}{tc_str}:")
                if details["prerequisites"]:
                    formatted_lines.append(f"  + Môn tiên quyết bắt buộc: {', '.join(details['prerequisites'])}")
                else:
                    formatted_lines.append("  + Môn tiên quyết: Không có")
                if details["recommended"]:
                    formatted_lines.append(f"  + Môn học trước khuyến nghị: {', '.join(details['recommended'])}")
                if details["prerequisite_for"]:
                    formatted_lines.append(f"  + Là tiên quyết cho các môn: {', '.join(details['prerequisite_for'])}")

            chains = self.get_prerequisite_chain(code, max_depth=3)
            if chains:
                graph_context["chains"][code] = chains
                formatted_lines.append(f"  + Chuỗi phụ thuộc đa bước tới {code}:")
                for c in chains:
                    chain_repr = " -> ".join([n["code"] for n in c["nodes"]])
                    formatted_lines.append(f"    * [Bậc {c['depth']}]: {chain_repr}")

        graph_context["formatted_text"] = "\n".join(formatted_lines)
        return graph_context


if __name__ == "__main__":
    print("=== KIỂM THỬ TRUY VẤN GRAPH RETRIEVER ===")
    test_code = "CO2003"
    try:
        with GraphRetriever() as retriever:
            print(f"[*] Thử trích xuất mã môn từ câu hỏi: 'Điều kiện tiên quyết để học CO2003 là gì?'")
            entities = retriever.extract_course_codes_from_text("Điều kiện tiên quyết để học CO2003 là gì?")
            print(f"  -> Entities: {entities}")

            print(f"\n[*] Truy vấn chi tiết môn {test_code}:")
            info = retriever.get_course_details(test_code)
            print(f"  -> Info: {info}")

            print(f"\n[*] Truy vết chuỗi tiên quyết tới môn {test_code}:")
            chains = retriever.get_prerequisite_chain(test_code)
            for c in chains:
                print(f"  -> Chuỗi bậc {c['depth']}: {' -> '.join(n['code'] for n in c['nodes'])}")

            print("\n[*] Thử định dạng ngữ cảnh cho RAG Prompt:")
            rag_data = retriever.query_graph_for_rag(f"Muốn học {test_code} thì phải hoàn thành môn nào trước?")
            print(rag_data["formatted_text"])
    except Exception as e:
        print(f"[X] Không thể kết nối Neo4j hoặc có lỗi: {e}")
        print("[*] Gợi ý: Hãy đảm bảo Neo4j container đã được bật và nạp dữ liệu từ neo4j_manager.py.")
