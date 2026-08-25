# 实验配置说明（schema v1）

> 本目录存放所有实验配置。格式由成员 D 维护；其他人**新增实验 = 复制 `example_v1.yaml` → 改名 → 填自己负责区块的参数**。

## 一、快速上手：新建一个实验

```bash
# 1. 复制模板，改名为你的实验名（这个名字就是实验 ID）
cp configs/experiments/example_v1.yaml configs/experiments/semantic_v1.yaml

# 2. 编辑新文件：把 experiment.name 改成 semantic_v1（必须与文件名一致），再改你要试的参数

# 3. 自检，确认配置合法、看看会生成哪些文件
python scripts/experiment_config.py configs/experiments/semantic_v1.yaml
```

三条基本规则：

1. **文件名就是实验的名字。** 之后生成的分块结果、索引、报告都用它命名；`experiment.name` 与文件名不一致会被校验器拦下。
2. **写错字段当场报错，不会带病运行。** 固定字段的拼写和取值范围都会被检查，拼错了会提示相近的正确拼写（如写了 `topk` 会提示 `top_k`）。各区块里 `params:` 下面的内容不检查，原样传给该负责人写的代码。
3. **密钥绝不写进 yaml。** 配置文件会提交到 Git；需要密钥的地方只填环境变量的**名字**（如 `api_key_env: EMBED_API_KEY`），真正的值放在 `.env` 里（不入 Git）。

两条附带约定：

- **不做模板继承。** 想试新实验就复制一份改几行，不要造 include / override 机制。
- **固定字段的增删只由 D 做**（同时递增 `schema_version`）；各 Owner 在自己区块的 `params:` 里加参数随时可以。

## 二、example_v1.yaml 参数逐项说明

> 每个表回答两个问题：这个参数管什么、值怎么定。没提到的默认值不用动。

### experiment —— 这次实验叫什么

| 参数 | 作用 | 怎么填 |
|---|---|---|
| `name` | 实验 ID，产物命名全靠它 | 复制模板后改成与文件名相同的名字 |
| `description` | 一句话说明实验目的 | 用大白话写清楚"这次想验证什么"，报告会引用 |
| `stage` | 实验性质标记 | `baseline`=基线 / `ablation`=对比实验 / `regression`=回归验证 / `product`=当前线上用的配置 |

### sources —— 知识库用哪些资料

| 参数 | 作用 | 怎么填 |
|---|---|---|
| `id` | 给来源起的短名 | 会出现在答案的来源标注里，如 `user_manual` |
| `type` | 资料类型 | `pdf` 或 `html` |
| `path` | 文件位置（相对仓库根） | 填完确认 `data/raw/` 下确实存在该文件 |
| `version` | 资料版本号 | 写资料的实际版本（如 `"2.4"`）；将来同主题多版本并存时，检索可按它过滤 |
| `url` | HTML 来源的网址 | `type: html` 时必填（引用要能点击跳转）；PDF 不填 |

### ingest —— 清洗阶段怎么跑

| 参数 | 作用 | 怎么填 |
|---|---|---|
| `cleaned_output` | 逐页清洗结果的输出路径 | 默认即可 |
| `quality_check` | 是否顺带跑数据质量检查 | 保持 `true`；解析出问题时先看它的报告 |

### chunking —— 长文本怎么切成检索用的小块

分块的目的：把整本手册切成大小合适、边界清晰的片段，检索时只取最相关的几段给模型。

| 参数 | 作用 | 怎么填 |
|---|---|---|
| `method` | 切块方案 | `struct`=按文档章节结构切（主方案）/ `semantic`=按语义相似度切（对照组）/ `hybrid`=先按结构切、超大段再语义二次切 / `fixed`=固定长度（仅作对照） |
| `version` | 方案内部版本号 | 第一版写 `v1`；切块逻辑变了就升 `v2`，旧结果不会被覆盖 |
| `params.unit_level` | 多大的章节算一个块 | `3` = 以三级节为单位。手册实测：127 个三级节长度中位数约 2263 字符，多数天然合适 |
| `params.oversize_threshold` | 超过多少字符算"超大节"、需要继续下切 | 单位是字符。手册有 50 个三级节超 2500 字符，所以建议 2500 附近 |
| `params.sub_split` | 超大节怎么继续切小 | `heading`=沿四、五级子节标题切 / `semantic`=按语义切（hybrid 方案用）/ `none`=不切 |
| `params.atomic_blocks` | 哪些内容不许从中间切断 | 表格和代码被拦腰切断就没法读了，保持 `[table, code]` |

### embedding —— 把文字变成可计算向量的模型

| 参数 | 作用 | 怎么填 |
|---|---|---|
| `provider` | 模型从哪来 | `local`=本地运行 / `api`=调用远程服务 |
| `model` | 模型名 | 中文技术文档场景常用 `bge-m3`；换模型 = 新建一个实验来对比 |
| `batch_size` | 每批处理多少条文本 | 报内存不足就调小 |
| `device` | 本地推理用什么设备 | `cpu` 或 `cuda` |
| `api_key_env` | 密钥的环境变量名 | `provider: api` 时必填；**只写变量名，不写密钥本身** |

