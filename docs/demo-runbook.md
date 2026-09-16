# Demo 演练手册（成员 D · 第四周，指南 §8 D 任务 3）

> **v0.7（2026-09-16 深夜·二）**：新增 **§8 各实验配置的运行策略（按迭代顺序）**——13 个配置的分组/成本/演示用法、相关度分数四条通路的口径对照（回答“BM25 下相关度为什么显得很低”）、通路切换节奏；§3 补“停止生成”与本地原文链接；§4 补分数不可比一条。详见 `docs/week4-delivery-review.md` §3.10。
> **v0.6（2026-09-16 深夜）**：前端四项经 D 代修后浏览器端到端实测可用（F1 真实统计 / F2 markdown / F3 节点原文 / F4 模式切换）；新增第 4 节前的前端就绪说明与 §5"左侧流程走完但主区无回答"兜底行（rAF 停摆导致的不渲染已修）；缺口 3 事实更新（P0 编码已修、三题 token 仍缺）。详见 `docs/week4-delivery-review.md` §3.9。
> **v0.5（2026-09-15 晚）**：§4 缺口 2 改写——精排阻塞已由 B 随 PR#40 修复（打分 to_thread），D 本机 ticker 复核热题 159/161 心跳；`hybrid_rerank` 从此**可进演示动线**（首切/冷加载 ~26s，靠 §3 预热口径覆盖）。
> **v0.4（2026-09-15）**：F4 落地（api.md v0.14）——**场景间切换检索实验不再需要重启服务**：`/query` 请求体带可选 `experiment`（白名单见 `/healthz` 的 `experiments`），见 §3 开头"通路切换"。
> **v0.3（2026-09-15）**：已知缺口 2 重写——B 的 PR#38 已落地 hybrid_rerank（四组对比入库），但 live 精排打分**阻塞事件循环**（本机实测热题 15.1s/题、首题 27.8s、B 机 ~63s/题，冻结期间整个服务不响应），演示动线不挂该配置，实测与解决方法见 `docs/week4-delivery-review.md` §3.5.1。
> **v0.2（2026-09-15）**：LLM 后端叙述改为 **API 为主**（`.env.example` 默认 OpenRouter 免费档），本地 Ollama + 网关降为可选附录（`models/` 不入 Git，属本机个人研究）；同步 PR#36（E）事实：前端 feedback 按钮已接入、`source_url` 前端外链闭环、semantic 超长块已随 A 的 PR#32 销项、指标口径更新（audit 首次 pass 但正式指标仍冻结）。
> **v0.1（2026-09-14）**：首版。四段演示场景已在**本机 live 通路实测**（真实 bge-m3 检索 + 真实本地 LLM 出词），耗时与引用页码均为实测值，非估算。
> 目的：周五验收与最终汇报可照着敲；任何一步与本文不符即为环境异常，按 §5 兜底排查。

---

## 1. 环境前提（一次性）

| 组件 | 要求 | 本机实测值 |
|---|---|---|
| LLM 后端 | 任何 OpenAI 兼容 API：`.env` 的 `LLM_BASE_URL` / `LLM_MODEL` / `LLM_API_KEY` 指向所选服务商（默认路线） | `.env.example` 预填 OpenRouter 免费档示例；密钥只引 env 名，不入库 |
| Embedding | bge-m3 已在 HF 本地缓存 | **必须** `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`，否则 SentenceTransformer 初始化对每个 config 文件反复 HEAD，挂数分钟 |
| 索引 | 目标实验的索引目录存在且指纹匹配 | 六套索引全部可用（见 `docs/index-rebuild-drill.md`） |
| `.env` | `RAG_MODE=live`、`RAG_EXPERIMENT_CONFIG=<实验 yaml>` | — |

### 1.1 可选：本地 LLM 后端（Ollama + 网关，离线演示备选）

`models/llm_gateway.py` **不入 Git**，属成员 D 本机个人研究；仅当本机具备以下组件时可用：

