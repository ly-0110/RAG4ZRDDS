# 第三周 B 检索设计：Metadata Filtering 验证 + Hybrid RRF 初版 + 跨来源验证

> 成员 B · 检索域。依据指南 §7 本周任务分解（产品实现指南 `product_rag_implementation_guide.md` §7）。
> 状态：设计定稿（2026-09-11），实现待 A 的 `html_v1.jsonl` 就绪后启动（团队决策，见 §1.3）。

---

## 1. 背景与决策记录

### 1.1 本周任务（指南 §7 成员 B）

| # | 任务 | 状态 |
|---|---|---|
| ① | Metadata Filtering：按 source_type/version 过滤，进 retrieval 统一接口 | 接口第二周已接线，本周做真实验证 + 版本口径对齐（§3） |
| ② | Hybrid 初版：向量 + BM25 以 RRF 融合，为第四周正式对比热身 | 新实现，本设计核心（§2） |
| ③ | 用 7.5 的 A/B/C/D 四类场景样例验证跨来源检索行为 | 验证方案定稿（§4），执行等 A + E 产物 |

### 1.2 现状核查（2026-09-10）

- **A 的 `data/processed/html_v1.jsonl` 未就绪**；processed 下仅第二周 4 个产物。
- **E 的跨来源题集未就绪**（`week3-delivery-review.md` P0：标注循环论证，整改中）。
- **接口层已就绪**：`filters` 等值过滤在 vector（chroma `where`）与 bm25（post-filter）两侧均已接线，`build_retriever` 已把 `cfg.retrieval.filters` 传入两个 retriever。
- **D 的 `experiment_config.py` 已预留**：`RetrievalCfg.candidate_top_k`（默认 30，注释即 §8.2 Top30→Top5）、`sources` 多来源注册集（`SourceCfg.type: pdf|html`、html 强制 url）、`source_priority`（C 域）、多来源 `nodes_path` 命名（`{method}_{version}__{sources_digest8}.jsonl`）。
- **第二周 4 索引**：`struct_v1`（vector）与 `struct_bm25`（bm25）是**同一节点集**的两个索引——Hybrid RRF 的现成输入。

### 1.3 关键决策（团队/用户拍板）

| 决策 | 结论 | 理由 |
|---|---|---|
| 落地节奏 | **设计先行，等 A 就绪后一次性实现+验证** | A 产物未就绪；避免 A 延迟导致返工 |
| Hybrid 索引来源 | **引用既有索引，零重建** | 复用 struct_v1 + struct_bm25；自建双索引需重复编码 12 分钟/实验，且与「索引目录=配置身份」约定有张力 |
| Metadata Filtering 增量 | **沿用等值过滤，只做验证** | 指南只要求 source_type/version 等值；比较运算符留给第四周 Version-aware（§8.3） |

---

## 2. Hybrid RRF 初版

### 2.1 设计原则

RRF（Reciprocal Rank Fusion）是**运行时融合**：两个子检索器各自出排名，按 `score = Σ 1/(k + rank)` 融合后取 top_k。不需要新索引——`struct_v1`（vector 索引）+ `struct_bm25`（bm25 索引）加载进同一 retriever 即可。

约束：`components` 引用的两个子配置必须产出**同一节点集**（chunking + sources 相同），否则 node_id 无法对齐融合。

### 2.2 配置形态

新增 `configs/experiments/struct_hybrid.yaml`（身份段照抄 struct_v1，节点集相同）：

```yaml
experiment:
  name: struct_hybrid
  stage: ablation
  description: Hybrid RRF 初版——vector(struct_v1) + bm25(struct_bm25) 引用融合，零重建
sources: # 与 struct_v1 完全一致
  - {id: manual_2_0, type: pdf, path: ..., version: "2.0"}
chunking: {method: struct, version: v1}   # 与 struct_v1 一致
embedding: {model: bge-m3, ...}           # 与 struct_v1 一致
retrieval:
  mode: hybrid
  top_k: 5
  candidate_top_k: 30                     # 子检索各取条数（复用既有字段，§8.2 Top30→Top5）
  filters: {}
  params: {rrf_k: 60}                     # RRF 常数放 params 袋（Owner 自由区，零 schema 改动）
  components:                             # ← 唯一新增字段（需 D 会签，见 §6）
    vector: struct_v1                     # 实验名 → configs/experiments/{name}.yaml
    bm25: struct_bm25
```

**设计要点**：

- `rrf_k` 放 `retrieval.params` 袋——bm25 的 k1/b 已有先例，params 是 Owner 自由区不校验，**避免 schema 改动**。
- 子检索候选数复用既有 `candidate_top_k`（默认 30），不新增字段。
- `components` 引用**实验名**（而非索引目录名）——目录名含 hash8 不便手写；实验名映射到 `configs/experiments/{name}.yaml` 后经 `experiment_config` 派生子索引目录，与 D 的「命名单一事实源」约定一致。
- `build_index` 对 `mode=hybrid` **跳过构建**并打印提示（子索引由各自配置构建，`make index CFG=...` 分别跑 struct_v1/struct_bm25）；不写 manifest（无索引产物）。
- `components` **不入** `index_identity_json`（身份段仍只含 mode/params/filters）：hybrid 不产出索引，`config_hash8` 对 hybrid 只影响其（无产物的）index_dirname，不影响子索引定位。

