# 索引升级演练（指南 §7 任务 3 · 成员 D · v0.1）

验收口径：**全量重建 ≤ 30 分钟、旧版本可回切**。本文记录机制、标准流程、
实测计时与 HTML 接入（Week 3）后的容量预警；演练实测记录在 §5 持续追加。

## 1. 支撑机制盘点（已落地）

| 机制 | 落点 | 作用 |
|---|---|---|
| 索引目录名 `{method}_{embed}_{hash8}` | `experiment_config.index_dirname` | hash8 只由索引身份段派生（`chunking`/`embedding`/`index`/`retrieval(mode,params,filters)`）——改 generation/evaluation/report **不触发重建**（R5 修复）；多来源配置的来源集参与身份（Week 3） |
| 产物指纹 `nodes_file_sha12` | manifest + `run_experiment._ensure_index` 硬校验 | 复用索引前校验 Node 集内容（CRLF 归一化，R6 修复）——产物变了配置没变时拒绝静默复用 |
| `--list` 盘点 | `python scripts/build_index.py --list` | 列出全部索引目录、对应实验/配置 hash/mode/节点数/构建时间——回切换位前先盘点 |
| 幂等重建语义 | `retrieval.index.build_index` | 先删旧集合再写入；**同名（同 hash8）重建会覆盖旧索引**——重建前确认是否有回切需求 |
| `--fake-embed` 守卫 | `build_index` / `run_experiment` | 目标为真实索引时拒绝假嵌入覆盖；`--rebuild` 为显式强制 |

## 2. 全量重建标准流程

```bash
make ingest                       # raw → cleaned → processed（Node 集）
make index CFG=configs/experiments/<实验>.yaml     # 按配置建索引（缺失自建/存在复用）
# 或一步到位（索引缺失时自动建）：
make experiment CFG=configs/experiments/<实验>.yaml
```

时长基线：真实 bge-m3 CPU 全量编码是大头（见 §3）；bm25 索引秒级（0.3s/301 节点）。

## 3. 实测计时（本机 CPU · Ryzen 7 9700X · bge-m3）

| 索引 | 节点数 | 实测耗时 | 日期 |
|---|---|---|---|
| struct（vector） | 301 | **468s（≈7.8 min）** | 2026-09-07 |
| struct（bm25） | 301 | 0.3s | 2026-09-07 |
| semantic（vector） | 1059 | **528.8s（≈8.8 min）** | 2026-09-07 |
| hybrid（vector） | 906 | **1176.5s（≈19.6 min）** | 2026-09-07 |

## 4. 旧版本回切演练

前提：旧索引目录仍在（不同 hash8 的目录互不覆盖）。

```bash
# ① 盘点：确认旧索引目录与 manifest 完好
python scripts/build_index.py --list

# ② 换位：把服务/实验配置指回旧版本对应的实验 yaml
#    （RAG_EXPERIMENT_CONFIG 环境变量或 make serve 前的 CFG）
RAG_EXPERIMENT_CONFIG=configs/experiments/struct_v1.yaml make serve

# ③ 验证：/healthz 报 mode 与实验名；发起一次已知查询核对 Citation 页码
#    （基线问法：DurabilityQosPolicy → 印刷 127 / 物理 133）
```

**风险与红线**：

- 同 hash8 的重建会**覆盖**旧索引目录——若需保留"升级前"版本，重建前把旧目录
  改名备份（目录名含 hash8 与集合名绑定，改名后仅作文件级备份，不可直接复用）。
- 回切后首查若报 `nodes_file_sha12` 校验失败，说明 Node 集已被新版本 ingest 重写——
  此时旧索引对应的产物版本已丢失，需 `git checkout` 对应产物提交后重建（演练时记录）。
- `--fake-embed` 产物不可用于服务（守卫已拒绝）；演练中误建可用目录删除清理。

## 5. 演练记录

| 日期 | 演练项 | 结果 | 记录人 |
|---|---|---|---|
| （待填） | 全量重建 struct（468s 基线复测） | — | D |
| （待填） | 回切 struct_v1 ↔ struct_bm25 + /healthz + Citation 核对 | — | D |
| 2026-09-12 | HTML 来源接入后全量重建计时（红线复核） | **struct_multisrc_v1（PDF 301 + HTML 1305 = 1606 节点）：1485.8s ≈ 24.8min，红线（30min）内**；索引 `struct_bge-m3_d57f695e`，120 题检索实验 17.7s（无标注只记明细，宁缺毋滥） | D |

## 6. HTML 接入后的 30 分钟红线预警（Week 3）

手册 PDF 295 页 → 301 chunk ≈ 468s；Doxygen HTML 436 页按 §7.3 结构化分块后，
预计新增数百~上千节点。**CPU bge-m3 线性外推：全库（PDF+HTML）向量全量重建
大概率超过 30 分钟红线**。应对选项（按侵入度排序）：

> **实测修正（2026-09-12）**：1606 节点全量重建实测 1485.8s ≈ 24.8min，**红线内**——
> 线性外推高估（bge-m3 编码吞吐随 batch 规模改善：301→1606 节点耗时仅 3.2× 而非 5.3×）。
> 短期内无需触发下列选项；接入第二 PDF 或节点数再翻倍时按 §5 记录复核。

1. **口径调整**：以实测数据（§5 记录）向团队申请把口径改为"单来源增量重建 ≤ 30 分钟"；
2. **增量嵌入**：Node 内容指纹未变的 chunk 复用既有向量，只编码新增/变更部分
   （需 `retrieval.index` 配合，属 B 域接缝，D 提需求）；
3. **提速手段**：调大 `embedding.batch_size`；或 `embedding.provider=api`（配置已支持，
   需 api_key_env，成本与密钥管理另议）；
4. **硬件**：本机无 CUDA（AMD 7900 GRE，torch 为 CPU 构建），GPU 提速不可用——
   不作为选项上报。

届时报实测数据（§5 演练记录）申请调口径或规划批量嵌入提速。