| 组件 | 要求 | 本机实测值 |
|---|---|---|
| Ollama | 监听 `127.0.0.1:11434` | v0.33.3；模型 `qwen3.5-9b`(8.8GB) / `qwen3.8-27b`(13GB) |
| LLM 网关 | `python models/llm_gateway.py` → `127.0.0.1:11500` | 存在意义：Ollama 0.33.x 的 OpenAI 兼容层会静默丢弃 `think:false`，网关转原生 `/api/chat` 强制关思考 |
| `.env` | `LLM_BASE_URL=http://127.0.0.1:11500/v1`、`LLM_MODEL=<ollama list 里的名字>`、`LLM_API_KEY=ollama`（网关不校验，占位即可） | — |

## 2. 启动序列

```bash
make serve    # .env 指向所选 LLM 后端（API 或 §1.1 本地网关）
```

预期（实测）：`make serve` 先做检索器预热再绑端口，随后

```bash
curl http://127.0.0.1:8000/healthz     # → {"status":"ok","mode":"live"}
```

**走 §1.1 本地后端时的完整序列**（三条命令）：

```bash
python models/llm_gateway.py                    # 终端 A，长期驻留
ollama list                                     # 若 11434 无服务，先跑任意 ollama 命令拉起
make serve                                      # 终端 B：HF_HUB_OFFLINE=1 后 uvicorn
```

**收摊顺序**（演示结束或换配置前）：先停 `make serve` 的 uvicorn，再停 `llm_gateway.py`（如用了 §1.1），
最后按需 `ollama stop <模型>` 释放显存（只卸载模型、不终止 11434 服务进程）。核验端口是否释放：

```bash
netstat -ano | grep LISTENING | grep -E ":8000|:11500|:11434"
```

## 3. 四段演示脚本

> **可随时演示的两个交互（v0.16）**：①**停止生成**——回答过程中输入框右侧出现「停止生成」，点它即中止本次回答；
> 已产出的部分保留、引用与请求标识仍可回查/反馈（服务端把部分答案以 `…（已终止）` 留档，上游 LLM 流随之关闭）。
> ②**打开原文**——引用卡与"节点详情"里的 HTML 外链指向本服务的 `GET /documents/{source_id}/{file}`，服务的是 A 的本地
> HTML 快照，**离线可用**（此前 `docs.zrtechnology.com` 是配置里的占位域名，点了必然打不开）。
> 节点详情按来源格式展示：PDF 给印刷页/物理页（跨页显示区间，如 `印刷页 80–81`）+ 正文；HTML 给文件/标题 + 章节路径 + 原文外链
> （不显示页码——HTML 没有页面概念）。

> **选哪条检索通路演示**：见 §8——按"基线 → 换分块 → 换检索模式 → 多来源 → 精排"的迭代顺序讲，一层只动一个变量。

**通路切换（v0.4 起，无需重启）**：各场景的"配置"行记录的是该场景**实测时的启动配置**；现在同一服务内可直接切换——`/query` 请求体带 `"experiment": "<实验ID>"`（如 `struct_multisrc_v1`、`struct_multisrc_hybrid`），白名单 = `/healthz` 返回的 `experiments`。注意：**首次切换到某实验需现场装载模型/索引（数秒~数十秒），演示前先把要用到的实验各点一题预热**；`hybrid_rerank` 因精排阻塞事件循环（v0.3 缺口 2）仍不建议挂入演示动线。

```bash
curl -N -X POST http://127.0.0.1:8000/query -H "Content-Type: application/json" \
     -d '{"question": "…", "experiment": "struct_multisrc_v1"}'
```

### 场景 1 · 单来源精确定位 + 引用真值（基线）

- 配置：`RAG_EXPERIMENT_CONFIG=configs/experiments/struct_v1.yaml`
- 问题：`DurabilityQosPolicy 的 kind 字段默认值是什么？`
- **预期引用**：top-1 = `10.7 DurabilityQosPolicy`，**印刷页 127 / 物理页 133**（页码地面真值 = 页眉印刷数字，差值恒 6）
- **实测**（2026-09-14，rid `33a22b78cb88`）：事件序列 `sources → token×372 → done`，**9.0s**；top-1 正是 10.7 节 印刷127/物理133；答案按 Prompt 规则给出 `VOLATILE_DURABILITY_QOS`（引 [1]）并**明确声明手册未定义语言级枚举默认值**，未虚构。
- 讲点：evidence-first（引用先于答案下发）+ 双页码 + 不编造。

