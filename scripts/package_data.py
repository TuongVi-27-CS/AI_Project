"""
Script dong goi du lieu Vector (ChromaDB + Vector Artifacts) thanh file zip de chia se qua Google Drive.
Cach dung:
    python scripts/package_data.py
"""
import os
import sys
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "DATA"
OUTPUT_ZIP = ROOT_DIR / "DATA_VECTOR_BUNDLE.zip"

FOLDERS_TO_PACK = [
    DATA_DIR / "chromadb_store",
    DATA_DIR / "vector_artifacts",
]

def package_data():
    print("=" * 60)
    print(" DONG GOI DU LIEU VECTOR RAG CHO THANH VIEN NHOM")
    print("=" * 60)

    for folder in FOLDERS_TO_PACK:
        if not folder.exists():
            print(f"[X] Loi: Khong tim thay thu muc {folder}")
            print("Vui long dam bao ban da chay module vector truoc khi dong goi.")
            sys.exit(1)

    print(f"[*] Dang tao file nén tai: {OUTPUT_ZIP.name} ...")
    
    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zipf:
        for folder in FOLDERS_TO_PACK:
            print(f"  -> Dang nén {folder.relative_to(ROOT_DIR)} ...")
            for root, _, files in os.walk(folder):
                for file in files:
                    full_path = Path(root) / file
                    # Luu giu dung cau truc tuong doi trong thu muc DATA/
                    rel_path = full_path.relative_to(ROOT_DIR)
                    zipf.write(full_path, arcname=str(rel_path))

    size_mb = OUTPUT_ZIP.stat().st_size / (1024 * 1024)
    print("=" * 60)
    print(f"[+] DONG GOI THANH CONG!")
    print(f"  • File: {OUTPUT_ZIP}")
    print(f"  • Dung luong: {size_mb:.2f} MB")
    print("\nBUOC TIEP THEO:")
    print("1. Upload file 'DATA_VECTOR_BUNDLE.zip' len Google Drive / OneDrive cua nhom.")
    print("2. Dan link tai file nay vao file QUICKSTART.md hoac gui truc tiep cho cac thanh vien.")
    print("=" * 60)

if __name__ == "__main__":
    package_data()
