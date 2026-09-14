# Demo 演练手册（成员 D · 第四周，指南 §8 D 任务 3）

> **v0.1（2026-09-14）**：首版。四段演示场景已在**本机 live 通路实测**（真实 bge-m3 检索 + 真实本地 LLM 出词），耗时与引用页码均为实测值，非估算。
> 目的：周五验收与最终汇报可照着敲；任何一步与本文不符即为环境异常，按 §5 兜底排查。

---

## 1. 环境前提（一次性）

| 组件 | 要求 | 本机实测值 |
|---|---|---|
| Ollama | 监听 `127.0.0.1:11434` | v0.33.3；模型 `qwen3.5-9b`(8.8GB) / `qwen3.8-27b`(13GB) |
| LLM 网关 | `python models/llm_gateway.py` → `127.0.0.1:11500` | 存在意义：Ollama 0.33.x 的 OpenAI 兼容层会静默丢弃 `think:false`，网关转原生 `/api/chat` 强制关思考（属 D 域基础设施，`models/` 不入 Git） |
| Embedding | bge-m3 已在 HF 本地缓存 | **必须** `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`，否则 SentenceTransformer 初始化对每个 config 文件反复 HEAD，挂数分钟 |
| 索引 | 目标实验的索引目录存在且指纹匹配 | 六套索引全部可用（见 `docs/index-rebuild-drill.md`） |
| `.env` | `RAG_MODE=live`、`RAG_EXPERIMENT_CONFIG=<实验 yaml>`、`LLM_BASE_URL=http://127.0.0.1:11500/v1` | 密钥只引 env 名，不入库 |

## 2. 启动序列（三条命令）

```bash
python models/llm_gateway.py                    # 终端 A，长期驻留
ollama list                                     # 若 11434 无服务，先跑任意 ollama 命令拉起
make serve                                      # 终端 B：HF_HUB_OFFLINE=1 后 uvicorn
```

预期（实测）：`make serve` 先做检索器预热再绑端口，随后

```bash
curl http://127.0.0.1:8000/healthz     # → {"status":"ok","mode":"live"}
```

## 3. 四段演示脚本

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

### 附 · 引用回查与三级日志（每段演示后随手展示）

```bash
curl http://127.0.0.1:8000/sources/<rid>     # 200：question / answer / sources
tail -n 1 logs/retrievals.jsonl              # 请求级检索明细（含实验名/hash8/latency）
tail -n 1 logs/requests.jsonl                # HTTP 级耗时与状态
```
实测：rid `33a22b78cb88` 在 `requests.jsonl`/`retrievals.jsonl`/`sources.jsonl` 三处均可关联（`config_hash8=0a7830b7`、`index_dirname=struct_bge-m3_0a7830b7`、`mode=vector`）。

## 4. 已知缺口（演示时必须如实说明）

1. **HTML 引用无法跳转原文 URL**：Node 产物有 `source_url`（1305/1305 非空），但 `SourceRef` wire 只投影 7 字段（`node_id/source_id/source_name/section/page_print/page_physical/score`），**`source_url` 不在其中**，`docs/api.md` 亦未定义，前端 `web/` 零引用。故 HTML 引用目前只能显示文件名（如 `group___c_publication.html`）。详见 week4 review §3 缺口 W1。
2. **Reranker 未落地**：`retrieval/retriever.py` 对 `hybrid_rerank` 仍抛 `NotImplementedError`（B 域第四周任务），Demo 不讲精排。
3. **指标不可讲**：现库 120 条标注仍是"检索 top-1 回显"的循环版（与规范检索仅 44/120 吻合），任何 hit_rate/mrr 数字都不得出现在汇报页（回归矩阵默认只走明细通道）。
4. 第三周遗留：`semantic` 超长块待 A 处置，semantic 实验暂不进演示链路。

## 5. 现场故障与兜底

| 症状 | 根因 | 处置 |
|---|---|---|
| `make serve` 卡在启动、端口迟迟不绑 | 未设 `HF_HUB_OFFLINE=1`，embedding 在线取文件 | 带上离线开关重启（本文 §1） |
| `/healthz` 报 `mode:mock` | `.env` 未加载或 `RAG_MODE` 非 live | 检查仓库根 `.env`；live 组装失败会给一行可读拒绝 |
| SSE 先出 `sources` 后紧跟 `error` | LLM 后端不可达（网关/Ollama 未起） | 起 `llm_gateway.py` → `ollama list` 验证；引用已下发可回查（X3 语义），不静默降级 |
| 中文问题在 curl 下 500 | Git Bash 按 GBK 发 body，网关 JSON 解码失败 | 用 UTF-8 客户端（Python/httpx、前端页面）发；不是服务缺陷 |
| 首个问题特别慢 | 预热只做一次检索，模型首次出词含加载 | 演示前先跑一遍场景 1 当暖场 |

## 6. 可选：MCP 宿主演示

`make mcp`（stdio）或 `make smoke-mcp`（端到端冒烟：initialize → list_tools → 两工具 → 回查一致）。工具 `query_knowledge_base(question, top_k)` / `get_sources(request_id)`，rid 前缀 `mcp-` 与 HTTP 区分。契约与注意项见 `docs/mcp.md`。

## 7. 演示题清单（可直接投屏）

| # | 场景 | 问题 | 现场判据（真值） |
|---|---|---|---|
| 1 | 单来源定位 | DurabilityQosPolicy 的 kind 字段默认值是什么？ | top-1 印刷127/物理133；答案不虚构语言级默认值 |
| 2 | 拒答 | ZRDDS 的错误码 E1003 代表什么含义？ | 明确"无法确认"，不编造错误码表 |
| 3 | 越界 | ZRDDS 用户手册第 300 页讲了什么？ | 明确"无法确认"，手册最大印刷页 289 |
| 4 | 跨来源 | 用 DDS_Publisher 创建 datawriter 的接口原型和调用步骤是什么？ | 引用同现 `zrdds_dev_guide` + `user_manual`；主动披露 C API / C++ 接口差异 |
| 5 | 精确 token | RapidIO 相关的 QoS 策略怎么配？ | 引用落在第10章 QoS 策略区间（印刷 125~161） |
| 6 | 回查 | （任一 rid）`GET /sources/<rid>` | 200 且 answer+sources 完整；三级日志按 rid 关联 |

> 表题 5 的实测值待下次演练补录（本轮未单独跑）。
