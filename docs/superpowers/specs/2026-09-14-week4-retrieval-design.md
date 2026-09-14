# 第四周 B 检索设计：Hybrid+Reranker 正式对比 + Version-aware 检索

> 成员 B · 检索域。依据指南 §8 本周任务分解（产品实现指南 `product_rag_implementation_guide.md` §8）。
> 状态：设计定稿（2026-09-14），实现立即可启动（无外部依赖阻塞，见 §5）。

---

## 1. 背景与决策记录

### 1.1 本周任务（指南 §8 成员 B）

| # | 任务 | 状态 |
|---|---|---|
| ① | 正式四组对比：Vector / BM25 / Hybrid / Hybrid+Reranker（§8.1/8.2），结论写入 `docs/evaluation.md` | 前三组配置就绪，第四组本周新实现（§2、§4） |
| ② | Version-aware 检索（§8.3）：版本作为过滤条件与排序加权 | 过滤半边第三周已验证；加权半边本周新实现（§3） |

### 1.2 现状核查（2026-09-14）

- **D 的 schema 已预留全套接口**：`mode: hybrid_rerank`、`rerank_model`（必填校验）、`candidate_top_k ≥ top_k` 校验均已落地；`rerank_model` 与 `components` 一样**不入索引身份**（引用制无自有索引，无需重建）。
- **检索侧唯一缺口**：`retrieval/retriever.py` 对 hybrid_rerank 明确拒绝（"待第四周实现"）；无 rerank 模块、无 reranker 模型。
- **依赖可用性已实测**：venv 内 `sentence_transformers 6.0.0` / `transformers 5.16.1` / `torch 2.13.0+cpu`，`CrossEncoder` 可导入；`models/` 下仅有 bge-m3，**需下载 bge-reranker-v2-m3（约 2.3GB，直连 huggingface.co，勿设 HF 镜像）**。
- **多来源三件套就绪**：`struct_multisrc_v1`（vector，1606 节点）/ `struct_multisrc_bm25` / `struct_multisrc_hybrid`（components 引用前两者）——四组对比只缺 rerank 配置。
- **标注仍为循环论证版**：`expected_sources.jsonl` 120 行全部 `user_manual` 且系检索 top-1 回显；多来源配置按"宁缺毋滥"协议挂 `expected_sources: null` → **正式指标待 E 真值标注 + C 判对口径**，本周先出证据链（§4.3）。
- **C 的 source-priority-draft 遗留问题 6.1**：`retrieval.source_priority` 是否进检索排序——本周一并答复（§6）。

### 1.3 关键决策（用户/团队拍板）

| 决策 | 结论 | 理由 |
|---|---|---|
| Reranker 选型 | **bge-reranker-v2-m3** | 与 bge-m3 同家族、多语言；CPU 上 30 候选/题约 1~2s，120 题/组约 5~10 分钟可接受 |
| 对比语料 | **多来源语料**（struct_multisrc_*） | 产品方向与第三周会签方向一致；单 PDF 历史可比性靠引用既有报告，不重跑 |
| Version-aware 范围 | **配置级**（params 袋），不动 API 协议 | 零跨组会签阻塞；每查询参数留作后续（服务端接入时再议） |
| Rerank 集成形态 | **专用类 `HybridRerankRetriever`**（内部组合融合与精排） | 富引用经 `_to_source_ref` 投影后不含 metadata，而版本加权需要 metadata——boost 必须在投影前、精排后完成，故精排类直接持有两个 store 走原始 hit 通路，不跨投影边界做通用装饰器；精排 score 量纲与 RRF/余弦仍在类内分离 |
| 版本加权算法 | **候选池内 min-max 归一 + 加成** | 四模式 score 量纲不同（余弦 0~1、RRF ~0.03、logits 可负），乘法在负分上翻转顺序、加法在 RRF 量纲上淹没原分；归一化对量纲免疫 |
| 指标阻塞处理 | **证据链先行，标注到位后翻配置补指标** | E/C 交付不在 B 控制内；本设计把影响隔离为"改一行配置重跑" |

---

## 2. Hybrid+Reranker 通路（§8.2）

### 2.1 流程

```
question → HybridRetriever（vector+bm25 RRF 粗排，取 candidate_top_k=30）
         → HybridRerankRetriever（交叉编码器精排）→ [版本加权] → top_k=5
```

