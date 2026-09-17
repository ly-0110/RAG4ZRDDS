# 检索日志字段定义（retrieval log schema）

> 定义 `logs/retrievals.jsonl` 的字段与语义，作为离线分析与日志关联的契约。

## 1. 目的与范围

- 目的：离线分析「检索环节发生了什么」——脱靶案例回查、错误案例采集、
  弱证据信号统计、性能回归，均以本日志为地面数据。
- 范围：**仅覆盖 server live 路径**的每次检索调用（`pipeline.retriever.retrieve`）。
  `run_experiment` 离线评测已有独立报告（`evaluation/reports/*.json`），不重复入此日志。

## 2. 存储格式

| 项 | 约定 |
|---|---|
| 文件 | `logs/retrievals.jsonl`（`LOG_DIR` 之下，与 `requests.jsonl` 同目录） |
| 格式 | 追加式 JSONL，每次 `retrieve()` 调用**一条**记录；`ts`（ISO 时间戳）由 `JsonlLog` 框架自动前置，无需业务侧提供 |
| 生命周期 | 追加不截断；损坏行容忍（与 `PersistentSourcesStore` 同原则：日志不阻断服务） |
| 入库 | 不入 Git（`logs/` 已在 .gitignore），仅本机 |

## 3. 字段定义

每次检索一条记录，字段如下（除注明外均必填）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `request_id` | str \| null | 关联 `requests.jsonl` 的请求级记录；非 HTTP 触发的检索调用为 `null` |
| `experiment` | str | 实验名（`cfg.experiment.name`），如 `struct_v1` |
| `config_hash8` | str | 配置身份 hash（仅由索引身份段派生），与 `manifest.json` 对齐 |
| `index_dirname` | str | 实际服务的索引目录名（`{method}_{embed}_{hash8}`） |
| `mode` | str | 检索模式：`vector` \| `bm25` \| `hybrid` \| `hybrid_rerank` |
| `top_k` | int | 本次请求的 Top-K |
| `question` | str | 查询文本（原样记录，不截断） |
| `latency_ms` | float | 检索耗时（从进入 `retrieve` 到结果就绪；不含日志写盘） |
| `result_count` | int | 实际返回条数。bm25 过滤零词面重叠候选后**可能小于 top_k；`0` 即「知识库无词面证据」信号**，下游据此走拒答路径 |
| `results` | array | 富引用数组（含正文，见下），按 rank 升序 |

`results[]` 元素（与 `retrieval/retriever.py` 富引用字段一致）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `node_id` | str | 知识节点 ID |
| `text` | str | chunk 正文（完整，不截断） |
| `source_id` | str | 来源注册 id（如 `user_manual`） |
| `source_name` | str | 来源文件名（如 `ZRDDS用户手册.pdf`） |
| `section` | str | 章节路径 |
| `page_print` | int \| null | 印刷页码（= 物理页 − 6） |
| `page_physical` | int \| null | 物理页码（1 基，与阅读器一致） |
| `score` | float | 相关性分数，**量纲随 mode 变**（见 §5） |

`filters` 非空时（`cfg.retrieval.filters` 配置了元数据过滤）追加可选字段
`filters`（object），便于复现「为什么某些块被排除」。

## 4. 示例记录

向量命中一例（`struct_v1`）：

```json
{"ts": "2026-09-08T10:30:01+0800", "request_id": "req_8f3a2c", "experiment": "struct_v1",
 "config_hash8": "0a7830b7", "index_dirname": "struct_bge-m3_0a7830b7",
 "mode": "vector", "top_k": 5, "question": "如何创建 DataWriter？", "latency_ms": 12.4,
 "result_count": 5, "results": [
  {"node_id": "struct_v1_s_s_s_s_s_PART_2_基本概念_第9章_订阅数据_9_3_DataReader_9_3_3_设置DataReader的QoS策略_9_3_3_1_创建DataReader时配置QoS策略_00000",
   "text": "9.3.3.1 创建DataReader 时配置QoS 策略 …（正文完整，此处省略）",
   "source_id": "user_manual", "source_name": "ZRDDS用户手册.pdf",
   "section": "PART 2 基本概念 / 第9章 订阅数据 / 9.3 DataReader / 9.3.3 设置DataReader的QoS策略 / 9.3.3.1 创建DataReader时配置QoS策略",
   "page_print": 101, "page_physical": 107, "score": 0.6234},
  {"node_id": "…", "text": "…", "source_id": "user_manual", "source_name": "ZRDDS用户手册.pdf",
   "section": "…", "page_print": 95, "page_physical": 101, "score": 0.5987}
 ]}
```

bm25 无证据一例（`struct_bm25`）：

```json
{"ts": "2026-09-08T10:31:22+0800", "request_id": "req_9c04d1", "experiment": "struct_bm25",
 "config_hash8": "677d777f", "index_dirname": "struct_bge-m3_677d777f",
 "mode": "bm25", "top_k": 5, "question": "如何配置 ROS2 节点？", "latency_ms": 3.1,
 "result_count": 0, "results": []}
```


