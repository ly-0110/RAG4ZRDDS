# 检索评测记录

> 维护：成员 B（检索域）。指标口径按指南 §9.1；判对标准归 C，真值标注归 E。
> 更新：2026-09-14（第四周：四组对比 + Version-aware）。

## 1. 方法学

- **语料**：多来源注册集——`user_manual`（PDF，v2.0，301 节点）+ `zrdds_dev_guide`（HTML/Doxygen，v2.4，1305 节点），合并节点集 `data/processed/struct_v1__b95d1061.jsonl`（1606 节点），struct/v1 结构分块。
- **四组定义**（同一节点集、同一题集，仅检索方式不同）：

| 组 | 配置 | 机制 |
|---|---|---|
| Vector | `struct_multisrc_v1` | chroma cosine 向量检索 |
| BM25 | `struct_multisrc_bm25` | 字符 bigram 词袋（k1=1.5, b=0.75） |
| Hybrid | `struct_multisrc_hybrid` | Vector + BM25 各取 30 → RRF 融合（k=60）→ Top-5 |
| Hybrid+Reranker | `struct_multisrc_hybrid_rerank` | 同上粗排 30 → bge-reranker-v2-m3 交叉编码器精排 → Top-5（`max_length=512`） |

- **题集**：`evaluation/datasets/questions.jsonl` 120 题（api_use 36 / config 30 / version 13 / operation 12 / error_code 11 / faq 11 / debug 7）。
- **执行**：`scripts/run_experiment.py`（D 的评测平台），报告落 `evaluation/reports/*.json`（schema v1.1，含三份输入产物指纹）。
- **指标状态**：真值标注未定版（`make audit` 门禁 verdict=blocked：48 题 token 与标注页错位、6 题题面实体全库零命中），按「宁缺毋滥」协议本轮为**证据链模式**（`expected_sources: null`）——不产出 hit_rate/mrr 数字，用不依赖真值的结构性证据（来源分布、top-1 漂移、模式间一致率）对比四组。标注定版后翻配置重跑即可补全正式指标。

## 2. 四组对比结果

### 2.1 运行耗时（本机 CPU，单进程顺序执行）

| 组 | 耗时 | 备注 |
|---|---|---|
| Vector | 21.5s | 查询编码（bge-m3）为主 |
| BM25 | 0.5s | 纯词袋，无模型 |
| Hybrid | 22.5s | 向量路编码为主 |
| Hybrid+Reranker | **7600.2s ≈ 2.1h** | 精排 120 题 × 30 候选为主（≈63s/题） |
| ver24 / ver20（对照） | 22.6s / 22.5s | 与 Hybrid 同量级 |

> 精排成本注记：CrossEncoder 不设 `max_length` 时按模型上限 8192 处理 2500 字符候选块，首轮实测 30 候选/题 118s → 120 题 17793s（**4.9 小时**）；改为 512 token 截断（BAAI 官方用法，`retrieval/rerank.py`）后实测 ≈63s/题 → **2.1 小时**（微基准 39s/题偏乐观，真实链路含两路粗排交织与长时热负载）。该参数已写进 api.md v0.13。
> 耗时随运行环境浮动：同配置同结果，基准报告（`reports/baseline/`）10.2s vs 本机约 21s（约 2×速差）；回归判定以结果重合为准，耗时仅作 >2× 提示（本次 `struct_multisrc_v1` 的 warn 即来自这一项，检索结果逐题一致）。

### 2.2 来源分布与命中结构（不依赖真值的结构性证据）

| 组 | Top-5 中 dev_guide 占比 | Top-1 为 dev_guide | api_use 36 题 top1=guide | error_code 11 题 top1=guide |
|---|---|---|---|---|
| Vector | 312/600 = 0.520 | 41/120 | 5/36 | 11/11 |
| BM25 | 216/600 = 0.360 | 34/120 | 8/36 | 8/11 |
| Hybrid | 233/600 = 0.388 | 33/120 | 4/36 | 8/11 |
| Hybrid+Reranker | 223/600 = 0.372 | 29/120 | 6/36 | 8/11 |

**模式间 top-1 一致率**：Vector↔BM25 0.292 · Vector↔Hybrid 0.567 · BM25↔Hybrid 0.558——两路检索行为差异大（一致率低），融合确认能改变排序结构。

**读法**：error_code 题上 Vector 11/11 全中 dev_guide；api_use 上 BM25 反而最好（8/36）、Vector 只有 5/36——与指南 §8.1 的判断一致（精确 token 类问题需要词面匹配，纯向量容易过泛）。

### 2.3 Rerank 增益（hybrid → hybrid_rerank）

**top-1 漂移**：59/120（49%）题目的 top-1 发生了变化。按题型：debug 5/7 · error_code 7/11 · version 7/13 · api_use 18/36 · config 14/30 · faq 5/11 · operation 3/12。

