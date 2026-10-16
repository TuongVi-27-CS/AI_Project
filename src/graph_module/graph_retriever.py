"""
Graph context retriever executing Cypher queries directly against Neo4j.
Hoàn toàn sử dụng cơ sở dữ liệu đồ thị Neo4j (Đã loại bỏ cơ chế Local Fallback).
Tuân thủ nghiêm ngặt Hợp đồng dữ liệu `src.engine.schema.ContextResult`.
"""
import os
import sys
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Set

# Đảm bảo thư mục gốc dự án luôn nằm trong sys.path để import được src
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from neo4j import GraphDatabase, exceptions as neo4j_exceptions
from src.config.settings import (
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD,
)
from src.engine.schema import ContextResult
from src.graph_module.query_parser import GraphQueryParser, ParsedQueryEntities
import unicodedata


def remove_accents(input_str: str) -> str:
    """
    Chuyển đổi chuỗi tiếng Việt có dấu thành không dấu chữ thường:
    Ví dụ: 'Nguyễn Đức Dũng' -> 'nguyen duc dung', 'Cấu trúc Dữ liệu' -> 'cau truc du lieu'.
    """
    if not input_str:
        return ""
    s = str(input_str).replace("đ", "d").replace("Đ", "D")
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).lower().strip()


class GraphRetriever:
    """
    Bộ truy vấn đồ thị tri thức (Knowledge Graph Retriever).
    Thực thi 100% bằng Cypher Query trực tiếp trên Neo4j:
    - Bóc tách thực thể (Môn học, Giảng viên, Khối kiến thức).
    - Truy vấn quan hệ đa thực thể (Tiên quyết, Giảng dạy, Đánh giá, Khối CTĐT).
    - Truy vết lộ trình tiên quyết đa bước (Multi-hop Path Traversal).
    - Thu thập toàn bộ `source_locator` phục vụ kiểm chứng chống ảo giác.
    - Đóng gói dữ liệu chuẩn hóa `ContextResult` và định dạng Pyvis cho UI.
    """

    def __init__(
        self,
        uri: str = NEO4J_URI,
        user: str = NEO4J_USERNAME,
        password: str = NEO4J_PASSWORD,
    ):
        self.uri = uri
        self.user = user
        self.password = password
        self.driver = None
        self.query_parser = GraphQueryParser()

    # ==========================================
    # QUẢN LÝ KẾT NỐI NEO4J
    # ==========================================
    def connect(self):
        """Khởi tạo và kiểm tra kết nối tới Neo4j."""
        if not self.driver:
            driver_kwargs = {"auth": (self.user, self.password)}
            try:
                from neo4j import NotificationDisabledClassification
                driver_kwargs["notifications_disabled_classifications"] = [
                    NotificationDisabledClassification.UNRECOGNIZED
                ]
            except (ImportError, AttributeError):
                pass
            self.driver = GraphDatabase.driver(self.uri, **driver_kwargs)
            self.driver.verify_connectivity()

    def close(self):
        """Đóng kết nối driver an toàn."""
        if self.driver:
            self.driver.close()
            self.driver = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # ==========================================
    # ENTITY EXTRACTION TRỰC TIẾP TỪ NEO4J
    # ==========================================
    def extract_course_codes_from_text(self, text: str) -> List[str]:
        """Trích xuất mã môn học chuẩn HCMUT bằng Regex."""
        if not text:
            return []
        normalized = re.sub(r"\b([A-Za-z]{2,4})[\s\-]+(\d{3,4})\b", r"\1\2", text)
        pattern = r"\b([A-Z]{2}\d{4}|SA4001|ENGGC)\b"
        matches = re.findall(pattern, normalized.upper())
        return list(dict.fromkeys(matches))

    def resolve_course_code(self, raw_input: str) -> Optional[str]:
        """Chuẩn hóa và ánh xạ từ viết tắt hoặc tên môn sang mã Course code trong Neo4j."""
        if not raw_input:
            return None
        text_clean = raw_input.strip()

        # 1. Kiểm tra nếu đã đúng format mã môn HCMUT (VD: CO2003, MT1003)
        codes = self.extract_course_codes_from_text(text_clean)
        if codes:
            return codes[0]

        # 2. Bảng ánh xạ từ viết tắt phổ biến
        abbrev_map = {
            "ctdl": "CO2003",
            "cấu trúc dữ liệu": "CO2003",
            "giải thuật": "CO2003",
            "ktlt": "CO1027",
            "kỹ thuật lập trình": "CO1027",
            "ai": "CO3033",
            "trí tuệ nhân tạo": "CO3033",
            "ttnt": "CO3033",
            "hdh": "CO2017",
            "hđh": "CO2017",
            "hệ điều hành": "CO2017",
            "mmt": "CO3093",
            "mạng máy tính": "CO3093",
            "nmlt": "CO1003",
            "nhập môn lập trình": "CO1003",
            "csdl": "CO2013",
            "cơ sở dữ liệu": "CO2013",
            "cnpm": "CO3001",
            "công nghệ phần mềm": "CO3001",
            "ktmt": "CO2007",
            "kiến trúc máy tính": "CO2007",
            "ctrr": "CO1007",
            "cấu trúc rời rạc": "CO1007",
            "toán rời rạc": "CO1007",
            "gt1": "MT1003",
            "giải tích 1": "MT1003",
            "gt2": "MT1005",
            "giải tích 2": "MT1005",
            "dstt": "MT1007",
            "đại số tuyến tính": "MT1007",
            "vl1": "PH1003",
            "vật lý 1": "PH1003",
            "tnvl": "PH1007",
            "thí nghiệm vật lý": "PH1007",
        }
        low = text_clean.lower()
        if low in abbrev_map:
            return abbrev_map[low]

        # 3. Tìm kiếm trong Neo4j theo tên
        self.connect()
        with self.driver.session() as session:
            res = session.run("MATCH (c:Course {code: $code}) RETURN c.code LIMIT 1", code=text_clean.upper())
            rec = res.single()
            if rec:
                return rec["c.code"]

            res = session.run(
                "MATCH (c:Course) WHERE toLower(c.name) CONTAINS toLower($kw) RETURN c.code LIMIT 1",
                kw=text_clean
            )
            rec = res.single()
            if rec:
                return rec["c.code"]

        return text_clean.upper()

    def extract_entities_from_text(self, text: str) -> Dict[str, List[str]]:
        """
        Bóc tách thực thể trực tiếp kết hợp Regex và Cypher matching trên Neo4j:
        - Môn học (Course code hoặc Tên môn tiếng Việt).
        - Giảng viên (Lecturer name).
        - Khối kiến thức (CurriculumBlock id).
        """
        self.connect()
        found_courses = self.extract_course_codes_from_text(text)
        found_lecturers = []
        found_blocks = []

        query_lower = text.lower()

        with self.driver.session() as session:
            # 1. Quét tên môn học trong Neo4j
            c_res = session.run("MATCH (c:Course) RETURN c.code AS code, toLower(c.name) AS name")
            for record in c_res:
                c_name = record["name"]
                if c_name and len(c_name) > 3 and c_name in query_lower:
                    if record["code"] not in found_courses:
                        found_courses.append(record["code"])

            # Từ khóa tên môn học phổ thông
            common_mappings = {
                "trí tuệ nhân tạo": ["CO3033", "GK5041"],
                "cấu trúc dữ liệu": ["CO2003"],
                "giải thuật": ["CO2003"],
                "kỹ thuật lập trình": ["CO1027", "CO1011"],
                "nhập môn lập trình": ["CO1003"],
                "cấu trúc rời rạc": ["CO1007"],
                "toán rời rạc": ["CO1007"],
                "mạng máy tính": ["CO3093"],
                "hệ điều hành": ["CO2017"],
                "giải tích 1": ["MT1003"],
                "giải tích 2": ["MT1005"],
                "đại số tuyến tính": ["MT1007"],
                "vật lý 1": ["PH1003"],
                "thí nghiệm vật lý": ["PH1007"],
            }
            for kw, codes in common_mappings.items():
                if kw in query_lower:
                    for c in codes:
                        if c not in found_courses:
                            found_courses.append(c)

            # 2. Quét tên giảng viên trong Neo4j
            l_res = session.run("MATCH (l:Lecturer) RETURN l.name AS name, toLower(l.name) AS name_lower")
            for record in l_res:
                if record["name_lower"] and record["name_lower"] in query_lower:
                    found_lecturers.append(record["name"])

            # 3. Quét khối kiến thức trong Neo4j
            b_res = session.run("MATCH (b:CurriculumBlock) RETURN b.id AS id, toLower(b.name) AS name")
            for record in b_res:
                if record["name"] and any(kw in query_lower for kw in ["khối", "chuyên ngành", "cơ sở", "tốt nghiệp"]):
                    # So khớp tương đối
                    b_clean = re.sub(r"\(.*?\)", "", record["name"]).strip()
                    if b_clean and b_clean in query_lower:
                        found_blocks.append(record["id"])

        return {
            "courses": list(dict.fromkeys(found_courses)),
            "lecturers": list(dict.fromkeys(found_lecturers)),
            "blocks": list(dict.fromkeys(found_blocks)),
        }

    # ==========================================
    # TRUY VẤN CHI TIẾT MÔN HỌC BẰNG CYPHER (NEO4J)
    # ==========================================
    def get_course_details(self, course_code: str) -> Optional[Dict[str, Any]]:
        """
        Truy vấn toàn bộ quan hệ của môn học trực tiếp từ Neo4j qua Cypher:
        - Môn tiên quyết (PREREQUISITE_FOR).
        - Môn khuyến nghị (RECOMMENDED_FOR).
        - Môn song hành (CO_REQUISITE_FOR).
        - Môn học sau (prerequisite for).
        - Giảng viên phụ trách (TAUGHT_BY).
        - Hình thức đánh giá (EVALUATED_BY).
        - Khối kiến thức CTĐT (CONTAINS).
        - Điều kiện tốt nghiệp (REQUIRES_GRADUATION).
        """
        self.connect()
        code_clean = course_code.strip().upper()

        query = """
        MATCH (c:Course {code: $code})
        OPTIONAL MATCH (prereq:Course)-[r1:PREREQUISITE_FOR]->(c)
        OPTIONAL MATCH (recom:Course)-[r2:RECOMMENDED_FOR]->(c)
        OPTIONAL MATCH (coreq:Course)-[r3:CO_REQUISITE_FOR]-(c)
        OPTIONAL MATCH (c)-[r4:PREREQUISITE_FOR]->(post:Course)
        OPTIONAL MATCH (c)-[r5:TAUGHT_BY]->(lec:Lecturer)
        OPTIONAL MATCH (c)-[r6:EVALUATED_BY]->(ass:Assessment)
        OPTIONAL MATCH (blk:CurriculumBlock)-[r7:CONTAINS]->(c)
        OPTIONAL MATCH (dktn:CurriculumBlock)-[r8:REQUIRES_GRADUATION]->(c)
        RETURN c.code AS code,
               c.name AS name,
               c.credits AS credits,
               c.source_locator AS source_locator,
               collect(DISTINCT {
                   code: prereq.code,
                   name: prereq.name,
                   credits: prereq.credits,
                   source_locator: coalesce(r1.source_locator, prereq.source_locator)
               }) AS prerequisites,
               collect(DISTINCT {
                   code: recom.code,
                   name: recom.name,
                   credits: recom.credits,
                   source_locator: coalesce(r2.source_locator, recom.source_locator)
               }) AS recommended,
               collect(DISTINCT {
                   code: coreq.code,
                   name: coreq.name,
                   credits: coreq.credits,
                   source_locator: coalesce(r3.source_locator, coreq.source_locator)
               }) AS corequisites,
               collect(DISTINCT {
                   code: post.code,
                   name: post.name,
                   credits: post.credits,
                   source_locator: coalesce(r4.source_locator, post.source_locator)
               }) AS prerequisite_for,
               collect(DISTINCT {
                   name: lec.name,
                   email: lec.email,
                   department: lec.department,
                   faculty: lec.faculty,
                   source_locator: coalesce(r5.source_locator, lec.source_locator)
               }) AS lecturers,
               collect(DISTINCT {
                   id: ass.id,
                   name: ass.name,
                   weight: ass.weight,
                   method: ass.method,
                   duration: ass.duration,
                   source_locator: coalesce(r6.source_locator, ass.source_locator)
               }) AS assessments,
               collect(DISTINCT {
                   id: blk.id,
                   name: blk.name,
                   major: blk.major,
                   source_locator: coalesce(r7.source_locator, blk.source_locator)
               }) AS blocks,
               collect(DISTINCT {
                   id: dktn.id,
                   name: dktn.name,
                   major: dktn.major,
                   source_locator: coalesce(r8.source_locator, dktn.source_locator)
               }) AS graduation_reqs
        """
        with self.driver.session() as session:
            res = session.run(query, code=code_clean)
            record = res.single()
            if not record or not record["code"]:
                return None

            return {
                "code": record["code"],
                "name": record["name"],
                "credits": record["credits"],
                "source_locator": record["source_locator"],
                "prerequisites": [p for p in record["prerequisites"] if p.get("code")],
                "recommended": [r for r in record["recommended"] if r.get("code")],
                "corequisites": [cr for cr in record["corequisites"] if cr.get("code")],
                "prerequisite_for": [pf for pf in record["prerequisite_for"] if pf.get("code")],
                "lecturers": [l for l in record["lecturers"] if l.get("name")],
                "assessments": [a for a in record["assessments"] if a.get("id")],
                "blocks": [b for b in record["blocks"] if b.get("id")],
                "graduation_reqs": [g for g in record["graduation_reqs"] if g.get("id")],
            }

    # ==========================================
    # TRUY VẾT LỘ TRÌNH ĐA BẬC CYPHER (NEO4J)
    # ==========================================
    def get_prerequisite_chain(self, course_code: str, max_depth: int = 3) -> List[Dict[str, Any]]:
        """Truy vết chuỗi môn học tiên quyết đa bước bằng Cypher Path Traversal."""
        self.connect()
        code_clean = course_code.strip().upper()

        query = f"""
        MATCH path = (prereq:Course)-[:PREREQUISITE_FOR*1..{max_depth}]->(target:Course {{code: $code}})
        RETURN [n in nodes(path) | {{
                   code: n.code,
                   name: n.name,
                   credits: n.credits,
                   source_locator: n.source_locator
               }}] AS path_nodes,
               [r in relationships(path) | {{
                   type: type(r),
                   source_locator: r.source_locator
               }}] AS path_rels,
               length(path) AS depth
        ORDER BY depth ASC
        """
        with self.driver.session() as session:
            result = session.run(query, code=code_clean)
            paths = []
            for record in result:
                paths.append({
                    "depth": record["depth"],
                    "nodes": record["path_nodes"],
                    "relationships": record["path_rels"],
                })
            return paths

    # ==========================================
    # ĐÓNG GÓI DỮ LIỆU ĐỒ THỊ PYVIS
    # ==========================================
    def format_pyvis_graph_data(
        self,
        target_codes: List[str],
        courses_data: Dict[str, Dict[str, Any]],
        chains_data: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """Chuẩn hóa cấu trúc đồ thị cho thư viện Pyvis."""
        nodes_dict = {}
        edges_list = []
        seen_edges = set()

        for code in target_codes:
            details = courses_data.get(code)
            if not details:
                continue

            # Node Môn học chính (Màu cam)
            nodes_dict[code] = {
                "id": code,
                "label": f"{code}\n{details['name']}",
                "title": f"Môn học: {details['name']}<br>Tín chỉ: {details['credits']}<br>Nguồn: {details.get('source_locator', '')}",
                "color": "#FF9900",
                "shape": "box",
                "font": {"color": "#FFFFFF", "bold": True},
            }

            # Tiên quyết
            for prereq in details.get("prerequisites", []):
                p_code = prereq["code"]
                if p_code not in nodes_dict:
                    nodes_dict[p_code] = {
                        "id": p_code,
                        "label": f"{p_code}\n{prereq.get('name', p_code)}",
                        "title": f"Tín chỉ: {prereq.get('credits', 0)}<br>Nguồn: {prereq.get('source_locator', '')}",
                        "color": "#4A90E2",
                        "shape": "box",
                    }
                e_key = (p_code, code, "PREREQUISITE_FOR")
                if e_key not in seen_edges:
                    seen_edges.add(e_key)
                    edges_list.append({
                        "from": p_code,
                        "to": code,
                        "label": "TIÊN QUYẾT",
                        "title": f"Nguồn: {prereq.get('source_locator', '')}",
                        "arrows": "to",
                        "color": {"color": "#D0021B"},
                    })

            # Khuyến nghị
            for recom in details.get("recommended", []):
                r_code = recom["code"]
                if r_code not in nodes_dict:
                    nodes_dict[r_code] = {
                        "id": r_code,
                        "label": f"{r_code}\n{recom.get('name', r_code)}",
                        "title": f"Tín chỉ: {recom.get('credits', 0)}<br>Nguồn: {recom.get('source_locator', '')}",
                        "color": "#50E3C2",
                        "shape": "box",
                    }
                e_key = (r_code, code, "RECOMMENDED_FOR")
                if e_key not in seen_edges:
                    seen_edges.add(e_key)
                    edges_list.append({
                        "from": r_code,
                        "to": code,
                        "label": "KHUYẾN NGHỊ",
                        "title": f"Nguồn: {recom.get('source_locator', '')}",
                        "arrows": "to",
                        "dashes": True,
                        "color": {"color": "#4A90E2"},
                    })

            # Giảng viên
            for lec in details.get("lecturers", []):
                lec_id = f"LEC_{lec['name']}"
                if lec_id not in nodes_dict:
                    nodes_dict[lec_id] = {
                        "id": lec_id,
                        "label": f"GV: {lec['name']}",
                        "title": f"Email: {lec.get('email', '')}<br>Bộ môn: {lec.get('department', '')}",
                        "color": "#7ED321",
                        "shape": "ellipse",
                    }
                e_key = (code, lec_id, "TAUGHT_BY")
                if e_key not in seen_edges:
                    seen_edges.add(e_key)
                    edges_list.append({
                        "from": code,
                        "to": lec_id,
                        "label": "GIẢNG DẠY",
                        "title": f"Nguồn: {lec.get('source_locator', '')}",
                        "arrows": "to",
                        "color": {"color": "#7ED321"},
                    })

            # Hình thức thi
            for ass in details.get("assessments", []):
                ass_id = ass["id"]
                if ass_id not in nodes_dict:
                    nodes_dict[ass_id] = {
                        "id": ass_id,
                        "label": f"{ass['name']}",
                        "title": f"Trọng số: {ass.get('weight', 0)}%<br>Hình thức: {ass.get('method', '')}",
                        "color": "#F8E71C",
                        "shape": "diamond",
                    }
                e_key = (code, ass_id, "EVALUATED_BY")
                if e_key not in seen_edges:
                    seen_edges.add(e_key)
                    edges_list.append({
                        "from": code,
                        "to": ass_id,
                        "label": f"{ass.get('weight', 0)}%",
                        "title": f"Nguồn: {ass.get('source_locator', '')}",
                        "arrows": "to",
                        "color": {"color": "#F5A623"},
                    })

        # Bổ sung các bước trung gian từ chuỗi đa bước (Chains)
        for code, paths in chains_data.items():
            for p in paths:
                nodes_in_path = p.get("nodes", [])
                for i in range(len(nodes_in_path) - 1):
                    s_n = nodes_in_path[i]
                    t_n = nodes_in_path[i + 1]
                    s_c = s_n["code"]
                    t_c = t_n["code"]

                    if s_c not in nodes_dict:
                        nodes_dict[s_c] = {
                            "id": s_c,
                            "label": f"{s_c}\n{s_n.get('name', s_c)}",
                            "title": f"Nguồn: {s_n.get('source_locator', '')}",
                            "color": "#9B9B9B",
                            "shape": "box",
                        }
                    e_key = (s_c, t_c, "PREREQUISITE_FOR")
                    if e_key not in seen_edges:
                        seen_edges.add(e_key)
                        edges_list.append({
                            "from": s_c,
                            "to": t_c,
                            "label": "TIÊN QUYẾT",
                            "arrows": "to",
                            "color": {"color": "#D0021B"},
                        })

        return {
            "target_entities": target_codes,
            "nodes": list(nodes_dict.values()),
            "edges": edges_list,
        }

    def render_pyvis_html(
        self,
        pyvis_data: Dict[str, Any],
        output_path: Optional[str] = None,
        height: str = "650px",
        width: str = "100%",
        title: str = "HCMUT Academic Knowledge Graph",
    ) -> str:
        """
        Vẽ đồ thị mạng tương tác bằng Pyvis từ dữ liệu pyvis_data và xuất ra mã HTML.
        - Hỗ trợ zoom, pan, kéo thả node (physics simulation mượt mà).
        - Hiển thị đầy đủ màu sắc, tooltip chi tiết và nhãn quan hệ có hướng (arrows).
        - Nếu chỉ định output_path, lưu đồ thị ra file .html.
        """
        try:
            from pyvis.network import Network
        except ImportError:
            print("[!] Thư viện 'pyvis' chưa được cài đặt. Hãy chạy: pip install pyvis")
            return ""

        if not pyvis_data or not pyvis_data.get("nodes"):
            return ""

        net = Network(height=height, width=width, directed=True, notebook=False, cdn_resources="in_line")
        net.heading = title

        # Cấu hình physics trực quan, chống rối dây
        net.set_options("""
        var options = {
          "nodes": {
            "borderWidth": 2,
            "shadow": true
          },
          "edges": {
            "color": { "inherit": false },
            "smooth": { "type": "continuous" },
            "shadow": true
          },
          "physics": {
            "barnesHut": {
              "gravitationalConstant": -4000,
              "centralGravity": 0.3,
              "springLength": 95,
              "springConstant": 0.04,
              "damping": 0.09
            },
            "minVelocity": 0.75
          },
          "interaction": {
            "hover": true,
            "navigationButtons": true,
            "keyboard": true
          }
        }
        """)

        # Thêm nodes
        for node in pyvis_data.get("nodes", []):
            node_id = str(node["id"])
            label = str(node.get("label", node_id))
            title_tooltip = str(node.get("title", label))
            color = node.get("color", "#97C2FC")
            shape = node.get("shape", "box")
            font = node.get("font", {"color": "#000000"})

            net.add_node(
                n_id=node_id,
                label=label,
                title=title_tooltip,
                color=color,
                shape=shape,
                font=font,
            )

        # Thêm edges
        for edge in pyvis_data.get("edges", []):
            src = str(edge["from"])
            dst = str(edge["to"])
            label = str(edge.get("label", ""))
            title_tooltip = str(edge.get("title", ""))
            arrows = str(edge.get("arrows", "to"))
            dashes = edge.get("dashes", False)
            color_prop = edge.get("color")
            color_val = color_prop.get("color") if isinstance(color_prop, dict) else color_prop

            net.add_edge(
                source=src,
                to=dst,
                label=label,
                title=title_tooltip,
                arrows=arrows,
                dashes=dashes,
                color=color_val,
            )

        html_content = net.generate_html()

        if output_path:
            out_file = Path(output_path)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"[+] Đã xuất file đồ thị Pyvis HTML thành công tại: {out_file.resolve()}")

        return html_content

    def visualize(
        self,
        context_result_or_pyvis_data: Any,
        output_file: str = "knowledge_graph.html",
        height: str = "650px",
        width: str = "100%",
    ) -> str:
        """
        API tiện ích: Nhận vào ContextResult hoặc Dict pyvis_data, 
        tự động vẽ và lưu file HTML đồ thị Pyvis tương tác.
        """
        if hasattr(context_result_or_pyvis_data, "raw_data"):
            pyvis_data = context_result_or_pyvis_data.raw_data.get("pyvis", {})
        elif isinstance(context_result_or_pyvis_data, dict):
            if "pyvis" in context_result_or_pyvis_data:
                pyvis_data = context_result_or_pyvis_data["pyvis"]
            else:
                pyvis_data = context_result_or_pyvis_data
        else:
            pyvis_data = {}

        return self.render_pyvis_html(
            pyvis_data=pyvis_data,
            output_path=output_file,
            height=height,
            width=width
        )

    # ==========================================
    # HÀM CHÍNH TRUY XUẤT THEO CHUẨN SCHEMA (API)
    # ==========================================
    def retrieve(
        self,
        query_text: str = "",
        course_codes: Optional[List[str]] = None,
        max_depth: int = 3,
    ) -> ContextResult:
        """
        API chính của Nhánh B (Graph Traversal).
        Áp dụng kiến trúc 2 tầng (Fast-Path Regex & Smart-Path Neuro-LLM).
        Truy vấn 100% qua Neo4j và trả về `ContextResult` chuẩn Pydantic.
        """
        self.connect()
        tier_used = "Chỉ định trực tiếp"
        target_codes = []
        target_lecturers = []
        target_blocks = []

        if course_codes:
            target_codes = list(course_codes)
        elif query_text:
            parsed: ParsedQueryEntities = self.query_parser.parse(query_text)
            target_codes = parsed.course_codes
            target_lecturers = parsed.lecturer_names
            target_blocks = parsed.block_ids
            tier_used = parsed.tier_used

            # Nếu query_parser chưa bắt được, quét thêm trực tiếp từ DB
            if not target_codes and not target_lecturers and not target_blocks:
                entities = self.extract_entities_from_text(query_text)
                target_codes = entities.get("courses", [])
                target_lecturers = entities.get("lecturers", [])
                target_blocks = entities.get("blocks", [])
                tier_used = "Neo4j Database Scan"

        # Entity Resolution mềm cho mã môn học
        resolved_codes = []
        for raw_c in target_codes:
            resolved = self.resolve_course_code(raw_c)
            if resolved and resolved not in resolved_codes:
                resolved_codes.append(resolved)
            elif raw_c and raw_c not in resolved_codes:
                resolved_codes.append(raw_c)
        target_codes = resolved_codes

        # Kiểm tra truy vấn Giảng viên hoặc Khối kiến thức nếu không có mã môn học
        if not target_codes:
            if target_lecturers:
                return self._retrieve_by_lecturers(target_lecturers, tier_used)

            if target_blocks:
                return self._retrieve_by_blocks(target_blocks, tier_used)

            return ContextResult(
                branch_name="Graph_Traversal",
                content=f"[DỮ LIỆU ĐỒ THỊ TRI THỨC (NEO4J - Xử lý qua: {tier_used})]: Không nhận diện được thực thể môn học, giảng viên hay khối kiến thức nào trong câu hỏi.",
                citations=[],
                raw_data={"target_entities": [], "nodes": [], "edges": [], "tier_used": tier_used},
            )

        citations_set: Set[str] = set()
        courses_data: Dict[str, Dict[str, Any]] = {}
        chains_data: Dict[str, List[Dict[str, Any]]] = {}

        formatted_lines = [f"[DỮ LIỆU ĐỒ THỊ TRI THỨC (NEO4J - Xử lý qua: {tier_used})]:\n"]

        for code in target_codes:
            details = self.get_course_details(code)
            if not details:
                formatted_lines.append(f"- Không tìm thấy thông tin môn {code} trong cơ sở dữ liệu Neo4j.")
                continue

            courses_data[code] = details
            if details.get("source_locator"):
                citations_set.add(details["source_locator"])

            tc_str = f" ({details['credits']} tín chỉ)" if details.get("credits", 0) > 0 else ""
            loc_str = f" [Nguồn: {details['source_locator']}]" if details.get("source_locator") else ""
            formatted_lines.append(f"### Môn học: {details['code']} - {details['name']}{tc_str}{loc_str}")

            # 1. Khối kiến thức
            if details.get("blocks"):
                b_names = []
                for b in details["blocks"]:
                    if b.get("source_locator"):
                        citations_set.add(b["source_locator"])
                    b_names.append(f"{b['name']} [Nguồn: {b['source_locator']}]")
                formatted_lines.append(f"  + Thuộc khối kiến thức: {'; '.join(b_names)}")

            # 2. Điều kiện tốt nghiệp
            if details.get("graduation_reqs"):
                formatted_lines.append("  + Đây là điều kiện tốt nghiệp bắt buộc của CTĐT.")
                for g in details["graduation_reqs"]:
                    if g.get("source_locator"):
                        citations_set.add(g["source_locator"])

            # 3. Tiên quyết
            if details["prerequisites"]:
                prereq_items = []
                for p in details["prerequisites"]:
                    if p.get("source_locator"):
                        citations_set.add(p["source_locator"])
                    p_tc = f" ({p['credits']} tín chỉ)" if p.get("credits", 0) > 0 else ""
                    p_loc = f" [Nguồn: {p['source_locator']}]" if p.get("source_locator") else ""
                    prereq_items.append(f"{p['code']} - {p['name']}{p_tc}{p_loc}")
                formatted_lines.append(f"  + Môn tiên quyết bắt buộc (Prerequisites): {'; '.join(prereq_items)}")
            else:
                formatted_lines.append("  + Môn tiên quyết bắt buộc (Prerequisites): Không có")

            # 4. Khuyến nghị
            if details["recommended"]:
                recom_items = []
                for r in details["recommended"]:
                    if r.get("source_locator"):
                        citations_set.add(r["source_locator"])
                    r_loc = f" [Nguồn: {r['source_locator']}]" if r.get("source_locator") else ""
                    recom_items.append(f"{r['code']} - {r['name']}{r_loc}")
                formatted_lines.append(f"  + Môn học trước khuyến nghị (Recommended): {'; '.join(recom_items)}")

            # 5. Song hành
            if details["corequisites"]:
                coreq_items = []
                for cr in details["corequisites"]:
                    if cr.get("source_locator"):
                        citations_set.add(cr["source_locator"])
                    cr_loc = f" [Nguồn: {cr['source_locator']}]" if cr.get("source_locator") else ""
                    coreq_items.append(f"{cr['code']} - {cr['name']}{cr_loc}")
                formatted_lines.append(f"  + Môn học song hành: {'; '.join(coreq_items)}")

            # 6. Giảng viên phụ trách
            if details.get("lecturers"):
                lec_items = []
                for l in details["lecturers"]:
                    if l.get("source_locator"):
                        citations_set.add(l["source_locator"])
                    email_str = f" ({l['email']})" if l.get("email") else ""
                    dept_str = f" - {l['department']}" if l.get("department") else ""
                    lec_items.append(f"{l['name']}{email_str}{dept_str}")
                formatted_lines.append(f"  + Giảng viên phụ trách: {'; '.join(lec_items)}")

            # 7. Hình thức thi
            if details.get("assessments"):
                ass_items = []
                for a in details["assessments"]:
                    if a.get("source_locator"):
                        citations_set.add(a["source_locator"])
                    ass_items.append(f"{a['name']}: {a.get('weight', 0)}%")
                formatted_lines.append(f"  + Hình thức đánh giá: {'; '.join(ass_items)}")

            # 8. Môn học sau
            if details["prerequisite_for"]:
                post_items = [f"{pf['code']} - {pf['name']}" for pf in details["prerequisite_for"]]
                formatted_lines.append(f"  + Là điều kiện tiên quyết cho các môn: {', '.join(post_items)}")

            # 9. Chuỗi lộ trình đa bước
            chains = self.get_prerequisite_chain(code, max_depth=max_depth)
            if chains:
                chains_data[code] = chains
                formatted_lines.append("  + Chuỗi lộ trình tiên quyết đa bước (Multi-hop Dependency Chains):")
                for c in chains:
                    chain_str = " -> ".join([n["code"] for n in c["nodes"]])
                    formatted_lines.append(f"    * [Bậc {c['depth']}]: {chain_str}")
                    for n in c["nodes"]:
                        if n.get("source_locator"):
                            citations_set.add(n["source_locator"])
                    for r in c.get("relationships", []):
                        if r.get("source_locator"):
                            citations_set.add(r["source_locator"])

        # Tạo Pyvis data
        pyvis_data = self.format_pyvis_graph_data(target_codes, courses_data, chains_data)
        raw_output = {
            "target_entities": target_codes,
            "courses": courses_data,
            "chains": chains_data,
            "pyvis": pyvis_data,
        }

        return ContextResult(
            branch_name="Graph_Traversal",
            content="\n".join(formatted_lines),
            citations=sorted(list(citations_set)),
            raw_data=raw_output,
        )

    def _retrieve_by_lecturers(self, lecturer_names: List[str], tier_used: str = "Smart-Path") -> ContextResult:
        """Truy xuất trực tiếp các môn do Giảng viên phụ trách từ Neo4j."""
        self.connect()
        formatted_lines = [f"[DỮ LIỆU ĐỒ THỊ TRI THỨC (TRA CỨU GIẢNG VIÊN - NEO4J - Xử lý qua: {tier_used})]:\n"]
        citations_set = set()
        nodes_dict = {}
        edges_list = []
        seen_edges = set()

        query = """
        MATCH (l:Lecturer)
        WHERE l.name = $name 
           OR toLower(l.name) = toLower($name)
           OR toLower(l.name) CONTAINS toLower($name)
           OR toLower($name) CONTAINS toLower(l.name)
        OPTIONAL MATCH (c:Course)-[r:TAUGHT_BY]->(l)
        RETURN l.name AS name,
               l.email AS email,
               l.department AS department,
               l.faculty AS faculty,
               collect(DISTINCT {
                   code: c.code,
                   name: c.name,
                   credits: c.credits,
                   source_locator: coalesce(r.source_locator, c.source_locator)
               }) AS courses
        """
        with self.driver.session() as session:
            for raw_name in lecturer_names:
                clean_name = re.sub(r"^(thầy|cô|ts\.|pgs\.|gs\.|thay|co)\s+", "", raw_name.strip(), flags=re.IGNORECASE).strip()
                res = session.run(query, name=clean_name)
                records = list(res)
                if not records:
                    continue

                for rec in records:
                    formatted_lines.append(f"### Giảng viên: {rec['name']}")
                    if rec.get("department") or rec.get("faculty"):
                        formatted_lines.append(f"  - Đơn vị: {rec.get('department', '')} ({rec.get('faculty', '')})")
                    if rec.get("email"):
                        formatted_lines.append(f"  - Email: {rec['email']}")

                    lec_id = f"LEC_{rec['name']}"
                    nodes_dict[lec_id] = {
                        "id": lec_id,
                        "label": f"GV: {rec['name']}",
                        "title": f"Email: {rec.get('email', '')}<br>Bộ môn: {rec.get('department', '')}",
                        "color": "#7ED321",
                        "shape": "ellipse"
                    }

                    taught = []
                    for c in rec.get("courses", []):
                        if c.get("code"):
                            taught.append(f"{c['code']} - {c['name']} ({c['credits']} tín chỉ)")
                            if c.get("source_locator"):
                                citations_set.add(c["source_locator"])

                            c_code = c["code"]
                            if c_code not in nodes_dict:
                                nodes_dict[c_code] = {
                                    "id": c_code,
                                    "label": f"{c_code}\n{c['name']}",
                                    "title": f"Môn học: {c['name']}<br>Tín chỉ: {c['credits']}",
                                    "color": "#FF9900",
                                    "shape": "box"
                                }
                            e_key = (c_code, lec_id, "TAUGHT_BY")
                            if e_key not in seen_edges:
                                seen_edges.add(e_key)
                                edges_list.append({
                                    "from": c_code,
                                    "to": lec_id,
                                    "label": "GIẢNG DẠY",
                                    "arrows": "to",
                                    "color": {"color": "#7ED321"}
                                })

                    if taught:
                        formatted_lines.append(f"  - Các môn phụ trách giảng dạy: {'; '.join(taught)}")
                    else:
                        formatted_lines.append("  - Không có thông tin môn học phụ trách.")

        pyvis_data = {
            "target_entities": lecturer_names,
            "nodes": list(nodes_dict.values()),
            "edges": edges_list
        }
        return ContextResult(
            branch_name="Graph_Traversal",
            content="\n".join(formatted_lines),
            citations=sorted(list(citations_set)),
            raw_data={"lecturers": lecturer_names, "pyvis": pyvis_data},
        )

    def _retrieve_by_blocks(self, block_ids: List[str], tier_used: str = "Smart-Path") -> ContextResult:
        """Truy xuất các môn thuộc Khối kiến thức CTĐT trực tiếp từ Neo4j."""
        self.connect()
        formatted_lines = [f"[DỮ LIỆU ĐỒ THỊ TRI THỨC (TRA CỨU KHỐI KIẾN THỨC - NEO4J - Xử lý qua: {tier_used})]:\n"]
        citations_set = set()
        nodes_dict = {}
        edges_list = []
        seen_edges = set()

        query = """
        MATCH (b:CurriculumBlock)
        WHERE b.id = $id 
           OR toLower(b.name) CONTAINS toLower($clean)
           OR toLower($clean) CONTAINS toLower(b.name)
        OPTIONAL MATCH (b)-[r:CONTAINS|REQUIRES_GRADUATION]->(c:Course)
        RETURN b.id AS id,
               b.name AS name,
               b.major AS major,
               collect(DISTINCT {
                   code: c.code,
                   name: c.name,
                   credits: c.credits,
                   source_locator: coalesce(r.source_locator, c.source_locator)
               }) AS courses
        """
        with self.driver.session() as session:
            for b_id in block_ids:
                clean_name = re.sub(r"^khối\s+", "", b_id.strip(), flags=re.IGNORECASE).strip()
                res = session.run(query, id=b_id, clean=clean_name)
                records = list(res)
                if not records:
                    continue

                for rec in records:
                    formatted_lines.append(f"### Khối kiến thức: {rec['name']}")
                    blk_id = rec["id"]
                    nodes_dict[blk_id] = {
                        "id": blk_id,
                        "label": rec["name"],
                        "title": f"Khối kiến thức: {rec['name']}<br>Ngành: {rec.get('major', '')}",
                        "color": "#9013FE",
                        "shape": "diamond",
                        "font": {"color": "#FFFFFF", "bold": True}
                    }

                    courses_in_block = []
                    for c in rec.get("courses", []):
                        if c.get("code"):
                            courses_in_block.append(f"{c['code']} - {c['name']} ({c['credits']} tín chỉ)")
                            if c.get("source_locator"):
                                citations_set.add(c["source_locator"])

                            c_code = c["code"]
                            if c_code not in nodes_dict:
                                nodes_dict[c_code] = {
                                    "id": c_code,
                                    "label": f"{c_code}\n{c['name']}",
                                    "title": f"Môn học: {c['name']}<br>Tín chỉ: {c['credits']}",
                                    "color": "#FF9900",
                                    "shape": "box"
                                }
                            e_key = (blk_id, c_code, "CONTAINS")
                            if e_key not in seen_edges:
                                seen_edges.add(e_key)
                                edges_list.append({
                                    "from": blk_id,
                                    "to": c_code,
                                    "label": "CHỨA",
                                    "arrows": "to",
                                    "color": {"color": "#9013FE"}
                                })

                    formatted_lines.append(f"  - Danh sách môn ({len(courses_in_block)} môn): {', '.join(courses_in_block) if courses_in_block else 'Đang cập nhật'}")

        pyvis_data = {
            "target_entities": block_ids,
            "nodes": list(nodes_dict.values()),
            "edges": edges_list
        }
        return ContextResult(
            branch_name="Graph_Traversal",
            content="\n".join(formatted_lines),
            citations=sorted(list(citations_set)),
            raw_data={"blocks": block_ids, "pyvis": pyvis_data},
        )

    # ==========================================
    # CÁC HÀM TIỆN ÍCH CHO ORCHESTRATOR
    # ==========================================
    def get_course_chains(self, course_names_or_codes: List[str], max_depth: int = 3) -> ContextResult:
        """API tiện ích cho Orchestrator (fusion_chain.py)."""
        resolved_codes = []
        for item in course_names_or_codes:
            extracted = self.extract_course_codes_from_text(item)
            if extracted:
                resolved_codes.extend(extracted)
            else:
                ents = self.extract_entities_from_text(item)
                resolved_codes.extend(ents.get("courses", []))
        resolved_codes = list(dict.fromkeys(resolved_codes))
        return self.retrieve(course_codes=resolved_codes, max_depth=max_depth)

    def query_graph_for_rag(self, query_text: str) -> ContextResult:
        """Alias tương thích ngược."""
        return self.retrieve(query_text=query_text)

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=== KIỂM THỬ GRAPH RETRIEVER TRỰC TIẾP TRÊN NEO4J ===")
    test_queries = [
        "Môn CO2003 thuộc khối kiến thức nào và cần tiên quyết môn gì?",    # Fast-Path: mã môn rõ ràng
        "Học CTDL với KTLT thì môn nào là tiên quyết?",                      # Smart-Path: từ viết tắt CTDL, KTLT
        "thay dung khoa may tinh day mon gi vay",                           # Smart-Path: không dấu, tìm giảng viên
        "Khối cơ sở ngành gồm những môn nào?",                              # Smart-Path: tra cứu khối kiến thức
    ]

    with GraphRetriever() as retriever:
        for q in test_queries:
            print("\n" + "=" * 65)
            print(f"[*] CÂU HỎI: {q}")
            res: ContextResult = retriever.retrieve(query_text=q)
            print(f"[*] Branch: {res.branch_name} | Citations: {len(res.citations)} nguồn")
            print("\n[+] CONTENT:\n" + res.content)
            if res.raw_data.get("pyvis", {}).get("nodes"):
                p_nodes = len(res.raw_data["pyvis"]["nodes"])
                p_edges = len(res.raw_data["pyvis"]["edges"])
                print(f"\n[+] PYVIS GRAPH: {p_nodes} nodes, {p_edges} edges")

        # Xuất file HTML demo trực quan cho câu hỏi đầu tiên
        # print("\n" + "=" * 65)
        # print("[*] XUẤT THỬ NGHIỆM ĐỒ THỊ PYVIS RA FILE HTML...")
        # demo_res = retriever.retrieve("Môn CO2003 thuộc khối kiến thức nào và cần tiên quyết môn gì?")
        # demo_html_path = BASE_DIR / "data" / "processed" / "pyvis_graph_demo.html"
        # retriever.visualize(demo_res, output_file=str(demo_html_path))
