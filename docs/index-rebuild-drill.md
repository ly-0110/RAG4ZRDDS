# 索引升级演练

验收口径：**全量重建 ≤ 30 分钟、旧版本可回切**。本文记录机制、标准流程与实测计时。

## 1. 支撑机制盘点（已落地）

| 机制 | 落点 | 作用 |
|---|---|---|
| 索引目录名 `{method}_{embed}_{hash8}` | `experiment_config.index_dirname` | hash8 只由索引身份段派生（`chunking`/`embedding`/`index`/`retrieval(mode,params,filters)`）——改 generation/evaluation/report **不触发重建**；多来源配置的来源集参与身份 |
| 产物指纹 `nodes_file_sha12` | manifest + `run_experiment._ensure_index` 硬校验 | 复用索引前校验 Node 集内容（CRLF 归一化）——产物变了配置没变时拒绝静默复用 |
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

| 索引 | 节点数 | 实测耗时 |
|---|---|---|
| struct（vector） | 301 | **468s（≈7.8 min）** |
| struct（bm25） | 301 | 0.3s |
| semantic（vector） | 622 | **528.8s（≈8.8 min）** |
| hybrid（vector） | 906 | **1176.5s（≈19.6 min）** |
| 多来源 struct（vector） | 1638 | **1485.8s（≈24.8 min）** |
| 多来源 struct（bm25） | 1638 | 0.1s |

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