### 场景 2 · 无证据拒答（Abstention）

同一服务连问两题（两题真值均已核实为"知识库里没有"）：

| 问题 | 真值依据 | 实测 |
|---|---|---|
| `ZRDDS 的错误码 E1003 代表什么含义？该如何处理？` | 8-30 审计与 A 的 html 产物均证实 **E1003 不存在**（`error_code` 字段 0 条命中） | `sources→token×196→done`，**7.6s**；答案："**无法确认**……没有任何一处提到具体的 API 错误码列表，也未提及 E1003"，并逐条说明 5 个片段实际是什么 |
| `ZRDDS 用户手册第 300 页讲了什么内容？` | 手册印刷页最大 **289**，300 越界 | **6.7s**；答案："**当前知识库无法确认**"，并列出检索到的实际页码（3/4/259/263/281）作为反证 |

- 讲点：拒答是可解释的（说明缺什么），不是空话。
- ⚠ 演示时**别**问"某个真实存在的错误码"，那属于检索命中区。

### 场景 3 · 跨来源联合 + 冲突披露（多来源）

- 配置：`RAG_EXPERIMENT_CONFIG=configs/experiments/struct_multisrc_v1.yaml`（1606 节点：PDF 301 + HTML 1305）
- 问题：`用 DDS_Publisher 创建 datawriter 的接口原型和调用步骤是什么？`
- **实测**（rid `19ed56607bd4`）：`sources→token×1280→done`，**29.0s**；5 条引用**两来源共存**——[1][3][4][5] `zrdds_dev_guide`（HTML 函数页），[2] `user_manual` 印刷页 80（8.3.1 创建DataWriter）。
- 答案主动指出："不同文档来源对函数原型的定义存在差异：[1][3][4][5] 是 **C 语言 API**，[2] 是 **C++ 风格的用户手册接口**" → §8.4 冲突披露在真实通路生效。

### 场景 4 · Hybrid 检索走 live 服务通路

- 配置：`RAG_EXPERIMENT_CONFIG=configs/experiments/struct_multisrc_hybrid.yaml`（引用制：复用 `d57f695e` 向量 + `3a834db2` 词袋，零重建）
- 同一问题（场景 3 原题对照）
- **实测**（rid `837a938406c8`）：**19.2s**；5 条引用分数 **0.0276~0.0318**（RRF 量纲，满量程 2/61≈0.0328，见 api.md v0.9），与向量余弦（0.72~0.75）完全不同尺度；来源仍是两来源混合，但排序把 HTML"发布模块"总览页提到 top-1。
- 讲点：三模式（vector/bm25/hybrid）同一套门面，换实验只换配置。

### 附 · 引用回查与四级日志（每段演示后随手展示）

```bash
curl http://127.0.0.1:8000/sources/<rid>     # 200：question / answer / sources
tail -n 1 logs/retrievals.jsonl              # 检索级明细（含实验名/hash8/latency）
tail -n 1 logs/requests.jsonl                # HTTP 级耗时与状态
curl -X POST http://127.0.0.1:8000/feedback -H "Content-Type: application/json" \
     -d '{"request_id":"<rid>","rating":"down","comment":"第2条引用与问题无关"}'   # 反馈级
tail -n 1 logs/feedback.jsonl
```
实测：rid `33a22b78cb88` 在 `requests.jsonl`/`retrievals.jsonl`/`sources.jsonl` 三处均可关联（`config_hash8=0a7830b7`、`index_dirname=struct_bge-m3_0a7830b7`、`mode=vector`）。

反馈端点（api.md **v0.10**）三条实测：对**上一次服务会话遗留的 rid** `837a938406c8` 打 `up` → 201（记录持久化在 `sources.jsonl`，跨重启仍可归因）；未知 rid → **404「无法归因反馈」，且不落任何孤儿记录**；新生成的 rid 带 `node_ids` 打 `down` → 201。

> 前端反馈按钮已由 E 接入（PR#36：回答下方 up/down 面板，走同一端点）；Demo 时用 curl 现场敲亦可，讲点是"用户反馈可回流成评测语料"。

## 4. 已知缺口（演示时必须如实说明）

