"""检索域（成员 B）：Embedding、向量索引、Top-K/BM25/Hybrid/Reranker。

技术决策（第一周，记录备查）：
  向量库直接封装 chromadb，未使用 LlamaIndex 的 VectorStoreIndex/Retriever。
  原因：D 的 Retriever 协议是自定义 dict 契约（server/core/pipeline.py），
  直接封装对 chroma 1.5.9 的行为（空元数据、异常类型、进程内共享存储）
  更可控；LlamaIndex 仅承担 Embedding 接口（retrieval/embeddings.py）。
"""