粗排/精排档位由既有 schema 强制（`candidate_top_k ≥ top_k`、`rerank_model` 必填），零新增字段。

### 2.2 模块与接口

**新增 `retrieval/rerank.py`**——精排模型工厂，模式与 `embeddings.py` 同款：

```python
def build_reranker(cfg) -> Callable[[str, list[str]], list[float]]:
    """懒加载 CrossEncoder：models/ 本地目录优先，否则按别名拉 BAAI/bge-reranker-v2-m3。"""
```

- 模型解析复用 `embeddings.py` 的本地目录/别名机制（`MODEL_DIR` 提为公共；`HF_REPO_ALIASES` 增补 `bge-reranker-v2-m3 → BAAI/bge-reranker-v2-m3`）。
- 返回 `(question, texts) -> scores` 闭包；`batched` 由 CrossEncoder 内部处理。

**新增 `HybridRerankRetriever`（`retriever.py`）**——精排通路专用类（走原始 hit，保证 boost 在投影前可用 metadata）：

```python
class HybridRerankRetriever:
    def __init__(self, vector_store, bm25_store, rerank_fn, rrf_k=60.0,
                 candidate_top_k=30, filters=None,
                 version_pref=None, version_boost=0.0): ...
    async def retrieve(self, question, top_k) -> list[dict]:
        # 1. 两路子检索各取 max(top_k, candidate_top_k) → fuse_hits 融合成粗排池（原始 hit，含 metadata）
        # 2. rerank_fn(question, [text...]) → 交叉编码器分，按分降序（并列 node_id 升序）
        # 3. apply_version_boost(...)  版本加权（可选）
        # 4. 截断 top_k，_to_source_ref 投影
```

**`build_retriever` 增 hybrid_rerank 分支**：把现有 hybrid 装载段（components 角色校验 → 节点集一致性 → 子索引存在性 → 构建两个 store → rrf_k）抽为 `_load_hybrid_stores(cfg)` 复用；hybrid_rerank = 该公共段 + 精排函数（`rerank_fn` 依赖注入，测试可绕过真模型）+ `HybridRerankRetriever`。

### 2.3 引用制 gate（三处，D 的脚本，走会签 §6）

hybrid_rerank 与 hybrid 一样是**引用制、无自有索引**，以下 gate 需一并纳入，否则 `make index` / `run_experiment` 会对它期望一个不存在的索引：

| 位置 | 现状 | 改为 |
|---|---|---|
| `retrieval/index.py::build_index` | 拒绝 hybrid | 拒绝 hybrid 与 hybrid_rerank（改提示语） |
| `scripts/build_index.py::cmd_build` | `mode == "hybrid"` 跳过 | 同上；`cmd_list` 的子索引星标同样扩展 |
| `scripts/run_experiment.py::_ensure_index` | `mode == "hybrid"` 走子索引检查 | 同上 |

### 2.4 配置

新增 `configs/experiments/struct_multisrc_hybrid_rerank.yaml`：身份段照抄 `struct_multisrc_hybrid`，`mode: hybrid_rerank`、`rerank_model: bge-reranker-v2-m3`、`candidate_top_k: 30`、`params: {rrf_k: 60}`、`expected_sources: null`（协议）、`compare_baseline: struct_multisrc_hybrid`。

### 2.5 score 语义

精排后 `SourceRef.score` = 交叉编码器分（sigmoid 后 0~1 或原始 logits，以 CrossEncoder 实际输出为准，冒烟时定死并写进 api.md）。**第三种量纲**，与 cosine/BM25/RRF 均不可比——沿用既有约定：阈值必须按 mode 分别定标（会签 §6）。

### 2.6 测试

| 层 | 用例 |
|---|---|
| 工厂 | `build_reranker`：本地目录优先解析、别名回退、懒加载只初始化一次（monkeypatch 假 CrossEncoder） |
| 精排类 | 假 store + 假 rerank_fn：按精排分排序、截断 top_k、粗排池条数 = max(top_k, candidate_top_k)、score 被替换、空结果透传 |
| 分发 | `build_retriever`：hybrid_rerank 构建成功、缺 components 报错复用 hybrid 校验、节点集不一致报错；`test_retrieval.py` 中"拒绝 hybrid_rerank"断言翻转为"支持" |
| 端到端 | 合成节点：精排把粗排第 2 提到第 1（假 rerank_fn 构造）；真模型仅人工冒烟（§5 步骤 4），不进 CI |

