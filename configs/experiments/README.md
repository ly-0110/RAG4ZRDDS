# configs/experiments/ —— 实验配置格式规范（schema v1）

> 格式 Owner：成员 D。A/B 在此目录下**新增/修改 yaml 填实验参数**，但结构层 key 的增删只能由 D 进行。
> 原则出处：实施指南 §4（“D 定格式，A/B 填参数”）、§6.2（公平性约束与回归矩阵）、§10（回归落盘）。

## 一、五条铁律

1. **一次实验一个 yaml**：文件名即实验 ID（`struct_v1.yaml` → `struct_v1`），全库唯一。
2. **命名单一事实源是文件名**：`experiment.name` 必须等于文件名；Node 集、索引目录、报告文件名全部由代码派生，禁止在任何地方手写重复 ID。
3. **两层 key**：
   - **结构层**：本文档列出的所有固定字段。加载时严格校验，未知 key 直接报错（附拼写建议）——防止实验变量静默失效。
   - **参数袋**（带 ◆ 标注的 `params:`）：对应 Owner 的自由区，schema 不校验内容、原样透传给该域模块。A 加第 4 个调优参数、B 加 BM25 k1/b 都无需改格式。
4. **密钥零明文**：yaml 入 Git，只允许引用 `.env` 变量**名**（如 `api_key_env: EMBED_API_KEY`）。
5. **不做继承/插值**：新实验 = 复制现有 yaml 改差异项。四周项目，显式优于巧妙。

## 二、派生命名规则（由 `scripts/experiment_config.py` 实现）

| 产物 | 规则 | 示例 |
|---|---|---|
| Node 集 | `data/processed/{chunking.method}_{chunking.version}.jsonl` | `struct_v1.jsonl` |
| 索引目录 | `indexes/{method}_{embedding.model}_{hash8}` | `struct_bge-m3_3fa1c9d2` |
| 报告 | `{report.dir}/{experiment.name}.json` | `evaluation/reports/struct_v1.json` |

`hash8 = sha256(规范化后的完整配置) 前 8 位`：配置不变 → 目录名不变（稳定可回切）；任何影响语义的改动 → 新目录，旧索引天然保留。`build_index` 会把 Node 文件 sha256 写入 manifest 做完整性核对。

## 三、区块速查

| 区块 | Owner | 关键约束 |
|---|---|---|
| `experiment` | D | name=文件名；stage ∈ baseline/ablation/regression/product |
| `sources` | D | id 唯一；type ∈ pdf/html；html 必填 url，pdf 可空 url；version 进 metadata 供 §8.3 版本过滤 |
| `ingest` | D | cleaned_output 默认 `data/cleaned/pages.jsonl`；quality_check 接 A 的 §16 清单检查 |
| `chunking` | A 填参 | method ∈ struct/semantic/hybrid/fixed；params 袋见 §6.2 回归矩阵（oversize_threshold / sub_split / atomic_blocks…） |
| `embedding` | B | provider ∈ local/api；api 时必须给 api_key_env |
| `index` | D | backend ∈ chroma/faiss；子目录不手填 |
| `retrieval` | B | mode ∈ vector/bm25/hybrid/hybrid_rerank；对比实验间 top_k 必须一致；hybrid_rerank 要求 candidate_top_k ≥ top_k 且必填 rerank_model |
| `generation` | C | enabled=false 时评测只跑检索侧；prompt_version 对应 generation/prompts/ 下版本 |
| `evaluation` | E 数据/C 口径/D 执行 | 指标格式 `名称@K`（hit_rate/mrr/precision/recall）；sample_size 用于联调冒烟 |
| `report` | D | compare_baseline 指向回归基准报告（§10） |

## 四、校验行为

加载入口统一为 `scripts/experiment_config.py::load()`：

- 未知结构层 key / 非法枚举值 → 报错并列出允许值或拼写建议；
- 文件名 ≠ experiment.name → 报错；
- 跨区规则（api 密钥、rerank 参数、source id 唯一）在加载时即失败，不留到运行中途。

冒烟自检：`python scripts/experiment_config.py configs/experiments/<name>.yaml`

## 五、演进规则

- 新增结构层 key / 新区块 / 收紧枚举 → **仅 D 可改**，同时递增 `schema_version` 并更新本 README 与既有 yaml；
- Owner 在自己 params 袋内加参数 → 随时可以，无需改 schema；
- 已产出的索引/报告不受 schema 演进影响的依据是 manifest 里记录的完整配置快照。

## 六、典型变体（第二周示例）

```bash
cp struct_v1.yaml semantic_v1.yaml   # method: semantic，params 换成 B 的 SemanticSplitter 参数
cp struct_v1.yaml hybrid_t2500.yaml  # method: hybrid，params.sub_split: semantic
```