1. **SSE wire 第 8 字段待会签**：HTML 引用的 `source_url` 可经 `GET /sources/{rid}`（及 MCP `get_sources`）回查获得（api.md **v0.11**），前端（E PR#36）已消费该通道并渲染"打开 HTML 原文"外链；但 **SSE 的 `sources`/`done` 事件仍是 7 字段、不含该键**，正式扩进 wire 需 B/C/E 会签。演示话术："引用可溯源到原文页——引用卡上可直接点开外链。"
2. **Reranker 可进演示动线（阻塞已修复）**：`hybrid_rerank` 检索与四组对比已入库（`docs/evaluation.md`）；**阻塞问题已由 B 随 PR#40 修复**（打分 `asyncio.to_thread` 移出事件循环），D 本机 ticker 复核：热题 16.1s 期间心跳 **159/161**（修复前同口径 0 跳动）——服务不再冻结。剩余成本是**首切/冷加载约 26s**（bge-m3 + CrossEncoder 冷加载），已由 §3"通路切换"的预热口径覆盖：演示前先把 `struct_multisrc_hybrid_rerank` 各点一题预热，现场再问即为热态。话术："精排通路已并发化（打分移线程），首次装载后单题约 16s、服务全程可响应。"
3. **指标数字不上汇报页**：E 的 P0 六题编码损坏已修复（PR#45，全库 0 处乱码），但三题（Q021/Q023/Q028）新题干用了产物中零出现的 camelCase 字段名，`make audit` 仍判 blocked；P1 宽区间复核未完成（见 `docs/week4-delivery-review.md` §3.8.2）——**正式 hit_rate/mrr 仍不得出现在汇报页**，回归默认只走明细通道。
4. **相关度分数跨通路不可比**：bm25（原始词面分，无上界）与 hybrid（RRF，~0.03）的分数量纲和 vector（cosine 0~1）/hybrid_rerank（sigmoid 0~1）不是一回事，前端已按模式换标签与口径（见 §8.2）；汇报时勿把 bm25 的原始分与 vector 的百分比并列比较。

> **前端四项已就绪（2026-09-16 实测）**：知识库状态卡取真实 `/healthz kb`、答案 markdown 渲染（含表格/代码）、"查看节点详情"显示该条引用原文（跨实验可查，api.md v0.15）、检索模式下拉可在 13 个实验间切换。演示建议：先按默认实验（`struct_v1`）跑场景 1/2，再切 `struct_multisrc_v1` 跑场景 3——切换后首题含该实验装载（约 30s），用"先点一题预热"话术覆盖。

## 5. 现场故障与兜底

| 症状 | 根因 | 处置 |
|---|---|---|
| `make serve` 卡在启动、端口迟迟不绑 | 未设 `HF_HUB_OFFLINE=1`，embedding 在线取文件 | 带上离线开关重启（本文 §1） |
| `/healthz` 报 `mode:mock` | `.env` 未加载或 `RAG_MODE` 非 live | 检查仓库根 `.env`；live 组装失败会给一行可读拒绝 |
| SSE 先出 `sources` 后紧跟 `error` | LLM 后端不可达（API 密钥/网络，或 §1.1 网关/Ollama 未起） | 核对 `.env` 的 `LLM_*` 指向；本地后端则起 `llm_gateway.py` → `ollama list` 验证；引用已下发可回查（X3 语义），不静默降级 |
| 中文问题在 curl 下 500 | Git Bash 按 GBK 发 body，网关 JSON 解码失败 | 用 UTF-8 客户端（Python/httpx、前端页面）发；不是服务缺陷 |
| 首个问题特别慢 | 预热只做一次检索，模型首次出词含加载 | 演示前先跑一遍场景 1 当暖场 |
| 左侧流程走完但主区一直没有回答 | 旧版前端把"空状态→回答区"包在 `mode="out-in"` 过渡里，离场依赖 rAF；标签页被遮挡/后台时 rAF 停摆，回答区永不挂载 | **已修（2026-09-16，D 代修）**：展示路径去过渡包装，内容可见性不再依赖动画帧；若现场仍复现，把该标签页切到前台一次即可（rAF 恢复） |

## 6. 可选：MCP 宿主演示

