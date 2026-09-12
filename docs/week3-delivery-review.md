# 第三周交付审查记录（成员 D）

> **v0.1（2026-09-08）**：首版，覆盖 E 的 PR#22（`b871bf8`，"修复问题集格式与本地回归验证"，merge `53e8099`）。
> 审查人：成员 D。审查方法沿用《week2-delivery-review》四步：基线核对 → pytest 全套 → 契约/格式核对 → 内容真值抽查。
> 同步状态：`feature/server-platform` 已 merge origin/develop（`96ae6f9`）零冲突，pytest **178/178** 绿。

---

## 1. 总览

| 交付物 | 结论 |
|---|---|
| `questions.jsonl`（120 题 JSONL） | ✅ 格式达标（PR#15 违约修复）；题集大改写待 C 口径会签 |
| `expected_sources.jsonl`（120 条标注分文件） | ❌ **P0：标注依据为检索 top-1 （导致循环论证），不可用作评测真值** |
| `annotation_audit.jsonl` | ❌ "审计"= 与索引核对，非对 PDF 核对 |
| `scripts/improve_questions*.py`、`fix_questions_format.py` | ❌ **P0：假验证脚本**（页码校验上限 1000、"吻合率"是模拟值） |
| `scripts/build_index.py` / `retrieval/embeddings.py` / `.env.example` 改动 | ❌ **P1：跨域未会签环境私货**（本次已由 D 清理，见 §4） |
| `web/RAG4ZRDDS/src/components/CitationsCard.vue`（+127 行） | ✅ E 域内，视觉升级，7 字段契约未破坏 |
| `web/RAG4ZRDDS/docs/` 过程文档 10 篇 | ✅ 记录详尽；第三周前端方向 = CitationsCard 视觉增强，仍自研轻量页路线，**无 OpenAI 兼容/MCP 需求** |


## 2. P0-1 标注循环论证（阻断验收项 1/2/3）

**实证方法**：对 `expected_sources.jsonl` 全部 120 条与 `evaluation/reports/struct_v1.json`（PR#22 入库版）的检索明细逐条比对。

- **120/120 条标注页码 = 检索 top-1 页码**，`annotation_audit.jsonl` 的 `retrieval_page_print` 与标注页逐条相同。
- 即：标注是从检索结果**反推**的，`hit_rate@5=1.0 / mrr@5=1.0` 是构造产物，不是评测结果——**检索缺陷被固化成"标准答案"再给检索打满分，导致评测丧失发现缺陷的能力，评测无任何意义。**。



### 给 E 的整改路径

1. 逐题打开 PDF 对到**页眉印刷数字**，标注"答案实际所在页"；区分"策略定义页 / 操作页"口径（该口径分歧请与 C 会签定稿）。
2. 禁止用检索/实验报告反推标注；`improve_questions*.py` 的"吻合率（模拟）"不可再作验证依据。
3. 自查工具：D 的真值核对脚本（对产物按 keyword 反查页码 + 已知审计锚点）；提交前先自查再提 PR。


## 3. P0-2 假验证脚本

- `scripts/improve_questions.py`："真值抽查吻合率（**模拟**）" = 标注数 ÷ 题数——不是任何意义上的真值核对。
- 页码合理性校验上限为 **1000**：脚本硬编码的 309/316 等页码（**超出手册印刷页最大 289、物理页最大 295**）全部判"合理"。
- 仍引用旧格式 `questions.json`（PR#15 违约格式），与本次交付的 `questions.jsonl` 脱节。
- 处置：**作废重做或删除**（E 域，待 E 答复）；在真值标注完成前，任何"验证通过"结论不采信。

## 4. P1 跨域环境私货（b871bf8 混入，**本次已清理**）

E 在 QA 提交中未经会签修改了三个跨域文件，给 embedding 环境塞入镜像默认值与个人机器路径：

| 文件（域） | E 的改动 | 问题 |
|---|---|---|
| `scripts/build_index.py`（D） | `main()` 默认设 `HF_ENDPOINT=https://nexus.aliyun.com/` | **该域名不是 HF 镜像**（Maven 仓库域）；与本机实测相悖（见 §5）；该文件 docstring 自述"勿设 HF_ENDPOINT"自打脸 |
| `retrieval/embeddings.py`（B） | 默认设 `HF_ENDPOINT` 清华镜像；新增 `BGE_M3_MODEL_PATH` env；`Path.home()/Desktop/bge-m3` 硬编码兜底 | 清华镜像同本机实测相悖；Desktop 路径是 E 个人机器布局，对他人是死路径 |
| `.env.example`（D） | 新增 `BGE_M3_MODEL_PATH` + E 个人路径示例（`C:\Users\55386\...`） | 环境私货入模板 |

**处置（2026-09-08，用户授权 D 代修）**：三文件已恢复到 PR#22 改动前的会签状态——`embeddings.py`、`build_index.py` 与基线 `472ff70` 逐字节一致；`.env.example` 仅保留 D 自己的 LOG_DIR 注释。pytest 178/178 + `build_index --list` 冒烟通过。随下次 D 的 PR 入库。**若 E 本机确需本地模型目录，请在自己的 `.env`（不入 Git）解决，勿改仓库文件。**

## 5. 正确的镜像/网络配置方式（本机实测，团队参考）
注意：建议完全不要在业务代码里设置环境变量--每个人的情况不同，都需要进行自己的设置，那么就不能在会同步到git的文件中设置。
本机（Windows + huggingface_hub 1.29）实测结论，**任何成员不得在仓库代码/脚本中默认设置 `HF_ENDPOINT`**：

1. **默认直连**：`huggingface.co` 直连可用（本机下载 bge-m3 权重即直连完成）。清华源似乎已失效，走清华镜像拉文件**必失败**（`FileMetadataError`）——设 `HF_ENDPOINT` 反而弄巧成拙。
2. **模型已缓存时**（权重在 `~/.cache/huggingface/`），务必设：
   ```bash
   HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
   ```
   否则 SentenceTransformer 初始化会对每个 config 文件做 5 次重试 HEAD，挂数分钟（`make experiment` 假死实录）。建议写进运行环境而非代码。
3. **本地已有模型目录**：放入仓库 `models/{model}`（如 `models/bge-m3`），解析顺序自动优先（`embeddings.py::_resolve_model`）；`models/` 不入 Git。
4. **确需镜像的场景**（如 CI 无直连）：在**运行环境变量**中设置，不改代码；且所选域名必须是真实 HF 镜像（`hf-mirror.com`），`nexus.aliyun.com` 是 Maven 仓库域、`mirrors.tuna.tsinghua.edu.cn/huggingface.co` 根本不可用。
5. GitHub 资产下载慢/超时：release 资产前缀 `https://gh-proxy.com/` 断点续传（仅人工操作，不入脚本）。

## 6. P2 与遗留

- `questions.jsonl` 大改写（135 行 diff，题面/类型/难度变动）：问题集口径归 C 管，**需 C 会签确认**后再视为正式题集。
- X1/X2/X3 追认、B 补充约定 3 条 + B1 追认、C2~C5 反馈等既有会签事项不变（见 AGENTS.md 待办区）。

## 7. 结论

PR#22 **格式整改合格、前端改动合格；标注与验证脚本不合格，评测闭环在真值标注完成前不可用**。验收项现状：2 达成 / 2 部分 / 3 未达成（不变，E 标注阻塞继续）。

> 变更记录：v0.1（2026-09-08）首版。
