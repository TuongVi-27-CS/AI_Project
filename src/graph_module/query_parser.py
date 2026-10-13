"""
Module bóc tách thực thể câu hỏi sử dụng Groq API siêu tốc.
Chuyên biệt hóa 100% cho Groq LPU với các mô hình:
- openai/gpt-oss-120b (Mặc định: mô hình 120B mạnh mẽ, độ chính xác cao)
- openai/gpt-oss-20b (Tốc độ phản hồi cực nhanh)
- qwen/qwen3.8-27b (Khả năng suy luận ngôn ngữ tốt)
"""
import sys
import os
import re
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env", override=True)
except Exception:
    pass


class ParsedQueryEntities(BaseModel):
    """Cấu trúc dữ liệu thực thể trích xuất bởi LLM."""
    tier_used: str = Field(default="Groq", description="Phương thức bóc tách")
    courses: List[str] = Field(default_factory=list, description="Mã môn học hoặc tên môn học")
    lecturers: List[str] = Field(default_factory=list, description="Tên giảng viên được nhắc đến")
    blocks: List[str] = Field(default_factory=list, description="Tên khối kiến thức hoặc chuẩn tốt nghiệp")
    intent: str = Field(default="general", description="Ý định câu hỏi")

    @property
    def course_codes(self) -> List[str]:
        return self.courses

    @property
    def lecturer_names(self) -> List[str]:
        return self.lecturers

    @property
    def block_ids(self) -> List[str]:
        return self.blocks


class GraphQueryParser:
    """
    Bộ phân tích câu hỏi bằng Groq API siêu tốc.
    Mặc định sử dụng model 'openai/gpt-oss-120b'.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        temperature: float = 0.0,
        timeout: float = 12.0,
    ):
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            print("[!] CẢNH BÁO: Chưa tìm thấy GROQ_API_KEY trong file .env.")
            print("[*] Gợi ý: Hãy tạo API Key miễn phí tại https://console.groq.com/keys và dán vào GROQ_API_KEY.")

        raw_model = model_name or os.getenv("GROQ_MODEL_NAME", "openai/gpt-oss-120b")
        # Chuẩn hóa nếu model trong .env là tên cũ
        if "llama" in raw_model.lower():
            self.model_name = "openai/gpt-oss-120b"
        else:
            self.model_name = raw_model

        self.temperature = temperature
        self.timeout = timeout
        self.client = None

        if self.api_key:
            try:
                from groq import Groq
                self.client = Groq(api_key=self.api_key, timeout=self.timeout)
            except ImportError:
                from openai import OpenAI
                self.client = OpenAI(
                    base_url="https://api.groq.com/openai/v1",
                    api_key=self.api_key,
                    timeout=self.timeout,
                )

    def parse(self, query: str) -> ParsedQueryEntities:
        """
        Gửi câu hỏi người dùng vào Groq để bóc tách thực thể ra định dạng JSON.
        Có cơ chế tự động chuyển đổi sang model dự phòng nếu gặp sự cố.
        """
        if not query or not query.strip():
            return ParsedQueryEntities(tier_used=f"Groq ({self.model_name})")

        if not self.client:
            return ParsedQueryEntities(tier_used="Groq (Chưa có API Key)")

        prompt = f"""Bạn là trợ lý trích xuất thực thể học vụ ĐH Bách Khoa (HCMUT).
Nhiệm vụ: Trích xuất môn học (mã hoặc tên/từ viết tắt), giảng viên (bỏ từ xưng hô thầy/cô), khối kiến thức và ý định câu hỏi.
Quy tắc Intent:
- "prerequisites": hỏi điều kiện tiên quyết, học trước, song hành.
- "lecturer_info": hỏi giảng viên dạy môn gì, liên hệ.
- "evaluation": hỏi hình thức thi, tỷ lệ điểm, bài tập lớn.
- "block_info": hỏi danh sách môn trong khối kiến thức.
- "general": câu hỏi khác.
Ví dụ:
1. "Học CTDL với KTLT môn nào tiên quyết?" -> {{"courses": ["CTDL", "KTLT"], "lecturers": [], "blocks": [], "intent": "prerequisites"}}
2. "thay dung, hung khoa may tinh day mon gi" -> {{"courses": [], "lecturers": ["Dũng", "Hùng"], "blocks": [], "intent": "lecturer_info"}}
3. "Khối cơ sở ngành gồm môn nào?" -> {{"courses": [], "lecturers": [], "blocks": ["Cơ sở ngành"], "intent": "block_info"}}
Câu hỏi: "{query}"
Chỉ trả về DUY NHẤT chuỗi JSON hợp lệ (không kèm giải thích):
{{
  "courses": ["..."],
  "lecturers": ["..."],
  "blocks": ["..."],
  "intent": "..."
}}"""
        tier_label = f"Groq ({self.model_name})"

        # Danh sách model Groq đang hoạt động
        candidate_models = [
            self.model_name,
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "qwen/qwen3.8-27b",
        ]
        candidate_models = list(dict.fromkeys(candidate_models))

        for model_cand in candidate_models:
            try:
                response = self.client.chat.completions.create(
                    model=model_cand,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that outputs only valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.temperature,
                )
                content = response.choices[0].message.content or ""
                json_match = re.search(r"\{.*\}", content, re.DOTALL)
                if json_match:
                    parsed_json = json.loads(json_match.group(0))
                    return ParsedQueryEntities(
                        tier_used=f"Groq ({model_cand})",
                        courses=parsed_json.get("courses", []) or [],
                        lecturers=parsed_json.get("lecturers", []) or [],
                        blocks=parsed_json.get("blocks", []) or [],
                        intent=parsed_json.get("intent", "general") or "general",
                    )
            except Exception as e:
                err_str = str(e)
                print(f"[*] Groq model {model_cand} gặp sự cố ({err_str[:60]}), chuyển model tiếp theo...")
                time.sleep(0.3)
                continue

        return ParsedQueryEntities(tier_used=tier_label)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=== KIỂM THỬ BÓC TÁCH THỰC THỂ BẰNG GROQ API ===")
    parser = GraphQueryParser()
    print(f"[*] Model mặc định: {parser.model_name}")

    test_queries = [
        "Môn CO2003 thuộc khối kiến thức nào và cần tiên quyết môn gì?",
        "Học CTDL với KTLT thì môn nào là tiên quyết?",
        "thay hung khoa may tinh day mon gi vay",
        "Khối cơ sở ngành gồm những môn nào?",
    ]

    for q in test_queries:
        print("\n" + "-" * 50)
        print(f"[*] Câu hỏi: '{q}'")
        res = parser.parse(q)
        print(f"  -> Model sử dụng: {res.tier_used}")
        print(f"  -> Intent: {res.intent}")
        print(f"  -> Courses: {res.courses}")
        print(f"  -> Lecturers: {res.lecturers}")
        print(f"  -> Blocks: {res.blocks}")