`make mcp`（stdio）或 `make smoke-mcp`（端到端冒烟：initialize → list_tools → 两工具 → 回查一致）。工具 `query_knowledge_base(question, top_k)` / `get_sources(request_id)`，rid 前缀 `mcp-` 与 HTTP 区分。契约与注意项见 `docs/mcp.md`。

## 7. 演示题清单（可直接投屏）

| # | 场景 | 问题 | 现场判据（真值） |
|---|---|---|---|
| 1 | 单来源定位 | DurabilityQosPolicy 的 kind 字段默认值是什么？ | top-1 印刷127/物理133；答案不虚构语言级默认值 |
| 2 | 拒答 | ZRDDS 的错误码 E1003 代表什么含义？ | 明确"无法确认"，不编造错误码表 |
| 3 | 越界 | ZRDDS 用户手册第 300 页讲了什么？ | 明确"无法确认"，手册最大印刷页 289 |
| 4 | 跨来源 | 用 DDS_Publisher 创建 datawriter 的接口原型和调用步骤是什么？ | 引用同现 `zrdds_dev_guide` + `user_manual`；主动披露 C API / C++ 接口差异 |
| 5 | 精确 token | RapidIO 相关的 QoS 策略怎么配？ | **实测**（rid `bad0c2ceb9f4`）top-1 = 10.21 RapidIOConfigQosPolicy 印刷 147/物理 153，top-3 = 10.22 RapidIOControllerQosPolicy（148），top-4/5 = 21.2 RapidIO通信配置（256）；答案分"控制器参数配置（工厂端）+ 通信端选择（参与者端）"两步 |
| 6 | 回查 | （任一 rid）`GET /sources/<rid>` | 200 且 answer+sources 完整；四级日志按 rid 关联 |

## 8. 各实验配置的运行策略（按迭代顺序）

> 演示时如何选配置、每条通路的花费与"分数怎么看"。索引成本为**本机实测**（9700X / CPU / bge-m3）；
> `已建`＝本机 `indexes/` 里已有可用索引，演示当天不必重建。

### 8.1 迭代顺序与分组

| 序 | 实验 | 阶段 | 检索模式 | 分块 | 知识源 | 索引成本 | 定位（演示用法） |
|---|---|---|---|---|---|---|---|
| 1 | `struct_v1` | baseline | vector | struct | 手册单源 | 468s（已建） | **主基线**：场景 1（精确定位+真值页码）、场景 2（拒答） |
| 2 | `struct_multisrc_v1` | baseline | vector | struct | 手册+HTML | 1486s≈25min（已建） | **多来源基线**：场景 3（跨来源联合、C API 取 HTML） |
| 3 | `final_v1` | product | vector | struct | 手册+HTML | 与 ②同 hash8，**共用索引** | 产品态终跑（回答侧四指标＋source_priority 定稿）；演示用 ② 即可，二者检索行为相同 |
| 4 | `semantic_v1` | baseline | vector | semantic | 手册单源 | 719s（已建） | 分块方案对照（A 域）；讲"方案对比"时提，不单独演示 |
| 5 | `hybrid_v1` | baseline | vector | hybrid | 手册单源 | 1177s（已建） | 同上（结构+语义混合分块） |
| 6 | `struct_bm25` | ablation | bm25 | struct | 手册单源 | 0.3s（已建） | 词面检索消融：讲"无神经网络也能召回"、专有名词命中 |
| 7 | `struct_hybrid` | ablation | hybrid | struct | 手册单源 | 引用制，**零重建** | RRF 双路融合消融 |
| 8 | `struct_multisrc_bm25` | ablation | bm25 | struct | 手册+HTML | 0.1s（已建） | 多来源 × 词面 |
| 9 | `struct_multisrc_hybrid` | ablation | hybrid | struct | 手册+HTML | 引用制，零重建 | 多来源 × 融合 |
| 10 | `struct_multisrc_hybrid_rerank` | ablation | hybrid_rerank | struct | 手册+HTML | 引用制 + 精排权重 2.2GB | **精排通路**：场景 4；首切/冷加载约 26s，热态约 16s/题 |
| 11 | `struct_multisrc_hybrid_ver20/ver24` | ablation | hybrid | struct | 手册+HTML | 引用制，零重建 | 版本加权对照（§8.3） |
| — | `example_v1` | — | vector | struct | 手册单源 | — | **模板文件，勿用于演示**（无 `sources[].id` 语义、无对照基准） |

