"""
Neo4j graph database manager and importer.
Hỗ trợ nạp Đồ thị tri thức Ontology mở rộng (Course, Lecturer, Assessment, CurriculumBlock).
Sử dụng Cypher Batching UNWIND và MERGE đảm bảo Idempotent và tốc độ cao.
"""
import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, List

# Đảm bảo thư mục gốc dự án luôn nằm trong sys.path để import được src
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from neo4j import GraphDatabase, exceptions as neo4j_exceptions
from src.config.settings import (
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD,
    GRAPH_TRIPLETS_DIR,
)


class Neo4jManager:
    """Quản lý kết nối và các thao tác ghi/đọc cơ sở dữ liệu đồ thị Neo4j."""

    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USERNAME, password: str = NEO4J_PASSWORD):
        self.uri = uri
        self.user = user
        self.password = password
        self.driver = None

    def connect(self):
        """Khởi tạo Neo4j driver và kiểm tra kết nối."""
        if not self.driver:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            self.driver.verify_connectivity()
            print(f"[+] Kết nối Neo4j thành công tại: {self.uri}")

    def close(self):
        """Đóng kết nối driver an toàn."""
        if self.driver:
            self.driver.close()
            self.driver = None
            print("[-] Đã đóng kết nối Neo4j.")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def create_constraints(self):
        """
        Tạo ràng buộc Unique Constraint cho từng loại thực thể:
        - Course.code
        - Lecturer.name
        - Assessment.id
        - CurriculumBlock.id
        """
        queries = [
            "CREATE CONSTRAINT course_code_unique IF NOT EXISTS FOR (c:Course) REQUIRE c.code IS UNIQUE",
            "CREATE CONSTRAINT lecturer_name_unique IF NOT EXISTS FOR (l:Lecturer) REQUIRE l.name IS UNIQUE",
            "CREATE CONSTRAINT assessment_id_unique IF NOT EXISTS FOR (a:Assessment) REQUIRE a.id IS UNIQUE",
            "CREATE CONSTRAINT block_id_unique IF NOT EXISTS FOR (b:CurriculumBlock) REQUIRE b.id IS UNIQUE",
        ]
        with self.driver.session() as session:
            for q in queries:
                session.run(q)
            print("[+] Đã kiểm tra/tạo đầy đủ Unique Constraints cho 4 loại thực thể.")

    def clear_database(self):
        """Xóa toàn bộ nodes và relationships hiện có trong cơ sở dữ liệu."""
        query = "MATCH (n) DETACH DELETE n"
        with self.driver.session() as session:
            result = session.run(query)
            summary = result.consume()
            print(f"[!] Đã dọn dẹp database (xóa {summary.counters.nodes_deleted} nodes, {summary.counters.relationships_deleted} relationships).")

    def import_curriculum(self, json_path=None):
        """
        Nạp dữ liệu từ file JSON đồ thị môn học (curriculum_graph.json) vào Neo4j.
        Hỗ trợ đa thực thể: Course, Lecturer, Assessment, CurriculumBlock.
        Sử dụng UNWIND batching và MERGE để đảm bảo Idempotent (không tạo trùng lặp).
        """
        if json_path is None:
            json_path = GRAPH_TRIPLETS_DIR / "curriculum_graph.json"

        if not Path(json_path).exists():
            raise FileNotFoundError(f"Không tìm thấy file đồ thị tại: {json_path}")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        nodes = data.get("nodes", [])
        relationships = data.get("relationships", [])

        # Phân loại Node theo Type
        nodes_by_type: Dict[str, List[Dict[str, Any]]] = {
            "Course": [],
            "Lecturer": [],
            "Assessment": [],
            "CurriculumBlock": [],
        }
        for n in nodes:
            ntype = n.get("type", "Course")
            if ntype in nodes_by_type:
                nodes_by_type[ntype].append(n)
            else:
                nodes_by_type.setdefault(ntype, []).append(n)

        # Phân loại Relationship theo Type
        rels_by_type: Dict[str, List[Dict[str, Any]]] = {}
        for r in relationships:
            rtype = r.get("type", "RECOMMENDED_FOR")
            rels_by_type.setdefault(rtype, []).append(r)

        batch_size = 100
        print(f"[*] Chuẩn bị import {len(nodes)} Nodes và {len(relationships)} Quan hệ vào Neo4j...")

        with self.driver.session() as session:
            # 1. Import Course Nodes
            course_query = """
            UNWIND $batch AS item
            MERGE (c:Course {code: item.code})
            SET c.name = item.name,
                c.credits = item.credits,
                c.source_locator = item.source_locator
            """
            for i in range(0, len(nodes_by_type["Course"]), batch_size):
                batch = nodes_by_type["Course"][i:i + batch_size]
                session.run(course_query, batch=batch)
            print(f"[+] Đã import thành công {len(nodes_by_type['Course'])} Course nodes.")

            # 2. Import Lecturer Nodes
            lec_query = """
            UNWIND $batch AS item
            MERGE (l:Lecturer {name: item.name})
            SET l.email = item.email,
                l.department = item.department,
                l.faculty = item.faculty,
                l.source_locator = item.source_locator
            """
            for i in range(0, len(nodes_by_type["Lecturer"]), batch_size):
                batch = nodes_by_type["Lecturer"][i:i + batch_size]
                session.run(lec_query, batch=batch)
            print(f"[+] Đã import thành công {len(nodes_by_type['Lecturer'])} Lecturer nodes.")

            # 3. Import Assessment Nodes
            ass_query = """
            UNWIND $batch AS item
            MERGE (a:Assessment {id: item.id})
            SET a.name = item.name,
                a.method = item.method,
                a.weight = item.weight,
                a.duration = item.duration,
                a.source_locator = item.source_locator
            """
            for i in range(0, len(nodes_by_type["Assessment"]), batch_size):
                batch = nodes_by_type["Assessment"][i:i + batch_size]
                session.run(ass_query, batch=batch)
            print(f"[+] Đã import thành công {len(nodes_by_type['Assessment'])} Assessment nodes.")

            # 4. Import CurriculumBlock Nodes
            block_query = """
            UNWIND $batch AS item
            MERGE (b:CurriculumBlock {id: item.id})
            SET b.name = item.name,
                b.major = item.major,
                b.source_locator = item.source_locator
            """
            for i in range(0, len(nodes_by_type["CurriculumBlock"]), batch_size):
                batch = nodes_by_type["CurriculumBlock"][i:i + batch_size]
                session.run(block_query, batch=batch)
            print(f"[+] Đã import thành công {len(nodes_by_type['CurriculumBlock'])} CurriculumBlock nodes.")

            # 5. Import Từng Loại Quan hệ (Edges)
            rel_cypher_templates = {
                "PREREQUISITE_FOR": """
                    UNWIND $batch AS item
                    MATCH (src:Course {code: item.source})
                    MATCH (tgt:Course {code: item.target})
                    MERGE (src)-[r:PREREQUISITE_FOR]->(tgt)
                    SET r.source_locator = item.source_locator
                """,
                "RECOMMENDED_FOR": """
                    UNWIND $batch AS item
                    MATCH (src:Course {code: item.source})
                    MATCH (tgt:Course {code: item.target})
                    MERGE (src)-[r:RECOMMENDED_FOR]->(tgt)
                    SET r.source_locator = item.source_locator
                """,
                "CO_REQUISITE_FOR": """
                    UNWIND $batch AS item
                    MATCH (src:Course {code: item.source})
                    MATCH (tgt:Course {code: item.target})
                    MERGE (src)-[r:CO_REQUISITE_FOR]->(tgt)
                    SET r.source_locator = item.source_locator
                """,
                "TAUGHT_BY": """
                    UNWIND $batch AS item
                    MATCH (src:Course {code: item.source})
                    MATCH (tgt:Lecturer {name: item.target})
                    MERGE (src)-[r:TAUGHT_BY]->(tgt)
                    SET r.source_locator = item.source_locator
                """,
                "EVALUATED_BY": """
                    UNWIND $batch AS item
                    MATCH (src:Course {code: item.source})
                    MATCH (tgt:Assessment {id: item.target})
                    MERGE (src)-[r:EVALUATED_BY]->(tgt)
                    SET r.source_locator = item.source_locator
                """,
                "CONTAINS": """
                    UNWIND $batch AS item
                    MATCH (src:CurriculumBlock {id: item.source})
                    MATCH (tgt:Course {code: item.target})
                    MERGE (src)-[r:CONTAINS]->(tgt)
                    SET r.source_locator = item.source_locator
                """,
                "REQUIRES_GRADUATION": """
                    UNWIND $batch AS item
                    MATCH (src:CurriculumBlock {id: item.source})
                    MATCH (tgt:Course {code: item.target})
                    MERGE (src)-[r:REQUIRES_GRADUATION]->(tgt)
                    SET r.source_locator = item.source_locator
                """,
            }

            for r_type, rel_list in rels_by_type.items():
                if not rel_list:
                    continue
                template = rel_cypher_templates.get(r_type)
                if not template:
                    # Generic fallback template
                    template = f"""
                    UNWIND $batch AS item
                    MATCH (src {{code: item.source}})
                    MATCH (tgt {{id: item.target}})
                    MERGE (src)-[r:{r_type}]->(tgt)
                    SET r.source_locator = item.source_locator
                    """
                for i in range(0, len(rel_list), batch_size):
                    batch = rel_list[i:i + batch_size]
                    session.run(template, batch=batch)
                print(f"[+] Đã tạo {len(rel_list)} quan hệ dạng [:{r_type}].")

    def get_statistics(self) -> Dict[str, Any]:
        """Lấy số lượng node và relationship chi tiết trong Neo4j."""
        with self.driver.session() as session:
            # Đếm theo Label
            labels = ["Course", "Lecturer", "Assessment", "CurriculumBlock"]
            node_counts = {}
            for lbl in labels:
                res = session.run(f"MATCH (n:{lbl}) RETURN count(n) AS count")
                node_counts[lbl] = res.single()["count"]

            # Đếm theo Relationship Type
            rel_res = session.run("MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS count")
            rel_stats = {record["rel_type"]: record["count"] for record in rel_res}

            return {
                "nodes": node_counts,
                "total_nodes": sum(node_counts.values()),
                "relationships": rel_stats,
                "total_relationships": sum(rel_stats.values()),
            }


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=== TIẾN HÀNH NẠP KNOWLEDGE GRAPH ĐA THỰC THỂ VÀO NEO4J ===")
    try:
        with Neo4jManager() as manager:
            # 1. Tạo ràng buộc duy nhất
            manager.create_constraints()

            # 2. Xóa dữ liệu cũ để đồng bộ dữ liệu sạch mới nhất
            manager.clear_database()

            # 3. Nạp dữ liệu từ curriculum_graph.json
            manager.import_curriculum()

            # 4. Thống kê kiểm tra lại
            stats = manager.get_statistics()
            print("\n" + "=" * 55)
            print(" THỐNG KÊ KNOWLEDGE GRAPH TRONG NEO4J:")
            print(f"  • Tổng số Thực thể (Nodes): {stats['total_nodes']}")
            for lbl, cnt in stats["nodes"].items():
                print(f"    - ({lbl}): {cnt}")
            print(f"  • Tổng số Quan hệ (Relationships): {stats['total_relationships']}")
            for r_type, count in stats["relationships"].items():
                print(f"    - [:{r_type}]: {count}")
            print("=" * 55 + "\n")
            print(f"URI: {NEO4J_URI} | User: {NEO4J_USERNAME}")
    except Exception as e:
        print(f"[X] Lỗi trong quá trình thao tác Neo4j: {e}")
        print("[*] Gợi ý: Hãy đảm bảo Docker container Neo4j đang chạy (`docker start neo4j-dath` hoặc tương tự).")