---

## 3. Version-aware 检索（§8.3）

### 3.1 两个半边

| 半边 | 机制 | 状态 |
|---|---|---|
| 版本作为**过滤条件**（硬约束） | `retrieval.filters: {version: "2.4"}` | 第三周已在真实索引上验证（`scripts/verify_filters.py`），本周不重复建设 |
| 版本作为**排序加权**（软偏好） | `retrieval.params.version_pref` + `version_boost` | 本周新实现 |

配置示例（新增两个对照实验，见 §4.2）：

```yaml
retrieval:
  mode: hybrid
  params:
    rrf_k: 60
    version_pref: "2.4"     # 目标版本；空/缺省 = 不加权
    version_boost: 0.1      # 命中加成（归一化分空间）
```

### 3.2 加权算法（新增 `retrieval/boosts.py` 纯函数）

```
apply_version_boost(hits, pref, boost):
  1. 池内 min-max 归一 score → [0,1]（max==min 时全部取 0.5）
  2. metadata.version == pref 的命中 + boost
  3. 按新分降序（并列按 node_id 升序，与 RRF 的确定性排序一致）
  4. 返回新列表；score 字段 = 归一化分 + 加成
```

**设计要点**：

- **顺序**：候选池 →（可选精排）→ 版本加权 → 截断 top_k，四种模式统一。加权必须在截断**前**，否则池外的版本命中没有机会进入 top_k。
- **池大小**：加权生效时取 `max(top_k, candidate_top_k)` 作为候选池（四种模式一致）；未配置 `version_pref` 时**行为与现状逐字节一致**（零回归，不改变任何既有实验的报告）。
- **score 语义变化**：boost 生效时 score 变为"池内归一化排序分"（跨查询不可比）。不生效时不动原分。此变化写进 api.md，C 的弱证据阈值口径对齐（会签 §6）。
- 过滤与加权可叠加：`filters: {version: "2.4"}` 是硬约束（只留 v2.4），`version_pref` 是软偏好（全池参与、命中者上浮）。两者语义不同，文档说明"硬约束用 filters、软偏好用 params"。
- 当前语料版本号与来源一一对应（manual 2.0 / guide 2.4），机制按通用 metadata 字段实现，不特判来源；多版本同源场景出现时零改动可用。

### 3.3 测试

| 层 | 用例 |
|---|---|
| 纯函数 | 命中加成后反超、未命中原序保持、max==min 池、单元素池、空 pref/boost=0 恒等、并列按 node_id 定序、返回新列表不改原列表 |
| 四模式集成 | vector / bm25 / hybrid / reranked 各一测（假 stores）：配置 version_pref 时版本命中上浮、未配置时输出与不加权完全一致 |
| 真实数据 | 版本实验（§4.2）跑通后人工核验 v2.4/v2.0 两个方向的 top-5 漂移方向正确 |

---

## 4. 四组对比实验与交付物（§8.1）

### 4.1 四组配置（多来源语料）

| 组 | 配置 | 状态 |
|---|---|---|
| Vector | `struct_multisrc_v1` | 已有 |
| BM25 | `struct_multisrc_bm25` | 已有 |
| Hybrid | `struct_multisrc_hybrid` | 已有 |
| Hybrid+Reranker | `struct_multisrc_hybrid_rerank` | 本周新增（§2.4） |

四组统一经 `run_experiment` 跑同一题集（`questions.jsonl` 120 题），报告落 `evaluation/reports/`，`compare_baseline` 链：hybrid_rerank → hybrid → v1。

### 4.2 版本实验配置（新增两个）

| 配置 | params | 对照 |
|---|---|---|
| `struct_multisrc_hybrid_ver24` | `version_pref: "2.4", version_boost: 0.1` | vs `struct_multisrc_hybrid`（无加权） |
| `struct_multisrc_hybrid_ver20` | `version_pref: "2.0", version_boost: 0.1` | 同上，反向验证 |