**为何是这个顺序**：先立基线（①②）→ 再换分块方案（④⑤，验证"知识工程质量"）→ 再换检索模式（⑥⑦，验证"检索算法贡献"）
→ 多来源下重复一遍（⑧⑨）→ 最后叠精排与版本加权（⑩⑪）。每一层只动一个变量，且有 `compare_baseline` 指向上一层，
这就是 §10 的消融口径；**演示时按同一顺序讲，听众能看出每层各加了什么**。

### 8.2 相关度指标怎么看（回答"为什么 BM25 下面看起来相关度很低"）

**结论：不是统计口径写错，而是四条通路的分数根本不同量纲**——前端此前用同一把尺子（>1 除以 100、再截断到 0~1）渲染，
于是 BM25 的 20 分显示成 "20%"、RRF 的 0.03 显示成 "3%"，都像"很不相关"，可它们各自都是当次 top-1。

| 模式 | 分数是什么 | 量纲/范围 | 能否跨查询比较 | 前端现在怎么显示（v0.16 起） |
|---|---|---|---|---|
| `vector` | cosine 相似度 | 0~1（实测 0.46~0.78） | ✅ 可比 | 「向量相关度 xx%」+ 强/中/弱关联 |
| `hybrid_rerank` | 交叉编码器 sigmoid | 0~1（实测 0.084~0.991） | ✅ 可比 | 「精排相关度 xx%」 |
| `bm25` | Robertson BM25 原始分 | 无上界（实测 7~56） | ❌ **不可比** | 「BM25 词面分 原始值」+ 池内相对进度条 + 「第 N 位」+ 不可比说明 |
| `hybrid` | RRF 融合分（1/(k+rank) 之和） | ~0.016~0.033 | ❌ 只有排序意义 | 「RRF 融合分 原始值」+ 池内相对进度条 + 「第 N 位」+ 不可比说明 |

- **BM25 分不可比的三个理由**：①无上界，长文档天然偏高；②它是词面重叠统计量，不是语义相似度——两个都不含查询词的文档也可能得低分而非 0；
  ③换了查询就换了词表，跨查询没有统一原点。**同一次检索内部**的排序有意义（这才是它存在的理由），所以前端改成"池内相对 + 位次"。
- **RRF 分只承载排名信息**：它是 rank 的函数，分值与相关性强弱不成比例；任何"阈值 0.5 以上算强证据"的说法在 hybrid 下无意义（X1 决议已按 mode 定标）。
- **演示话术**：切到 `struct_bm25` 时主动说明"这是词面检索，看的是命中与排序，不是相似度百分比；界面已按模式换标签"——
  比让听众自己看到 "8%" 生疑要好。
- 需要"打分看起来高"的通路就选 `vector` 或 `hybrid_rerank`；需要"专有名词/错误码一字不差命中"就讲 `bm25`。

**与检索质量的关系（避免混淆）**：上面说的是**显示口径**。至于"哪条通路检索得更准"——正式 hit_rate/mrr 仍冻结
（E 的标注未定版，见 §4 缺口 3），所以**汇报里不给通路间质量排名数字**，只讲机制与场景适配。

### 8.3 演示时的通路切换节奏

1. 开场用默认 `struct_v1`（服务端启动即预热，首题 ~9s）：场景 1、场景 2。
2. 切 `struct_multisrc_v1`：**首次切换该实验含装载（约 29s）**，用"先点一题预热"话术覆盖；随后场景 3。
3. 如需讲检索模式对比，切 `struct_bm25`（冷暖都很快，0.1~0.3s）与 `struct_hybrid`（引用制，零重建）。
4. 精排（`struct_multisrc_hybrid_rerank`）仅在**预留时间**时演示：首切 ~26s，热态 ~16s/题；讲解重点是"打分移出事件循环，
   生成期间服务仍可响应"（PR#40 修复，D 本机 ticker 复核 159/161 心跳）。
5. 全程不需要重启服务：切换只改请求体里的 `experiment`（api.md v0.14+），已建索引全部复用。
