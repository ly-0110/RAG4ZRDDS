"""实验配置加载与校验 —— configs/experiments/*.yaml 的唯一合法入口。

职责（成员 D · 集成与实验平台）：
  * 结构层严格校验：未知 key 报错并给拼写建议；各 params 袋为 Owner 自由区不校验
  * 跨区规则：api 密钥引用、rerank 参数、source id 唯一、name=文件名
  * 派生命名（单一事实源 = 配置文件名）：
      Node 集   data/processed/{method}_{version}.jsonl
      索引目录  indexes/{method}_{embed_model}_{hash8}    hash8=sha256(规范化配置)[:8]
      报告      {report.dir}/{experiment.name}.json

用法：
  from experiment_config import load, index_dirname, nodes_path   # 供 ingest/build_index/run_experiment 共用
  python scripts/experiment_config.py configs/experiments/example_v1.yaml   # 冒烟自检

格式规范：configs/experiments/README.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from difflib import get_close_matches
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

REPO_ROOT = Path(__file__).resolve().parent.parent

METRIC_RE = re.compile(r"^(hit_rate|mrr|precision|recall)@\d+$")

# 回答质量指标（成员 C 口径，第二周起）：与检索指标不同，无 @K 后缀。
# judges 落地见 evaluation/judges/（faithfulness / answer_relevance）。
RESPONSE_METRICS = {"faithfulness", "answer_relevance", "correctness", "citation_accuracy"}


class _Strict(BaseModel):
    """结构层一律禁止未知 key；params 袋所在模型对袋子本身用普通 dict 放行。"""

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- 区块模型


class ExperimentCfg(_Strict):
    name: str
    description: str = ""
    stage: Literal["baseline", "ablation", "regression", "product"] = "baseline"


class SourceCfg(_Strict):
    id: str
    type: Literal["pdf", "html"]
    path: str
    version: str | None = None
    url: str | None = None
    params: dict[str, Any] = {}

    @model_validator(mode="after")
    def _url_rule(self) -> "SourceCfg":
        if self.type == "html" and not self.url:
            raise ValueError("type=html 的来源必须提供 url（HTML 引用需可跳转，指南 §7.2）")
        return self


class IngestCfg(_Strict):
    cleaned_output: str = "data/cleaned/pages.jsonl"
    quality_check: bool = True


class ChunkingCfg(_Strict):
    method: Literal["struct", "semantic", "hybrid", "fixed"]
    version: str = "v1"
    params: dict[str, Any] = {}


class EmbeddingCfg(_Strict):
    provider: Literal["local", "api"] = "local"
    model: str
    batch_size: int = Field(default=32, ge=1)
    device: str = "cpu"
    api_key_env: str | None = None

    @model_validator(mode="after")
    def _key_rule(self) -> "EmbeddingCfg":
        if self.provider == "api" and not self.api_key_env:
            raise ValueError("embedding.provider=api 时必须填写 api_key_env（引用 .env 变量名，禁止明文密钥）")
        return self


class IndexCfg(_Strict):
    backend: Literal["chroma", "faiss"] = "chroma"
    metric: Literal["cosine", "ip", "l2"] = "cosine"


class RetrievalCfg(_Strict):
    mode: Literal["vector", "bm25", "hybrid", "hybrid_rerank"] = "vector"
    top_k: int = Field(default=5, ge=1)
    candidate_top_k: int = Field(default=30, ge=1)
    rerank_model: str | None = None
    filters: dict[str, Any] = {}
    source_priority: list[str] = []
    params: dict[str, Any] = {}

    @model_validator(mode="after")
    def _rerank_rules(self) -> "RetrievalCfg":
        if self.mode == "hybrid_rerank":
            if self.candidate_top_k < self.top_k:
                raise ValueError(
                    f"hybrid_rerank 要求 candidate_top_k({self.candidate_top_k}) ≥ top_k({self.top_k})"
                    "（§8.2 先粗排后精排）"
                )
            if not self.rerank_model:
                raise ValueError("mode=hybrid_rerank 必须指定 rerank_model（如 bge-reranker-v2-m3）")
        return self


class GenerationCfg(_Strict):
    enabled: bool = False
    prompt_version: str = "v0"
    llm_env_prefix: str = "LLM_"


class EvaluationCfg(_Strict):
    dataset: str = "evaluation/datasets/questions.jsonl"
    expected_sources: str | None = "evaluation/datasets/expected_sources.jsonl"
    retrieval_metrics: list[str] = ["hit_rate@5", "mrr@5"]
    response_metrics: list[str] = []
    sample_size: int | None = Field(default=None, ge=1)

    @field_validator("retrieval_metrics")
    @classmethod
    def _retrieval_metric_format(cls, v: list[str]) -> list[str]:
        bad = [m for m in v if not METRIC_RE.match(m)]
        if bad:
            allowed = "hit_rate / mrr / precision / recall，格式 名称@K"
            raise ValueError(f"检索指标名不合法: {bad}；允许 {allowed}")
        return v

    @field_validator("response_metrics")
    @classmethod
    def _response_metric_names(cls, v: list[str]) -> list[str]:
        bad = [m for m in v if m not in RESPONSE_METRICS]
        if bad:
            raise ValueError(
                f"回答质量指标不合法: {bad}；允许 {sorted(RESPONSE_METRICS)}"
            )
        return v


class ReportCfg(_Strict):
    dir: str = "evaluation/reports"
    compare_baseline: str | None = None


class ExperimentConfig(_Strict):
    schema_version: int = 1
    experiment: ExperimentCfg
    sources: list[SourceCfg]
    ingest: IngestCfg = IngestCfg()
    chunking: ChunkingCfg
    embedding: EmbeddingCfg
    index: IndexCfg = IndexCfg()
    retrieval: RetrievalCfg = RetrievalCfg()
    generation: GenerationCfg = GenerationCfg()
    evaluation: EvaluationCfg = EvaluationCfg()
    report: ReportCfg = ReportCfg()

    @model_validator(mode="after")
    def _unique_source_ids(self) -> "ExperimentConfig":
        ids = [s.id for s in self.sources]
        dup = sorted({i for i in ids if ids.count(i) > 1})
        if dup:
            raise ValueError(f"sources.id 重复: {dup}")
        return self


# ---------------------------------------------------------------- 友好报错

_SECTION_MODELS: dict[str, type[BaseModel]] = {
    "experiment": ExperimentCfg,
    "sources": SourceCfg,
    "ingest": IngestCfg,
    "chunking": ChunkingCfg,
    "embedding": EmbeddingCfg,
    "index": IndexCfg,
    "retrieval": RetrievalCfg,
    "generation": GenerationCfg,
    "evaluation": EvaluationCfg,
    "report": ReportCfg,
}


def _candidates_for(loc: tuple[Any, ...]) -> set[str]:
    """根据报错路径定位所在层级的模型，返回该层级允许的 key 集合。"""
    fields: dict[str, Any] = ExperimentConfig.model_fields
    for part in loc[:-1]:
        if isinstance(part, int):  # 列表下标：仍处于同一 item 的字段层
            continue
        field = fields.get(str(part))
        if field is None:
            return set()
        ann = field.annotation
        if hasattr(ann, "__origin__") and ann.__origin__ is list:  # list[Model]
            ann = ann.__args__[0]
        fields = getattr(ann, "model_fields", {})
    return set(fields)


def _friendly_errors(exc: ValidationError, path: Path) -> list[str]:
    msgs: list[str] = []
    for err in exc.errors():
        loc = tuple(err.get("loc", ()))
        pretty = " -> ".join(str(x) for x in loc) or "(root)"
        if err["type"] == "extra_forbidden":
            key = str(loc[-1])
            candidates = _candidates_for(loc)
            near = get_close_matches(key, candidates, n=1, cutoff=0.6)
            hint = f"，你是否想写 '{near[0]}'？" if near else f"；允许的 key: {sorted(candidates)}"
            msgs.append(f"{path.name} [{pretty}] 不认识的配置项 '{key}'{hint}")
        else:
            msgs.append(f"{path.name} [{pretty}] {err['msg']}")
    return msgs


# ---------------------------------------------------------------- 加载与派生


class ConfigError(Exception):
    pass


def load(path: str | Path) -> ExperimentConfig:
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"配置文件不存在: {p}")
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ConfigError(f"{p}: YAML 语法错误\n{e}") from e
    if not isinstance(raw, dict):
        raise ConfigError(f"{p}: 顶层必须是键值映射")
    try:
        cfg = ExperimentConfig.model_validate(raw)
    except ValidationError as e:
        raise ConfigError("\n".join(_friendly_errors(e, p))) from e
    stem = p.stem
    if cfg.experiment.name != stem:
        raise ConfigError(
            f"{p.name}: experiment.name='{cfg.experiment.name}' 与文件名 '{stem}' 不一致"
            "（命名单一事实源是文件名，见 configs/experiments/README.md 铁律 2）"
        )
    return cfg


def canonical_json(cfg: ExperimentConfig) -> str:
    """整份配置的规范化序列化：键排序、紧凑分隔符。任何语义改动都会改变结果。"""
    return json.dumps(cfg.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


# 索引身份只由「决定索引产物内容」的段派生：
#   chunking   → Node 集（data/processed/{method}_{version}.jsonl）
#   embedding  → 向量本身（model/provider/device/batch_size）
#   index      → 后端与度量
#   retrieval.mode/params/filters → mode 决定产物类型（chroma 集合 vs bm25.json），
#                bm25 的 k1/b 会被 save 落进产物，filters 影响入库范围
# generation / evaluation / report / experiment 与索引产物无关：改它们不该触发
# 十分钟级别的重建（2026-09-07 实测：C 把三个 yaml 的 generation 段置 v1 后，
# 三个真实 bge-m3 索引全部孤儿化、live 服务启动失败）。
_INDEX_IDENTITY_SECTIONS = ("chunking", "embedding", "index")
_INDEX_IDENTITY_RETRIEVAL_KEYS = ("mode", "params", "filters")


def index_identity_json(cfg: ExperimentConfig) -> str:
    """索引产物身份的规范化序列化——config_hash8 的唯一输入。"""
    data = cfg.model_dump(mode="json")
    identity = {k: data[k] for k in _INDEX_IDENTITY_SECTIONS if k in data}
    retrieval = data.get("retrieval") or {}
    identity["retrieval"] = {k: retrieval.get(k) for k in _INDEX_IDENTITY_RETRIEVAL_KEYS}
    # 多来源注册集参与索引身份（指南 §7：来源集变了索引内容必变）；
    # 单来源不进身份——保持既有 hash8 不变，避免真实索引孤儿化（R5 教训）。
    if len(cfg.sources) > 1:
        identity["sources"] = sorted(
            ({"id": s.id, "type": s.type, "path": s.path, "version": s.version}
             for s in cfg.sources),
            key=lambda s: s["id"],
        )
    return json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def config_hash8(cfg: ExperimentConfig) -> str:
    """索引目录名后缀：sha256(index_identity_json) 前 8 位。

    语义＝「索引产物身份」，不是「整份配置身份」。同 chunking/embedding/index/
    retrieval(mode,params,filters) 的实验共用同一索引目录，改生成或评测段不触发重建。
    """
    return hashlib.sha256(index_identity_json(cfg).encode("utf-8")).hexdigest()[:8]


def sources_digest8(cfg: ExperimentConfig) -> str:
    """多来源注册集的身份摘要（sha256 前 8 位）：排序后的 (id,type,path,version)。

    仅在 sources 数量 >1 时参与派生命名（见 nodes_path / index_identity_json），
    单来源配置的派生命名保持与 Week2 冻结版逐字节一致。
    """
    items = sorted([s.id, s.type, s.path, s.version or ""] for s in cfg.sources)
    payload = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8]


def nodes_path(cfg: ExperimentConfig) -> Path:
    name = f"{cfg.chunking.method}_{cfg.chunking.version}"
    if len(cfg.sources) > 1:
        # 多来源合并节点集与单来源产物同 method/version 时不得共用文件，
        # 否则注册一个来源就会覆盖另一个配置的 Node 集。
        name += f"__{sources_digest8(cfg)}"
    return REPO_ROOT / "data" / "processed" / f"{name}.jsonl"


def index_dirname(cfg: ExperimentConfig) -> str:
    return f"{cfg.chunking.method}_{cfg.embedding.model}_{config_hash8(cfg)}"


def index_dir(cfg: ExperimentConfig) -> Path:
    return REPO_ROOT / "indexes" / index_dirname(cfg)


def report_path(cfg: ExperimentConfig) -> Path:
    return REPO_ROOT / cfg.report.dir / f"{cfg.experiment.name}.json"


# ---------------------------------------------------------------- CLI 冒烟


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):  # Windows 控制台默认 GBK，统一按 UTF-8 输出
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="实验配置校验与派生命名自检")
    parser.add_argument("config", help="configs/experiments/*.yaml 路径")
    args = parser.parse_args(argv)

    try:
        cfg = load(args.config)
    except ConfigError as e:
        print(f"[配置无效]\n{e}", file=sys.stderr)
        return 1

    print("[配置有效]")
    print(f"  实验 ID     : {cfg.experiment.name} ({cfg.experiment.stage})")
    print(f"  知识源      : {', '.join(s.id for s in cfg.sources)}")
    print(f"  分块方案    : {cfg.chunking.method}/{cfg.chunking.version}  params={cfg.chunking.params or '{}'}")
    print(f"  Embedding   : {cfg.embedding.model} ({cfg.embedding.provider})")
    print(f"  检索        : mode={cfg.retrieval.mode} top_k={cfg.retrieval.top_k}")
    print(f"  hash8       : {config_hash8(cfg)}")
    print(f"  Node 集     : {nodes_path(cfg)}{'  [存在]' if nodes_path(cfg).exists() else '  [尚无——待 ingest]'}")
    print(f"  索引目录    : {index_dir(cfg)}")
    print(f"  报告        : {report_path(cfg)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
