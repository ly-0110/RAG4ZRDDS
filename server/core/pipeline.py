"""RAG 管线构建器。

职责：组装检索（A）与生成（B）组件，支持 mock/live 两种模式。
Mock 模式：无需真实 PDF 数据即可测试完整流程。
Live 模式：接线到 server/core/rag.py 的真实实现。
"""

from typing import Any
from chromadb.api.models.Collection import Collection


class MockEmbeddingModel:
    """Mock Embedding 模型（用于 mock 模式）。"""
    
    def embed(self, texts: list[str]) -> list[list[float]]:
        """返回全零向量（简化版）。"""
        return [[0.0] * 1024 for _ in texts]


class MockRetriever:
    """Mock 检索器。"""
    
    def __init__(self, collection: Collection):
        self.collection = collection
    
    def query(self, query_text: str, n_results: int = 3) -> dict[str, Any]:
        """返回 mock 检索结果。"""
        return {
            "ids": [["mock_doc_1", "mock_doc_2"]],
            "documents": [["Mock document content"], ["Another mock doc"]],
            "metadatas": [[{"source": "mock"}]],
        }


class MockGenerator:
    """Mock 生成器。"""
    
    def __call__(self, context: list[str]) -> str:
        """返回 mock 答案。"""
        return "这是来自 mock 模式的回答，实际内容取决于上下文。"


def build_pipeline(mode: str, config: dict | None) -> Any:
    """构建 RAG 管线。
    
    Args:
        mode: "mock" 或 "live"
        config: 实验配置（JSON）
    
    Returns:
        Pipeline 对象（包含检索和生成组件）
    """
    if mode == "mock":
        # Mock 模式：无需真实数据
        return {
            "mode": "mock",
            "retriever": MockRetriever(None),
            "generator": MockGenerator(),
        }
    else:
        # Live 模式：接线到真实实现
        raise NotImplementedError("Live 模式需要真实 PDF 数据，请先运行 make index")
