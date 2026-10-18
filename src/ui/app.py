"""BK Scholar – Streamlit Chat UI (NotebookLM / Gemini style).

Run:  streamlit run src/ui/app.py
"""

from __future__ import annotations

import html
import base64
import json
import sys
import time
from pathlib import Path
from typing import Any

import streamlit as st

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="BK Scholar · Trợ lý học vụ",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Knowledge sources shown in sidebar
# ---------------------------------------------------------------------------
SUGGESTIONS = [
    "Môn Trí tuệ nhân tạo có những môn tiên quyết nào?",
    "GPA dưới 1.0 thì sinh viên có bị cảnh báo học vụ không?",
    "Môn CO2003 có bao nhiêu tín chỉ và học nội dung gì?",
    "Gợi ý lộ trình học để đăng ký môn CO3033.",
]

# ╔═════════════════════════════════════════════════════════════════════════╗
# ║  Theme: colour tokens injected as CSS custom properties               ║
# ╚═════════════════════════════════════════════════════════════════════════╝

_DARK = {
    "bg":              "#0f0f11",
    "surface":         "#1b1b1f",
    "surface-dim":     "#141416",
    "surface-bright":  "#252529",
    "outline":         "rgba(255,255,255,0.08)",
    "outline-variant": "rgba(255,255,255,0.16)",
    "fg":              "#ffffff",
    "fg-muted":        "#b0b0b8",
    "accent":          "#8ab4f8",
    "accent-glow":     "rgba(138,180,248,0.18)",
    "accent-gradient": "linear-gradient(135deg,#4285f4,#a855f7 55%,#ec4899)",
    "shadow":          "rgba(0,0,0,0.35)",
    # tint chips
    "tint-blue":       "rgba(138,180,248,0.14)",
    "on-tint-blue":    "#8ab4f8",
    "tint-green":      "rgba(52,168,83,0.14)",
    "on-tint-green":   "#81c995",
    "tint-amber":      "rgba(251,188,4,0.14)",
    "on-tint-amber":   "#fdd663",
    "tint-red":        "rgba(234,67,53,0.14)",
    "on-tint-red":     "#f28b82",
}

_LIGHT = {
    "bg":              "#f8f9fa",
    "surface":         "#ffffff",
    "surface-dim":     "#f1f3f4",
    "surface-bright":  "#e8eaed",
    "outline":         "#dadce0",
    "outline-variant": "#c4c7c5",
    "fg":              "#1f1f1f",
    "fg-muted":        "#5f6368",
    "accent":          "#1a73e8",
    "accent-glow":     "rgba(26,115,232,0.15)",
    "accent-gradient": "linear-gradient(135deg,#4285f4,#a855f7 55%,#ec4899)",
    "shadow":          "rgba(0,0,0,0.08)",
    "tint-blue":       "rgba(26,115,232,0.10)",
    "on-tint-blue":    "#1967d2",
    "tint-green":      "rgba(24,128,56,0.10)",
    "on-tint-green":   "#188038",
    "tint-amber":      "rgba(234,160,0,0.12)",
    "on-tint-amber":   "#b06000",
    "tint-red":        "rgba(197,34,31,0.10)",
    "on-tint-red":     "#c5221f",
}


def _inject_theme() -> None:
    dark = st.session_state.get("dark_mode", True)
    palette = _DARK if dark else _LIGHT
    props = ";".join(f"--{k}:{v}" for k, v in palette.items())
    css_file = Path(__file__).with_name("styles.css")
    css = css_file.read_text(encoding="utf-8") if css_file.exists() else ""
    scheme = "dark" if dark else "light"
    st.markdown(
        f"<style>:root{{{props};color-scheme:{scheme}}}\n{css}</style>",
        unsafe_allow_html=True,
    )


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║  Session state                                                        ║
# ╚═════════════════════════════════════════════════════════════════════════╝

def _init() -> None:
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("pending_question", None)
    st.session_state.setdefault("dark_mode", True)


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║  vis.js Knowledge Graph renderer                                      ║
# ╚═════════════════════════════════════════════════════════════════════════╝

