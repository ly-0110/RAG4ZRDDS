.PHONY: setup ingest index experiment regression test serve inspect mcp smoke-mcp help

CFG ?= configs/experiments/struct_v1.yaml
REG_ARGS ?=
APP_HOST ?= 127.0.0.1
APP_PORT ?= 8000
# pip 国内镜像源（团队约定默认走国内源；可按网络环境替换为阿里云等）
PIP_INDEX ?= https://pypi.tuna.tsinghua.edu.cn/simple

help:
	@echo "targets: setup | ingest/index/experiment CFG=... | regression REG_ARGS='--only a,b' | test | serve | inspect | mcp | smoke-mcp"

setup:
	python -m venv .venv
	.venv/Scripts/python -m pip install -U pip -i $(PIP_INDEX)
	.venv/Scripts/python -m pip install -r requirements.txt -i $(PIP_INDEX)
	@echo ready: copy .env.example to .env and fill keys

ingest:
	python scripts/ingest.py --config $(CFG)

index:
	python scripts/build_index.py --config $(CFG)

experiment:
	python scripts/run_experiment.py --config $(CFG)

# 指南 §10 回归机制：变更 → 一键跑相关实验 → 与历史/基准报告比对 → 退出码判定
regression:
	python scripts/run_regression.py $(REG_ARGS)

test:
	python -m pytest tests/ -q

serve:
	uvicorn server.main:app --host $(APP_HOST) --port $(APP_PORT)

inspect:
	python scripts/inspect_nodes.py

mcp:
	python -m server.mcp_server

smoke-mcp:
	python scripts/smoke_mcp.py
