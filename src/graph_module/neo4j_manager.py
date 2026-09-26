"""Neo4j graph database manager and importer."""
import os
import sys
from pathlib import Path

# Đảm bảo thư mục gốc dự án luôn nằm trong sys.path để import được src
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import json
from neo4j import GraphDatabase
from src.config.settings import (
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD,
    GRAPH_TRIPLETS_DIR,
)

class Neo4jManager:
    """Quản lý kết nối và các thao tác ghi/đọc cơ sở dữ liệu đồ thị Neo4j."""

    def __init__(self, uri=NEO4J_URI, user=NEO4J_USERNAME, password=NEO4J_PASSWORD):
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
        """Đóng kết nối driver."""
        if self.driver:
            self.driver.close()
            self.driver = None
            print("[-] Đã đóng kết nối Neo4j.")

    def __enter__(self): #Tự động gọi connect() khi mở khối lệnh with
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb): #tự động dọn dẹp bằng close() khi kết thúc
        self.close()

    def create_constraints(self):
        """Tạo ràng buộc Unique Constraint trên thuộc tính code của Course để tối ưu tốc độ MERGE/MATCH."""
        query = """
        CREATE CONSTRAINT course_code_unique IF NOT EXISTS
        FOR (c:Course) REQUIRE c.code IS UNIQUE
        """
        with self.driver.session() as session:
            session.run(query)
            print("[+] Đã kiểm tra/tạo Constraint: course_code_unique (Course.code).")

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
        Sử dụng UNWIND batching và MERGE để đảm bảo tính Idempotent (không nhân đôi dữ liệu).
        """
        if json_path is None:
            json_path = GRAPH_TRIPLETS_DIR / "curriculum_graph.json"

        if not Path(json_path).exists():
            raise FileNotFoundError(f"Không tìm thấy file đồ thị tại: {json_path}")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        nodes = data.get("nodes", [])
        relationships = data.get("relationships", [])

        print(f"[*] Chuẩn bị import {len(nodes)} Courses và {len(relationships)} Quan hệ...")

        with self.driver.session() as session:
            # 1. Import Courses (Nodes)
            nodes_query = """
            UNWIND $batch AS item
            MERGE (c:Course {code: item.code})
            SET c.name = item.name,
                c.credits = item.credits
            """
            batch_size = 100
            for i in range(0, len(nodes), batch_size):
                batch = nodes[i:i + batch_size]
                session.run(nodes_query, batch=batch)
            print(f"[+] Đã import thành công {len(nodes)} Course nodes.")

            # 2. Phân loại quan hệ theo loại để thực thi Cypher tối ưu
            rel_by_type = {
                "PREREQUISITE_FOR": [],
                "RECOMMENDED_FOR": [],
                "CO_REQUISITE_FOR": [],
            }
            for rel in relationships:
                r_type = rel.get("type", "RECOMMENDED_FOR")
                if r_type in rel_by_type:
                    rel_by_type[r_type].append(rel)
                else:
                    rel_by_type.setdefault(r_type, []).append(rel)

            # 3. Import từng loại quan hệ (Edges)
            for r_type, rel_list in rel_by_type.items():
                if not rel_list:
                    continue

                rel_query = f"""
                UNWIND $batch AS item
                MATCH (src:Course {{code: item.source}})
                MATCH (tgt:Course {{code: item.target}})
                MERGE (src)-[r:{r_type}]->(tgt)
                """
                for i in range(0, len(rel_list), batch_size):
                    batch = rel_list[i:i + batch_size]
                    session.run(rel_query, batch=batch)
                print(f"[+] Đã tạo {len(rel_list)} quan hệ dạng [:{r_type}].")

    def get_statistics(self):
        """Lấy số lượng node và relationship thực tế trong Neo4j."""
        with self.driver.session() as session:
            node_res = session.run("MATCH (c:Course) RETURN count(c) AS total_courses")
            total_courses = node_res.single()["total_courses"]

            rel_res = session.run("MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS count")
            rel_stats = {record["rel_type"]: record["count"] for record in rel_res}

            return {
                "total_courses": total_courses,
                "relationships": rel_stats
            }


if __name__ == "__main__":
    print("=== TIẾN HÀNH NẠP KNOWLEDGE GRAPH VÀO NEO4J ===")
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
            print("\n" + "="*50)
            print(" THỐNG KÊ KNOWLEDGE GRAPH TRONG NEO4J:")
            print(f"  • Tổng số Course Nodes: {stats['total_courses']}")
            print("  • Chi tiết Relationships:")
            for r_type, count in stats["relationships"].items():
                print(f"    - {r_type}: {count}")
            print("="*50 + "\n")
    except Exception as e:
        print(f"[X] Lỗi trong quá trình thao tác Neo4j: {e}")
        print("[*] Gợi ý: Hãy đảm bảo Docker container Neo4j đang chạy (`docker start neo4j-dath`).")