def _render_graph(graph_data: dict[str, Any] | None) -> None:
    if not graph_data:
        return
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    if not nodes:
        return

    dark = st.session_state.get("dark_mode", True)

    # ── Colour palette keyed by the hint colour each node carries ──
    # Maps the original node["color"] → { bg, border, text } pastel set.
    _PALETTE = {
        "#34a853": {"bg": "#dce8fc", "border": "#8babd9", "text": "#3b5998"},  # Cơ sở  (blue-ish)
        "#4285f4": {"bg": "#e8dff5", "border": "#a68bc7", "text": "#5b3a8c"},  # Toán   (purple)
        "#fbbc04": {"bg": "#dce8fc", "border": "#8babd9", "text": "#3b5998"},  # Nền tảng (blue)
        "#a142f4": {"bg": "#dff5e8", "border": "#7cc09e", "text": "#2d6e4f"},  # Chuyên ngành (green)
    }
    _DEFAULT = {"bg": "#e4eaf0", "border": "#8babd9", "text": "#3b5998"}

    # Build enriched node list with individual pastel colours
    enriched_nodes = []
    for nd in nodes:
        pal = _PALETTE.get(nd.get("color"), _DEFAULT)
        enriched_nodes.append({
            "id": nd["id"],
            "label": nd.get("label", nd["id"]),
            "color": {
                "background": pal["bg"],
                "border": pal["border"],
                "highlight": {"background": pal["bg"], "border": pal["border"]},
                "hover":      {"background": pal["bg"], "border": pal["border"]},
            },
            "font": {"color": pal["text"], "face": "Segoe UI, Arial, sans-serif",
                     "size": 13, "bold": {"color": pal["text"], "size": 14}},
        })

    # Background / foreground tokens for dark / light mode
    canvas_bg   = "#1e1e24" if dark else "#fafbfc"
    header_bg   = "#26262e" if dark else "#f2f4f6"
    header_fg   = "#d0d0d8" if dark else "#3c3c3c"
    edge_color  = "#8babd9" if dark else "#8babd9"
    label_color = "#9a9ab0" if dark else "#6b6b80"
    footer_fg   = "#7a7a90" if dark else "#6b7b6b"
    border_clr  = "rgba(255,255,255,0.06)" if dark else "#e2e6ea"

    nodes_json = json.dumps(enriched_nodes, ensure_ascii=False)
    edges_json = json.dumps(edges, ensure_ascii=False)

    html_src = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<script src="https://unpkg.com/vis-network@9/standalone/umd/vis-network.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{background:{canvas_bg};overflow:hidden;font-family:'Segoe UI',Arial,sans-serif;height:100%;width:100%}}
.wrap{{width:100%;height:100%;border:1px solid {border_clr};border-radius:12px;overflow:hidden;background:{canvas_bg}}}
.hdr{{display:flex;justify-content:space-between;align-items:center;padding:10px 16px;background:{header_bg};border-bottom:1px solid {border_clr};font-size:13px;font-weight:600;color:{header_fg}}}
.hdr .hint{{font-weight:400;font-size:11.5px;color:{label_color};opacity:.85}}
#g{{width:100%;height:340px}}
.ftr{{display:flex;justify-content:space-between;align-items:center;padding:6px 14px;background:{header_bg};border-top:1px solid {border_clr};font-size:11px;color:{footer_fg}}}
.ftr .zoom-info{{display:flex;align-items:center;gap:2px}}
.ftr button{{background:none;border:1px solid {border_clr};border-radius:4px;width:24px;height:24px;font-size:14px;color:{footer_fg};cursor:pointer;display:grid;place-items:center}}
.ftr button:hover{{background:{canvas_bg}}}
</style></head><body>
<div class="wrap">
  <div class="hdr">
    <span>Đồ thị chương trình học</span>
    <span class="hint">▷ Có thể kéo và zoom</span>
  </div>
  <div id="g"></div>
  <div class="ftr">
    <span class="zoom-info" id="zl">100% · Mức thu phóng</span>
    <span style="display:flex;gap:4px">
      <button onclick="w.moveTo({{scale:w.getScale()*0.8,animation:true}})" title="Thu nhỏ">−</button>
      <button onclick="w.moveTo({{scale:w.getScale()*1.25,animation:true}})" title="Phóng to">+</button>
      <button onclick="w.fit({{animation:true}})" title="Vừa khung">⛶</button>
    </span>
  </div>