证据口径：同一组版本敏感探针（复用第三周 §7.5 D 场景问题 + 题集中 13 道 `version` 类题），人工核对 top-5 中目标版本占比与排位的漂移方向符合预期。

### 4.3 指标阻塞与降级路径

- **本周**：`expected_sources: null` → 报告只记录检索结果（每題 retrieved×5），**不产出循环论证指标**（宁缺毋滥协议）。
- **判读**：用证据链做定性结论——精确 token 题（api_use 36 + error_code 11）的 rerank 排名增益、双来源共存性、版本漂移方向。
- **E/C 就绪后**：多来源配置翻回 `expected_sources: evaluation/datasets/expected_sources.jsonl`（真值版）重跑，一步补全四组正式指标与 `compare_baseline` 差值。

### 4.4 交付物

- `docs/evaluation.md`（B 的检索部分）：方法学（四组定义、阈值口径、语料与题集）+ 四组证据结论 + 版本加权结果 + 局限（指标待真值标注、A 终版 Node 集未冻结）+ 与单 PDF 历史报告的引用对照。
- 若 rerank 无增益：**如实记录**（§8.2 明示"必须先有 Baseline 才知道它是否真的产生提升"），不粉饰。

---

## 5. 实现顺序与触发条件

| 步骤 | 内容 | 依赖 | 备注 |
|---|---|---|---|
| 0 | 后台下载 bge-reranker-v2-m3 → `models/`（约 2.3GB，直连 HF） | 网络 | 与 1/2 并行，不阻塞编码 |
| 1 | `rerank.py` 工厂 + `HybridRerankRetriever` + `build_retriever` 分支 + 三处 gate（TDD） | 无 | 提交点 1 |
| 2 | `boosts.py` + 四模式接线（TDD） | 无 | 提交点 2（可与 1 同 PR） |
| 3 | 新增 3 份配置（hybrid_rerank + ver24 + ver20）；连同既有 3 份共 6 份逐份自检 | 1、2 | `python scripts/experiment_config.py configs/experiments/<名>.yaml` |
| 4 | 真模型冒烟：单题加载 + 精排核验，定死 score 量纲 | 0、1 | 人工执行，不进 CI |
| 5 | 四组 + 版本实验运行（6 次 run_experiment） | 3、4 | 预计机器时间 1~1.5h（rerank 为主） |
| 6 | `docs/evaluation.md` + PR（含会签事项清单） | 5 | 提交点 3 |

**触发条件**：全部步骤无外部依赖，即刻可启动；唯一外部风险是 A 的终版 Node 集（§7）。

---

## 6. 会签与跨域事项

| 事项 | 归属 | 内容 |
|---|---|---|
| 三处引用制 gate 纳入 hybrid_rerank | **D** | `retrieval/index.py`（B 域直改）、`scripts/build_index.py` / `run_experiment.py`（D 脚本，B 出补丁、D 审，沿用 PR#33 先例） |
| api.md 量纲补条目 | **D** | hybrid_rerank 的 score 量纲（交叉编码器分）+ version_boost 生效时的归一化分说明 |
| 弱证据阈值口径 | **C** | boost 生效配置下 score 不可跨查询比较，C 的阈值（0.5 起）需按 mode/配置分别定标 |
| source-priority-draft 问题 6.1 答复 | **B→C** | 检索侧本周只做 version 加权（软偏好）；`source_priority` 维持生成侧采信用途，不做检索排序——避免"检索时排掉低优先级、生成时又需要它做冲突披露"的矛盾。若后续 C 需要检索侧优先级，可复用 `boosts.py` 同一机制（通用 metadata 加成），届时走会签 |
| configs README 补 params 说明 | **D（B 出稿）** | `params` 行补 `version_pref` / `version_boost` 一句说明（沿用 candidate_top_k 行先例） |
| 真值标注 | **E** | 多来源题集标注（禁循环论证）；B 只消费 |
| 终版 Node 集冻结时机 | **A/D** | 见 §7 首条 |

### 6.1 D 会签结论（2026-09-14，用户拍板；PR#34 审查后回写）