### index —— 向量索引存哪、怎么比相似度

| 参数 | 作用 | 怎么填 |
|---|---|---|
| `backend` | 向量库软件 | `chroma` 或 `faiss`，本地原型二选一 |
| `metric` | 相似度算法 | 一般 `cosine`，不用动 |

索引目录名自动生成：`{方案}_{模型}_{hash8}`，例如 `struct_bge-m3_88e38bf8`。hash8 是这份配置内容的指纹前 8 位——**配置不变则目录名不变**（重复重建覆盖同一目录，旧目录保留可回退）；**配置一改就是新目录**，不会污染旧索引。

### retrieval —— 检索时怎么取片段

| 参数 | 作用 | 怎么填 |
|---|---|---|
| `mode` | 检索方式 | `vector`=向量语义匹配 / `bm25`=关键词精确匹配（适合 API 名、错误码）/ `hybrid`=两者融合 / `hybrid_rerank`=融合后再用模型精排 |
| `top_k` | 最终取几个片段交给生成环节 | 先用 `5`。注意：对比不同实验时各配置此项必须一致，否则结果不可比 |
| `candidate_top_k` | 精排前先粗取多少条 | 仅 `hybrid_rerank` 生效，必须 ≥ top_k（典型做法：粗取 30 → 精排留 5） |
| `rerank_model` | 精排用的模型名 | `mode: hybrid_rerank` 时必填 |
| `filters` | 检索时的过滤条件 | 例如只搜 v2.4 的内容：`{version: "2.4"}` |
| `source_priority` | 来源优先顺序 | 按 id 从高到低列，如 `[api_ref, user_manual]`；空 = 不分先后 |
| `params` | 本域自由参数区 | BM25 的 k1/b、混合权重等，由 B 决定 |

### generation —— 回答怎么生成

| 参数 | 作用 | 怎么填 |
|---|---|---|
| `enabled` | 评测是否包含生成环节 | 第一周 `false`（只测检索准不准）；第二周起 `true` |
| `prompt_version` | 使用哪一版提示词 | 对应 `generation/prompts/` 下的版本号 |
| `llm_env_prefix` | 从 `.env` 读哪组 LLM 配置 | 默认 `LLM_`（即读 LLM_MODEL / LLM_API_KEY 等），一般不动 |

### evaluation —— 拿什么题目、按什么标准打分

| 参数 | 作用 | 怎么填 |
|---|---|---|
| `dataset` | 问题集路径 | E 维护的 jsonl 文件 |
| `expected_sources` | 每题的标准答案出处 | 用来判断"该命中的内容有没有被检索到" |
| `retrieval_metrics` | 检索质量指标 | 格式为 名称@取几条：`hit_rate@5`=前5条里命中过没有、`mrr@5`=正确结果排得有多靠前；也支持 `precision@K` / `recall@K` |
| `response_metrics` | 回答质量指标 | 第二周起启用，如 `faithfulness`（答案是否忠于原文） |
| `sample_size` | 这次跑多少题 | 空=全部；联调调试时填 `10` 省时间 |

### report —— 结果存在哪

| 参数 | 作用 | 怎么填 |
|---|---|---|
| `dir` | 报告输出目录 | 默认 `evaluation/reports/`（入 Git，作为回归对比依据） |
| `compare_baseline` | 和哪份历史报告做对比 | 填报告文件名如 `baseline.json`；不填=只记录不比较 |

## 三、自检命令会告诉你什么

```bash
python scripts/experiment_config.py configs/experiments/<你的实验>.yaml
```

- **通过** → 打印实验 ID 和三个产物的落地路径（分块结果 / 索引目录 / 报告文件），尚未生成的路径标注 `[尚无——待生成]`
- **失败** → 逐条列出错误位置、原因和拼写建议

ingest / build_index / run_experiment 三个脚本加载配置都走同一个入口，在这里能通过，后面就不会再因配置问题中断。

## 四、产物命名规则（速查）

| 产物 | 规则 | 示例（假设实验叫 `semantic_v1`） |
|---|---|---|
| 分块结果 | `data/processed/{chunking.method}_{chunking.version}.jsonl` | `semantic_v1.jsonl` |
| 索引目录 | `indexes/{method}_{embedding.model}_{hash8}` | `semantic_bge-m3_7c1d22aa` |
| 报告 | `{report.dir}/{experiment.name}.json` | `evaluation/reports/semantic_v1.json` |

## 五、分工边界

| 谁 | 可以做什么 |
|---|---|
| A / B / C / E | 复制模板新建实验；修改自己负责区块的参数与 `params:` 内容 |
| D | 增删固定字段、调整校验规则（须递增 `schema_version` 并同步更新本文档与既有配置） |

发现字段不够用、或对某个参数含义有疑问 → 直接找 D，不要自行新增固定字段。