### 2.3 RRF 融合算法

```
输入: question, top_k, filters（同时下推两个子检索器）
1. vector 子检索: VectorStore.query(question, candidate_top_k, filters)
2. bm25 子检索:   BM25Store.query(question, candidate_top_k, filters)
3. 按 node_id 融合: score = Σ_{每路命中} 1/(rrf_k + rank)   # rank 从 1 起
4. 降序取 top_k
5. text/metadata 取 vector 路（两路节点集相同，字段一致；vector 路分数可解释性更好）
```

- **同 node_id 两路命中 → 分数叠加**（天然奖励共识，RRF 的核心机制）。
- 单路命中分数落在 `1/(k+1) ~ 1/(k+30)`；双路叠加最大 `2/(k+1)`。
- filters 语义：等值过滤（与子检索器现有语义一致），过滤发生在各自排名**之前**（chroma where 前置、bm25 post-filter 前置），融合只看见过滤后的候选。

### 2.4 score 语义与日志

- 融合 score 为 **RRF 分**（量纲 0~2/61，k=60），直接落 `SourceRef.score` 与检索日志 `results[].score`。
- 与 cosine（0~1）、BM25（7.7~56.4）**不可比**——沿用 bm25.py docstring 的既有约定：跨模式 score 比较无意义，任何 score 阈值必须按 mode 分别定标。日志 schema（`docs/retrieval-log-schema.md`）**无需改字段**。

### 2.5 测试

| 层 | 测试 | 手段 |
|---|---|---|
| 纯函数 | RRF 融合：rank→分、两路共识叠加、去重、单路命中、并列排名 | 单测（TDD 先行） |
| 分发 | `build_retriever`：components 派生子索引目录、节点集一致性校验（两配置 `nodes_path` 不同 → 报错）、filters 双路下推 | 假索引目录单测 |
| 端到端 | 合成数据：两路命中共识 > 单路命中的排序；filters 在 hybrid 下等价于两侧同时过滤 | 合成节点 + FakeEmbedder |
| 真实数据 | `struct_hybrid` 跑 120 题评测，指标与 struct_v1/struct_bm25 对比 | 等 A 就绪后统一执行（§5） |

**预期指标**（设计假设，实测校准）：RRF 融合通常 ≥ 单路较优者，至少应显著高于较差者；若 hybrid 低于两路最大值，说明节点集/参数有问题而非算法本身。

---

## 3. Metadata Filtering 验证

### 3.1 现状（第二周已交付）

- `VectorStore.query(filters)` → chroma `where` 等值过滤（`_to_chroma_where`）
- `BM25Store.query(filters)` → Python 侧 metadata 等值 post-filter
- `cfg.retrieval.filters` 已接进 `build_retriever`
- 单测覆盖：`test_retrieval.py` 过滤相关用例

### 3.2 第三周增量

1. **版本元数据口径对齐（与 A 会签）**：PDF 手册 `version="2.0"`；HTML Doxygen 文档为 v2.4.0 → 约定 HTML 节点 `version="2.4"`（字符串等值匹配；等值过滤不支持前缀/范围，`"2.4.0"` 与 `"2.4"` 不互通，**必须在 A 落盘前定死格式**，见 §6 会签事项）。
2. **多来源混合索引上的过滤验证**：混合索引建成后，验证 `{source_type: pdf}`、`{source_type: html}`、`{version: "2.4"}`、组合过滤（`{source_type: html, version: "2.4"}`）的行为：
   - 过滤结果全部满足约束（结果集无违规元数据）；
   - 过滤后空结果 → 确定性空列表（与现有契约一致，下游拒答路径可用）；
   - filters 在 vector/bm25/hybrid 三模式语义一致。
3. **7.5 A/D 场景的过滤应用**：A 场景（单一来源）验证 source_type 过滤切到目标来源；D 场景（版本冲突）验证 version 过滤区分版本（见 §4）。

### 3.3 测试

- 合成多来源节点集（pdf + html 混合）的过滤单测：三模式行为对齐；
- 真实数据冒烟：过滤结果元数据全量校验脚本（不依赖题集，A 产物就绪即可跑）。

---

## 4. 跨来源验证方案（7.5 A/B/C/D）

### 4.1 依赖链

```
A: html_v1.jsonl（7.2 schema 元数据齐全）
  → D: ingest 多来源注册式接入 → 多来源节点集/索引（vector + bm25）
  → B: 验证矩阵执行
E: 跨来源题集（P0 整改后，真值不循环论证）+ C: 判对口径会签
```

### 4.2 验证矩阵

四场景（指南 §7.5）× 三模式（vector / bm25 / hybrid）× 过滤（无 / source_type / version）：

