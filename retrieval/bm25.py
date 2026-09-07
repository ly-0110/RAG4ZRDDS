"""BM25 词袋检索：字符 bigram 分词 + rank_bm25。

分词策略（中文手册 + 英文标识符混合场景）：
  * ASCII 词（[a-zA-Z0-9_]+）整体保留并小写——API 名/错误码如
    DomainParticipant、E1003 是精确检索对象，不能切开
  * 中文连续段按相邻两字切 bigram，单字保留 unigram 兜底
  * 其余字符（标点/空白）作分隔符

接口对齐 retrieval/vector_store.py 的 VectorStore（add_nodes/query/save/load），
query 返回 {node_id,text,metadata,score}；score 为原始 BM25 分数，**不做归一化**
（hit_rate/mrr 只依赖排名）。注意 score 量纲与向量检索的 cosine 相似度（0~1）
不可比——实测 301 块语料上 BM25 落在 7.7~56.4，跨模式比较无意义，任何基于
score 的阈值（如「弱证据」判定）必须按 retrieval.mode 分别定标。

零分候选（与查询零词面重叠）会被过滤，故返回条数可能少于 top_k；
返回空列表即「知识库无词面证据」信号，下游据此走拒答路径。
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

from retrieval.nodes import NodeRecord

_ASCII_WORD = re.compile(r"[a-zA-Z0-9_]+")
_CJK_RUN = re.compile(r"[一-鿿]+")

INDEX_FILE = "bm25.json"


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    pos = 0
    for m in _CJK_RUN.finditer(text):
        if m.start() > pos:
            tokens.extend(w.lower() for w in _ASCII_WORD.findall(text[pos:m.start()]))
        run = m.group()
        if len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[i:i + 2] for i in range(len(run) - 1))
        pos = m.end()
    tokens.extend(w.lower() for w in _ASCII_WORD.findall(text[pos:]))
    return tokens


class _PositiveIdfBM25Okapi(BM25Okapi):
    """经典 Robertson idf（log 内 +1，恒正）。

    rank_bm25 自带的 ATIRE idf = log((N−df+0.5)/(df+0.5)) 在 N=2 时恒为 0，
    过滤后只剩少量候选文档会全体并列 0 分、排名退化为插入顺序。
    """

    def _calc_idf(self, nd: dict) -> None:
        idf_sum = 0.0
        for word, freq in nd.items():
            idf = math.log(1.0 + (self.corpus_size - freq + 0.5) / (freq + 0.5))
            self.idf[word] = idf
            idf_sum += idf
        self.average_idf = idf_sum / len(self.idf) if self.idf else 0.0


class BM25Store:
    """BM25 词袋检索（Okapi BM25）；k1/b 为平滑参数，从 cfg.retrieval.params 传入。"""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self._k1 = k1
        self._b = b
        self._nodes: list[NodeRecord] = []
        self._tokens: list[list[str]] = []
        self._bm25 = None

    def add_nodes(self, nodes: list[NodeRecord]) -> None:
        for n in nodes:
            if not (n.text or "").strip():
                continue
            self._nodes.append(n)
            self._tokens.append(tokenize(n.text))
        self._bm25 = None

    def query(self, question: str, top_k: int, filters: dict | None = None) -> list[dict]:
        q_tokens = tokenize(question)
        if not q_tokens or not self._nodes:
            return []
        idxs = list(range(len(self._nodes)))
        if filters:
            idxs = [
                i for i in idxs
                if all(self._nodes[i].metadata.get(k) == v for k, v in filters.items())
            ]
        if self._bm25 is None:
            self._bm25 = _PositiveIdfBM25Okapi(
                self._tokens, k1=self._k1, b=self._b
            )
        scores = self._bm25.get_scores(q_tokens)
        # score == 0 ＝ 与查询零词面重叠，不构成证据。保留会把无关块按插入顺序
        # 填进 top_k 喂给生成侧；过滤后「空结果」成为天然的无证据信号，
        # 下游 query_engine 对空检索有确定性拒答路径。
        matched = [i for i in idxs if scores[i] > 0]
        ranked = sorted(matched, key=lambda i: scores[i], reverse=True)[:top_k]
        return [
            {
                "node_id": self._nodes[i].node_id,
                "text": self._nodes[i].text,
                "metadata": dict(self._nodes[i].metadata),
                "score": float(scores[i]),
            }
            for i in ranked
        ]

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        # tokens 不落盘：可由 text 经 tokenize 确定性重算，存下来纯属冗余
        # （301 节点产物 2.4MB，semantic 的 1059 节点会到约 9MB）
        data = {
            "k1": self._k1,
            "b": self._b,
            "nodes": [
                {"node_id": n.node_id, "text": n.text, "metadata": n.metadata}
                for n in self._nodes
            ],
        }
        (path / INDEX_FILE).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return path

    @classmethod
    def load(cls, path: str | Path) -> "BM25Store":
        p = Path(path) / INDEX_FILE
        if not p.exists():
            raise FileNotFoundError(
                f"BM25 索引不存在: {p}（请先运行 build_index 建索引，再启动检索）"
            )
        data = json.loads(p.read_text(encoding="utf-8"))
        store = cls(k1=data.get("k1", 1.5), b=data.get("b", 0.75))
        store._nodes = [NodeRecord(**n) for n in data["nodes"]]
        store._tokens = [tokenize(n.text) for n in store._nodes]
        return store
