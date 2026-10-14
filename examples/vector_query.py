"""Run from the repository root: python -m examples.vector_query"""

from src.engine.query_understanding import QueryUnderstanding
from src.engine.vector_pipeline import VectorPipeline


def main():
    # The caller/UI owns history and appends new messages between requests.
    history = [{"role": "user", "content": "Tôi muốn tìm hiểu môn CO1003."}]
    with QueryUnderstanding() as understanding:
        result = VectorPipeline(understanding).run("Môn đó có bao nhiêu tín chỉ?", history)
    print(result.model_dump_json(indent=2))
    return result


if __name__ == "__main__":
    main()
