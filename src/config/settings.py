"""Global configuration and environment variable loader."""
import os
from pathlib import Path #Tự động đảm bảo cú pháp đường dẫn phù hợp với từng HDH

# Đường dẫn gốc dự án
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Tải biến môi trường từ .env nếu có
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

# Đường dẫn dữ liệu
DATA_DIR = BASE_DIR / "data"
RAW_DATA_1_DIR = DATA_DIR / "raw" / "Raw_data_1"
RAW_DATA_2_DIR = DATA_DIR / "raw" / "Raw_data_2"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_1_DIR = PROCESSED_DIR / "output_1"
OUTPUT_2_DIR = PROCESSED_DIR / "output_2"
GRAPH_TRIPLETS_DIR = DATA_DIR / "graph_triplets"
TEST_DATASETS_DIR = DATA_DIR / "test_datasets"
# Cấu hình Neo4j
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")