| 场景 | 样例问题 | 理想结果 | 验证点 |
|---|---|---|---|
| A 单一来源 | 产品如何安装？ | User Manual | 无过滤时 top-k 以 manual 为主；`source_type=pdf` 过滤后仍可答 |
| B HTML 更适合 | `create_datawriter()` 的参数？ | Developer/API Guide | 无过滤时 top-k 以 html 为主；`source_type=html` 过滤后仍可答 |
| C 多来源联合 | 用户手册的设备连接在 Java SDK 如何实现？ | Manual + Developer Guide | top-k 双来源共存；hybrid 融合不丢失任一路证据 |
| D 冲突/版本 | v2.4 的 API 是否仍用旧参数？ | 区分版本和来源 | `version` 过滤后结果版本一致；无过滤时双版本均可出现在 top-k（供 C 的冲突披露话术取用） |

**判据**：hit_rate@5 / mrr@5 沿用第二周口径；跨来源题的「理想来源」标注与 C 的 source-priority-draft 会签后定稿（判对标准归 C，B 只消费）。

### 4.3 降级路径

- **E 题集未就绪**：先用 §7.5 的 4 个样例 + C 的 source-priority-draft 场景做行为冒烟（理想结果对照表即真值），结果只作开发参考、不进正式报告；
- **正式评测**：等 E 重新标注（禁循环论证）+ C 会签口径后，接 `questions.jsonl` 扩展的跨来源题跑全套指标。

### 4.4 新实验配置（等 A 就绪后创建）

沿用第二周命名习惯，多来源三件套：

- `multi_v1`（多来源节点集，mode=vector）、`multi_bm25`（mode=bm25）、`multi_hybrid`（mode=hybrid，components 引用前两者）
- 三配置的 `sources` 均为多来源注册集（pdf + html），chunking 沿用 struct（第二周最优）；具体 path 等 A 产物落盘后填。

---

## 5. 实现顺序与触发条件

**触发判据（A 就绪）**：`data/processed/html_v1.jsonl` 存在，且每行含 §7.2 schema 元数据（`source_type` / `source_url` / `version` 非空、格式符合 §3.2 会签口径）。

| 步骤 | 内容 | 依赖 | 备注 |
|---|---|---|---|
| 0 | Hybrid RRF 实现（§2 全部） | **无外部依赖** | 团队决策为「全部等 A」，但此步零依赖，A 长期延迟时可在例会提出单独先行 |
| 1 | Metadata Filtering 真实验证（§3.2-2/3） | 多来源索引建成（A + D） | 不含题集，仅元数据校验脚本 |
| 2 | 跨来源冒烟（§4.3 降级路径） | 同步骤 1 | 4 样例行为对照，不进正式报告 |
| 3 | 跨来源正式评测 | E 题集 + C 口径 | 三模式 × 过滤矩阵，落 `evaluation/reports/` |

---

## 6. 会签与跨域事项

| 事项 | 归属 | 内容 |
|---|---|---|
| `retrieval.components` 字段 | **D** | `RetrievalCfg` 是 `extra=forbid` 严格模型，新增字段必须由 D 改 `scripts/experiment_config.py`（`components: dict[str, str] \| None = None`，校验 mode=hybrid 时必填、引用的实验名对应 yaml 存在）并更新 `configs/experiments/README.md` |
| `build_index` hybrid 跳过行为 | D | `retrieval/index.py::build_index` 的 hybrid 分支：打印提示、返回子索引列表或跳过；与 D 的 `--list`/manifest 逻辑对齐 |
| HTML 节点 version 格式 | **A** | `version="2.4"`（非 `"2.4.0"`）字符串等值口径，落盘前定死；source_type 取值 pdf/html |
| 跨来源题集与真值 | **E** | P0 整改（禁循环论证）后交付；B 只消费 |
| D 场景判对口径 | **C** | 版本冲突题的「正确」定义（source-priority-draft 会签） |
| `run_experiment` 对 hybrid 兼容 | D | 评测 runner 经 `build_retriever` 走 components 派生，无需新索引目录；若 runner 有「索引必须存在」前置检查需豁免 hybrid |

---

## 7. 风险与开放问题

- **semantic 分块质量问题**（第二周语义垫底 0.06）属 A 域，第三周多来源沿用 struct chunking，不消费 semantic 节点集——若 A 修复后需重评，另行实验。
- **RRF k 值未调参**：k=60 为经典默认，第四周正式对比（§8.1）时可扫参（如 k∈{20,60,100}），第三周不做。
- **components 引用的配置必须存在于仓库**：`configs/experiments/{name}.yaml` 是引用约定的一部分，换机器/删配置会破坏 hybrid 加载——报错信息需明确指出缺失的配置文件。
- **score 量纲混淆风险**：hybrid 报告中的 score 是 RRF 分，若评测/前端有基于 score 的阈值逻辑（如「弱证据」判定），必须按 mode 分别定标（第二周 bm25 已有同款约定）。