**结构性代理指标——技术 token 覆盖率**（题目 ASCII 技术 token 出现在 top-1 块正文的比例；**结构性证据，非真值指标**，token 在块内 ≠ 块回答了问题）：

| 题型 | Hybrid | Hybrid+Reranker | Δ |
|---|---|---|---|
| error_code | 0.591 | 0.886 | **+0.295** |
| api_use | 0.898 | 0.912 | +0.014 |
| config | 0.867 | 0.867 | 0.000 |
| operation | 1.000 | 0.972 | −0.028 |
| version | 0.936 | 0.859 | −0.077 |
| debug | 0.929 | 0.786 | −0.143 |
| **全部** | 0.867 | 0.881 | **+0.015** |

「top-1 块含题目全部技术 token」的题数：90/120 → 90/120（持平）。

**典型案例（人工核验）**：

- ✅ **改善 Q012**（DataReader `create_readcondition` 的 SampleStateMask）：top-1 从手册叙述节（5.5.5 ReadConditions）切到 dev_guide 的 API 参考（`FooDataReader_create_readcondition`，含函数签名与参数表）——精确 token 题的理想行为。
- ✅ **改善 Q001**（创建 DomainParticipant）：从父节 6.3 切到更精确的 6.3.1 创建DomainParticipant。
- ❌ **劣化 Q003**（DomainParticipant Listener mask 如何设置）：top-1 被 7.2.1 创建Topic 顶掉——该块含同样的 `Listener *a_listener, StatusKindMask &mask` 参数模式，但实体是 Topic 而非 DomainParticipant（交叉编码器被参数模式相似性误导，score 0.997 高分错位）。
- ❌ **劣化 Q010**（`delete_participant` 失败条件与错误码）：原 top-1（6.3.2 删除DomainParticipant）正文含 `DDS_RETCODE_PRECONDITION_NOT_MET` 的精确答案，被 11.6.2 发布端示例代码顶掉。

**结论**：精排改变近半题目排序；结构性证据整体略正（token 覆盖 +0.015，error_code 类大幅改善），但存在实体错位的劣化案例（Q003/Q010 型）。**是否净提升需真值标注定版后用 hit_rate/mrr 判定**——指南 §8.2 明示「必须先有 Baseline 才知道是否真的产生提升」，此处不预设结论。

## 3. Version-aware 结果（§8.3）

**机制**：`retrieval.params.version_pref` + `version_boost`（配置级、四模式通用）；候选池内 min-max 归一化后给命中版本加成（示例 0.1），再截断 Top-K。未配置时行为与现状逐字节一致（零回归，既有实验报告不受影响）。

**方向核验**（两个相反方向对照组，同一题集）：

| 配置 | 偏好 | dev_guide 占比 | top-1 为 guide |
|---|---|---|---|
| `struct_multisrc_hybrid` | 无 | 233/600 = 0.388 | 33/120 |
| `struct_multisrc_hybrid_ver24` | v2.4（= dev_guide） | **285/600 = 0.475** | **62/120** |
| `struct_multisrc_hybrid_ver20` | v2.0（= user_manual） | **162/600 = 0.270** | **15/120** |

双向单调成立（ver24 > baseline > ver20），机制在真实语料上按预期生效。当前语料版本号与来源一一对应（manual=2.0 / guide=2.4），机制按通用 metadata 字段实现，真实多版本同源场景出现时零改动可用。

**score 语义**：boost 生效时 score 为「池内归一化分 + 加成」（可超 1.0），跨查询/跨配置不可比——已写进 api.md v0.13，C 的弱证据阈值对该类配置不适用绝对阈值（沿用「返回条数 < top_k / 空 sources」信号）。

## 4. 局限与后续

- **正式指标待真值标注**：`make audit` 门禁解除后，把多来源配置的 `expected_sources` 翻回 `evaluation/datasets/expected_sources.jsonl` 重跑，即可补 hit_rate@5 / mrr@5 与基线差值（一步操作）。
- **A 终版 Node 集未冻结**：若 A 交付终版后产物变更，索引需重建、四组需重跑（增量成本：向量重建约 25 分钟（D 实测，Ryzen 7 9700X）/本机冷启首建实测 87 分钟 + 检索约 2 分钟 + 精排约 2.1 小时（本机））。
- **精排 CPU 成本**：512 截断后单组约 2.1 小时（本机）；全量回归矩阵含精排组时建议 `--only` 选择性运行（D 的 `run_regression.py` 支持）。
- **双版本同源场景当前不存在**：版本加权/过滤的机制是通用的，但「同一文档多版本并存」的真实场景要等语料扩充后才能实测。
- **精排增益结论**：§2.3 完成后如实记录——指南 §8.2 明示「必须先有 Baseline，才知道它是否真的产生提升」，无增益也是有效结论。