</div>
<script>
var n=new vis.DataSet({nodes_json});
var e=new vis.DataSet({edges_json}.map(function(edge){{
  var lbl=(edge.label||'').replace('TIÊN QUYẾT','Tiên quyết').replace('HỌC TRƯỚC','Học trước');
  return Object.assign({{}},edge,{{
    label:lbl,
    font:{{color:'{label_color}',face:'Segoe UI,Arial,sans-serif',size:11,
           strokeWidth:0,background:'{canvas_bg}',align:'top'}},
    color:{{color:'{edge_color}',highlight:'{edge_color}',hover:'{edge_color}'}},
    title:lbl
  }});
}}));
var c=document.getElementById('g');
var o={{
  autoResize:true,
  nodes:{{
    shape:'box',
    margin:{{top:12,bottom:12,left:18,right:18}},
    borderWidth:2,
    borderWidthSelected:2.5,
    shapeProperties:{{borderRadius:12}},
    shadow:{{enabled:true,color:'rgba(0,0,0,0.06)',size:8,x:0,y:3}}
  }},
  edges:{{
    arrows:{{to:{{enabled:true,scaleFactor:0.7,type:'arrow'}}}},
    width:1.8,
    hoverWidth:0.3,
    smooth:{{type:'cubicBezier',forceDirection:'horizontal',roundness:0.35}}
  }},
  layout:{{hierarchical:{{
    enabled:true,direction:'LR',sortMethod:'directed',
    levelSeparation:200,nodeSpacing:90,treeSpacing:40,
    blockShifting:true,edgeMinimization:true
  }}}},
  interaction:{{
    hover:true,tooltipDelay:150,
    navigationButtons:false,
    zoomView:true,zoomSpeed:0.6,
    dragNodes:true,dragView:true
  }},
  physics:{{enabled:false}}
}};
var w=new vis.Network(c,{{nodes:n,edges:e}},o);
setTimeout(function(){{w.fit({{animation:{{duration:300}}}});}},150);
window.onresize=function(){{w.fit();}};
w.on('zoom',function(){{
  document.getElementById('zl').textContent=Math.round(w.getScale()*100)+'% · Mức thu phóng';
}});
</script></body></html>"""
    st.components.v1.html(html_src, height=420, scrolling=False)


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║  Backend / demo responses                                             ║
# ╚═════════════════════════════════════════════════════════════════════════╝

def _get_response(question: str) -> dict[str, Any]:
    # Try real backend first
    if (ROOT / "src/engine/app_service.py").is_file():
        try:
            from src.engine.app_service import answer_question  # type: ignore
            hist = [{"role": m["role"], "content": m.get("content", "")}
                    for m in st.session_state.messages[-4:]]
            r = answer_question(question=question, history=hist)
            if hasattr(r, "model_dump"):
                r = r.model_dump()
            return {
                "answer": r.get("answer", ""),
                "references": r.get("references") or r.get("citations") or [],
                "graph_data": r.get("graph_data"),
                "intent": r.get("intent", "Backend"),
                "verified": True,
            }
        except Exception:
            pass  # fall through to demo

    lo = question.casefold()

    if any(k in lo for k in ("tiên quyết", "co3033", "trí tuệ nhân tạo", "lộ trình", "học trước")):
        return {
            "answer": (
                "Dựa trên **Đồ thị Tiên quyết KHMT 2024** và **Đề cương CO3033** ¹, "
                "môn **CO3033 – Trí tuệ Nhân tạo** (3 TC) yêu cầu:\n\n"
                "### Chuỗi tiên quyết bắt buộc\n"
                "- **CO1003 – Nhập môn Lập trình** (3 TC) → Bắt buộc đạt trước CO2003.\n"
                "- **CO2003 – Cấu trúc Dữ liệu & Giải thuật** (4 TC) → **Tiên quyết trực tiếp** của CO3033.\n"
                "- **CO3033 – Trí tuệ Nhân tạo** (3 TC) → Chỉ đăng ký khi đạt CO2003.\n\n"
                "### Khuyến nghị học trước\n"
                "- **MT2013 – Xác suất Thống kê** → Nền tảng cho Machine Learning ².\n\n"
                "Bạn có thể xem đồ thị suy luận tiên quyết ở ngay bên dưới."
            ),
            "references": [
                {"code": "[1]", "title": "Chương trình ĐT KHMT 2024 · Bảng tiên quyết",
                 "source": "Neo4j KG – Khoa KH&KT Máy tính",
                 "chunk": "CO3033 yêu cầu tiên quyết CO2003. Sinh viên chưa đạt CO2003 không được đăng ký CO3033."},
                {"code": "[2]", "title": "Đề cương CO3033 · Mục 4 – Kiến thức nền tảng",
                 "source": "Văn bản 342/ĐHBK-ĐT",
                 "chunk": "Xác suất thống kê (MT2013), Đại số tuyến tính (MT1007), lập trình Python/C++."},
            ],
            "graph_data": {
                "nodes": [
                    {"id": "CO1003", "label": "CO1003\nNhập môn LT",       "color": "#34a853"},
                    {"id": "MT2013", "label": "MT2013\nXác suất TK",       "color": "#4285f4"},
                    {"id": "CO2003", "label": "CO2003\nCấu trúc DL&GT",    "color": "#fbbc04"},
                    {"id": "CO3033", "label": "CO3033\nTrí tuệ Nhân tạo",  "color": "#a142f4"},
                ],
                "edges": [
                    {"from": "CO1003", "to": "CO2003", "label": "TIÊN QUYẾT"},
                    {"from": "CO2003", "to": "CO3033", "label": "TIÊN QUYẾT"},
                    {"from": "MT2013", "to": "CO3033", "label": "HỌC TRƯỚC"},
                ],
            },
            "intent": "UC2 · Suy luận đồ thị",
            "verified": True,
        }

    if any(k in lo for k in ("gpa", "cảnh báo", "học vụ", "thôi học")):
        return {
            "answer": (
                "Theo **Quy chế Đào tạo ĐH Chính quy 2024** ¹:\n\n"
                "### Cảnh báo học vụ mức 1\n"
                "- GPA học kỳ **< 1.00** (HK đầu) hoặc **< 1.20** (HK sau).\n\n"
                "### Cảnh báo mức 2\n"
                "- Bị mức 1 trong **2 HK liên tiếp**, hoặc > 50 % tín chỉ không đạt ².\n\n"
                "### Buộc thôi học\n"
                "- Mức 2 + HK tiếp vẫn không đạt ngưỡng, hoặc quá 12 HK chính.\n\n"
                "⚠️ *Nếu đang cảnh báo, nên giới hạn ≤ 14 TC và ưu tiên trả nợ môn cơ sở.*"
            ),
            "references": [
                {"code": "[1]", "title": "Quy chế ĐT ĐH 2024 · Điều 19 – Cảnh báo học vụ",
                 "source": "Văn bản hợp nhất ĐHBK",
                 "chunk": "GPA HK < 1.00 (HK1) hoặc < 1.20 (HK sau) → Cảnh báo mức 1."},
                {"code": "[2]", "title": "Quy chế ĐT ĐH 2024 · Điều 20 – Buộc thôi học",
                 "source": "Văn bản hợp nhất ĐHBK",
                 "chunk": "Cảnh báo 3 lần liên tiếp → xem xét buộc thôi học."},
            ],
            "graph_data": None,
            "intent": "UC3 · Quy chế học vụ",
            "verified": True,
        }

    if any(k in lo for k in ("co2003", "cấu trúc dữ liệu", "tín chỉ")):
        return {
            "answer": (
                "Theo **Đề cương CO2003** ¹:\n\n"
                "- **Tín chỉ:** 4 (3 LT + 1 TH)\n"
                "- **Nội dung:** Linked List, Stack/Queue, BST, AVL, Hash, BFS/DFS, Dijkstra, MST.\n"
                "- **Tiên quyết:** CO1003 – Nhập môn Lập trình ².\n\n"
                "CO2003 là nền tảng bắt buộc trước CO3033 (AI), CO2013 (CSDL) và CO2011 (HĐH)."
            ),
            "references": [
                {"code": "[1]", "title": "Đề cương CO2003 (2024)",
                 "source": "Khoa KH&KT Máy tính",
                 "chunk": "Mã: CO2003. Khối lượng: 4(3.1.8). Tiên quyết: CO1003."},
                {"code": "[2]", "title": "Khung CT Kỹ sư KHMT 2024",
                 "source": "Chương trình chuẩn",
                 "chunk": "CO2003 bắt buộc trước CO3033, CO2011, CO2013."},
            ],
            "graph_data": {
                "nodes": [
                    {"id": "CO1003", "label": "CO1003\nNhập môn LT",    "color": "#34a853"},
                    {"id": "CO2003", "label": "CO2003\nCấu trúc DL",    "color": "#fbbc04"},
                    {"id": "CO3033", "label": "CO3033\nTrí tuệ NT",     "color": "#a142f4"},
                    {"id": "CO2013", "label": "CO2013\nCơ sở DL",       "color": "#ea4335"},
                ],
                "edges": [
                    {"from": "CO1003", "to": "CO2003", "label": "TIÊN QUYẾT"},
                    {"from": "CO2003", "to": "CO3033", "label": "TIÊN QUYẾT"},
                    {"from": "CO2003", "to": "CO2013", "label": "TIÊN QUYẾT"},
                ],
            },
            "intent": "UC1 · Vector retrieval",
            "verified": True,
        }

    return {
        "answer": (
            f"Tôi đã nhận câu hỏi: *\"{question}\"*.\n\n"
            "Hệ thống **Neuro-Symbolic RAG** sẽ kết hợp Vector Retrieval, Knowledge Graph "
            "và Symbolic Solver để trả lời chính xác ¹. "
            "Vui lòng nhập rõ mã môn (CO3033, CO2003…) hoặc điều khoản quy chế cần tra."
        ),
        "references": [
            {"code": "[1]", "title": "Cơ sở tri thức BK Scholar",
             "source": "Hệ thống RAG ĐHBK",
             "chunk": "Tổng hợp từ Quy chế đào tạo và đồ thị môn học Khoa KH&KT Máy tính."},
        ],
        "graph_data": None,
        "intent": "AUTO · Đa luồng RAG",
        "verified": True,
    }


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║  Render helpers                                                       ║
# ╚═════════════════════════════════════════════════════════════════════════╝

def _conversation_sources() -> list[dict[str, str]]:
    """Collect cited documents only, without duplicate files."""
    documents = {}
    for message in st.session_state.messages:
        if message.get("role") != "assistant":
            continue
        for ref in message.get("response", {}).get("references", []):
            if isinstance(ref, dict):
                file = str(ref.get("source_file") or ref.get("file_name") or "")
                title = str(ref.get("title") or ref.get("doc_id") or file or ref.get("source") or "").strip()
                source = str(ref.get("source") or "")
                identity = str(ref.get("doc_id") or file or title)
                display = file.replace(chr(92), "/").rsplit("/", 1)[-1] if file else title
            else:
                title = str(ref).strip()
                identity, display, source = title, title, ""
            if title and identity not in documents:
                documents[identity] = {"title": display, "source": source}
    return list(documents.values())


def _toggle_theme() -> None:
    st.session_state.dark_mode = not st.session_state.dark_mode


def _render_sidebar() -> None:
    sources = _conversation_sources()
    with st.sidebar:
        logo = base64.b64encode(
            Path(__file__).with_name("assets").joinpath("hcmut-logo.png").read_bytes()
        ).decode("ascii")
        st.markdown(
            '<div class="sidebar-brand">'
            f'<img src="data:image/png;base64,{logo}" alt="Logo Đại học Bách khoa TP.HCM">'
            '<div><div class="topbar-name">BK Scholar</div>'
            '<div class="topbar-sub">ĐH Bách khoa TP.HCM</div></div></div>',
            unsafe_allow_html=True,
        )
        if st.button("＋ Chat mới", key="new_chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.pending_question = None
            st.rerun()
        with st.container(key="sidebar_sources"):
            _render_source_list(sources)
        with st.container(key="sidebar_theme"):
            st.button(
                "", key="theme_switch",
                icon=":material/light_mode:" if st.session_state.dark_mode else ":material/dark_mode:",
                help="Chuyển sang nền sáng" if st.session_state.dark_mode else "Chuyển sang nền tối",
                on_click=_toggle_theme,
            )


def _render_source_list(sources: list[dict[str, str]]) -> None:
        st.markdown(
            '<div class="sb-header"><span class="sb-title">Nguồn tài liệu</span>'
            f'<span class="sb-count">{len(sources)}</span></div>',
            unsafe_allow_html=True,
        )
        if not sources:
            st.markdown(
                '<div class="sources-empty">Chưa có tài liệu được trích dẫn.<br>'
                'Nguồn trong câu trả lời sẽ xuất hiện ở đây.</div>',
                unsafe_allow_html=True,
            )
        for source in sources:
            st.markdown(
                '<div class="src-card"><div class="document-symbol">▤</div>'
                '<div class="source-details">'
                f'<div class="src-name">{html.escape(source["title"])}</div>'
                f'<div class="src-meta">{html.escape(source["source"])}</div>'
                '</div></div>',
                unsafe_allow_html=True,
            )


def _render_hero() -> None:
    st.markdown(
        '<div class="hero">'
        ''
        '<h1>Xin chào! Mình là BK Scholar</h1>'
        '<p>Bạn muốn tìm hiểu gì về môn học hoặc quy chế học vụ?</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="sug-label">Gợi ý để bắt đầu</div>', unsafe_allow_html=True)
    cols = st.columns(2)
    for i, q in enumerate(SUGGESTIONS):
        with cols[i % 2]:
            if st.button(q, key=f"sug_{i}", use_container_width=True):
                st.session_state.pending_question = q
                st.rerun()


def _render_assistant(msg: dict[str, Any], idx: int) -> None:
    resp = msg.get("response", {})
    verified = resp.get("verified", False) and (ROOT / "src/engine/app_service.py").is_file()
    refs = resp.get("references", [])

    label = "Đã đối chiếu nguồn" if verified else "Dữ liệu minh họa"
    st.markdown(f'<div class="answer-label">BK Scholar <span>· {label}</span></div>', unsafe_allow_html=True)

    content = msg.get("content", "")
    for dot in ("🟢", "🟡", "🟣", "🔵"):
        content = content.replace(dot + " ", "").replace(dot, "")
    st.markdown(content)

    # Graph
    _render_graph(resp.get("graph_data"))

    # Citations
    if refs:
        with st.expander(f"Trích dẫn nguồn ({len(refs)})"):
            for ref in refs:
                if isinstance(ref, dict):
                    st.markdown(
                        f'<div class="cite-card">'
                        f'<span class="cite-badge">{ref.get("code","")}</span>'
                        f'<strong>{html.escape(ref.get("title",""))}</strong>'
                        f' <span class="cite-source">– {html.escape(ref.get("source",""))}</span>'
                        f'<div class="cite-chunk">{html.escape(ref.get("chunk",""))}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f'<div class="cite-card"><strong>{html.escape(str(ref))}</strong></div>',
                        unsafe_allow_html=True,
                    )


# ╔═════════════════════════════════════════════════════════════════════════╗
# ║  Main                                                                 ║
# ╚═════════════════════════════════════════════════════════════════════════╝

def _render_user(content: str) -> None:
    # One flex row avoids Streamlit's nested full-width Markdown wrappers.
    st.markdown(
        '<div class="user-chat-row" aria-label="Tin nhắn của bạn">'
        f'<div class="user-chat-bubble">{html.escape(content)}</div>'
        '<div class="user-chat-avatar" aria-hidden="true">🧑‍🎓</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def _assistant_avatar() -> str:
    """Streamlit accepts SVG image data as a chat avatar."""
    import base64

    dark = st.session_state.get("dark_mode", True)
    background, foreground = ("#252529", "#ffffff") if dark else ("#e8eaed", "#1f1f1f")
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">'
        f'<rect width="40" height="40" rx="10" fill="{background}"/>'
        f'<text x="20" y="26" text-anchor="middle" font-family="Arial,sans-serif" '
        f'font-size="18" font-weight="600" fill="{foreground}">Bk</text></svg>'
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def main() -> None:
    _init()
    _inject_theme()
    _render_sidebar()

    mode = "Tích hợp backend" if (ROOT / "src/engine/app_service.py").is_file() else "Bản demo giao diện"
    if mode == "Bản demo giao diện":
        st.caption("Bản xem trước giao diện · Dữ liệu minh họa")

    # ── Messages ──
    if not st.session_state.messages:
        _render_hero()
    else:
        for i, m in enumerate(st.session_state.messages):
            if m["role"] == "user":
                _render_user(m["content"])
            else:
                with st.chat_message("assistant", avatar=_assistant_avatar()):
                    _render_assistant(m, i)

    # ── Input ──
    pending = st.session_state.pop("pending_question", None)
    question = st.chat_input("Đặt câu hỏi về học vụ…") or pending
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        _render_user(question)
        with st.chat_message("assistant", avatar=_assistant_avatar()):
            with st.spinner("Đang truy xuất và kiểm chứng nguồn…"):
                time.sleep(0.3)
                resp = _get_response(question)
            ans = {"role": "assistant", "content": resp["answer"], "response": resp}
            _render_assistant(ans, len(st.session_state.messages))
            st.session_state.messages.append(ans)
            st.rerun()

    st.markdown(
        '<div class="footer-note">'
        'BK Scholar có thể mắc lỗi. Hãy đối chiếu văn bản chính thức trước khi đưa ra quyết định học vụ.'
        '</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