| 事项 | D 结论 |
|---|---|
| 三处引用制 gate | **D 侧两处已完成，无需 B 出补丁**：`scripts/build_index.py` / `run_experiment.py` 已由 D 第四周交付五收敛为单一事实源 `experiment_config.uses_reference_index()`（判定 `mode in ("hybrid","hybrid_rerank") and components`，hybrid_rerank 引用制形态已覆盖；提交在 feature/server-platform 待 push，合入 develop 后 B 复核即可）。`retrieval/index.py` 属 B 域按原计划直改——但见下方「设计一致性」条。**B 实现时请勿再对两个 D 脚本出补丁**，避免与 D 侧提交冲突 |
| 设计一致性（新增，需 B 拍板） | §2.3 计划让 `retrieval/index.py` 一刀切拒绝 `hybrid_rerank`，但 schema 刻意**不强制** hybrid_rerank 填 components（experiment_config.py L132 注释）、configs README components 行也写明"未填则按自有索引 + 精排建索引"——`uses_reference_index()` 对无 components 的 hybrid_rerank 返回 False，D 侧脚本会走自有索引路径，核心层却拒绝，两侧矛盾。二选一：①hybrid_rerank 一律引用制 → schema 收紧 components 必填 + README 行更新，`retrieval/index.py` 可一刀切拒绝；②保留自有索引形态 → `retrieval/index.py` 按 `uses_reference_index()`（或等价判定）分派拒绝，只拦引用制形态。D 无倾向，B 实现时定并回写本表 |
| api.md 量纲补条目 | **已落 v0.12（D 落笔）**：score 字段表补 `hybrid_rerank` 交叉编码器分条目（具体量纲 sigmoid 0~1 或原始 logits **以 B 冒烟实测为准，B 定死后回写字段表**）；version_boost 生效配置 score = 池内归一化排序分 + 加成，跨查询/跨配置不可比；阈值注记补 `hybrid_rerank` 不设绝对阈值（沿用条数/top_k 信号）、boost 生效配置一律不适用绝对阈值 |
| configs README params 行 | **已由 D 直接写**（不走 B 出稿往返）：`version_pref`/`version_boost` 作用与典型值 + 与 `filters` 硬过滤的分工 + F1 提示 |
| 弱证据阈值口径（C） | **D 认可**：按 mode/配置定标与 X1 决议（api.md v0.7）同向，boost 生效配置下 score 不可跨查询比较，绝对阈值一律不适用（已写入 api.md v0.12）。例会通报 C |
| source-priority 6.1 答复（B→C） | **D 认可**：检索侧只做 version 加权、`source_priority` 维持生成侧采信的理由成立（避免检索/生成对优先级的矛盾诉求）；`boosts.py` 通用 metadata 加成是干净的扩展路径。例会通报 C |
| 终版 Node 集冻结（A/D） | 流程认可（先跑对比，A 冻结后走 R2 指纹复核）。**成本数字修正**：§7 的"向量重建 ~87 分钟"与 D 实测不符——本机（Ryzen 7 9700X）multisrc 1606 节点单次重建 **24.8min**；即便四套向量索引（301+622+906+1606 节点）全部重建合计约 **64min**。通报 A 时以实测为准 |

---

## 7. 风险与开放问题

- **A 的终版 Node 集变更 → 全部索引作废**（向量重建 CPU ~87 分钟）：本周对比先跑；A 冻结后需复核索引指纹，若产物已变则重建后重跑四组（约 1.5h 机器时间）。例会同步该依赖。
- **transformers 5.16 较新**，bge-reranker-v2-m3 加载可能有兼容问题：冒烟不过则退用 `CrossEncoder` 直载 + `trust_remote_code`，仍不过则降级 bge-reranker-base 并记录（模型选型变更是实验记录的一部分）。
- **CPU 精排耗时**：30 候选 × 120 题 ≈ 5~10 分钟/组；若明显超预期，`candidate_top_k` 保持 30 不动（对比较口径的影响最小），改为减少重复运行次数。
- **归一化分的解读风险**：boost 生效时 score 不再是原始分——报告与前端展示需带 mode/配置上下文，防止跨配置比较（会签 §6 已列）。
- **rerank 可能无增益**：如实记录；若精确 token 题也无增益，说明 RRF 已把 API 名类词项命中拉满，结论同样是有效实验产出。
- **双版本同源场景当前不存在**（版本号与来源一一对应）：机制按通用字段实现，真实多版本语料出现时零改动可用；本条在 `docs/evaluation.md` 局限中说明。
