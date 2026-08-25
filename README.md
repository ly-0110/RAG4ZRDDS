# RAG4ZRDDS

**ZRDDS 产品知识库构建与开发调试问答系统** —— 以《ZRDDS用户手册.pdf》为第一阶段唯一知识源的最小可评价 RAG 系统。

## 快速开始（第一周脚本落地后生效）

```bash
cp .env.example .env      # 填写密钥
make setup                # 建环境并安装依赖
make ingest  CFG=configs/experiments/example_v1.yaml
make index   CFG=configs/experiments/example_v1.yaml
make serve                # 启动 API
```

## 文档

- 计划与规范（唯一权威）：[`product_rag_implementation_guide.md`](./product_rag_implementation_guide.md)
- 工作区记忆：[`AGENTS.md`](./AGENTS.md)

## 目录速览

| 目录 | Owner | 说明 |
|---|---|---|
| `data_pipeline/` | A | 解析/清洗/章节树/三方案 chunker |
| `retrieval/` | B | Embedding/索引/BM25/Hybrid/Reranker |
| `generation/` | C | Prompt/Context/Citation |
| `server/` · `scripts/` | D | API、OpenAI 兼容门面、MCP、实验流水线 |
| `web/` | E | 问答界面（自研或开源改造）|
| `evaluation/` | E 数据集 / C 判分 / D 报告 | 评测体系 |
| `configs/experiments/` | D 定格式 | 一次实验一个 yaml |
| `data/raw/` · `indexes/` | — | 大文件，不入 Git |

## 当前状态

脚手架阶段：目录结构与计划文档已就绪，第一周实现数据管线与最小 RAG（见指南 §5）。
