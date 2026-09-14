.PHONY: setup ingest index experiment regression test serve inspect mcp smoke-mcp help

CFG ?= configs/experiments/struct_v1.yaml
REG_ARGS ?=
APP_HOST ?= 127.0.0.1
APP_PORT ?= 8000
VENV_DIR ?= .venv
# pip 国内镜像源（团队约定默认走国内源；可按网络环境替换为阿里云等）
PIP_INDEX ?= https://pypi.tuna.tsinghua.edu.cn/simple

# 解释器选择：$(VENV_DIR) 建好就用它，否则退回系统 python。
# 此前 setup 建了 .venv 而其余目标全用裸 python —— 干净环境照 README 走会用错解释器，
# "三行命令可跑"名不副实（venv 里装了依赖却没人用，系统 python 里可能什么都没有）。
ifeq ($(OS),Windows_NT)
  VENV_PY := $(VENV_DIR)/Scripts/python.exe
else
  VENV_PY := $(VENV_DIR)/bin/python
endif
PY := $(if $(wildcard $(VENV_PY)),$(VENV_PY),python)

help:
	@echo "targets: setup | ingest/index/experiment CFG=... | regression REG_ARGS='--only a,b' | test | serve | inspect | mcp | smoke-mcp"
	@echo "interpreter: $(PY)   (uses $(VENV_PY) when present, else system python)"
	@echo "first real index build: ~8 min for 301 nodes, ~25 min for 1606 nodes (bge-m3 on CPU)"
	@echo "if HF weights are cached, export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 to avoid network stalls"
	@echo "see README.md for the full three-command quick start"

setup:
	python -m venv $(VENV_DIR)
	$(VENV_PY) -m pip install -U pip -i $(PIP_INDEX)
	$(VENV_PY) -m pip install -r requirements.txt -i $(PIP_INDEX)
	@echo ready: copy .env.example to .env and fill keys

ingest:
	$(PY) scripts/ingest.py --config $(CFG)

index:
	$(PY) scripts/build_index.py --config $(CFG)

experiment:
	$(PY) scripts/run_experiment.py --config $(CFG)

# 指南 §10 回归机制：变更 → 一键跑相关实验 → 与历史/基准报告比对 → 退出码判定
regression:
	$(PY) scripts/run_regression.py $(REG_ARGS)

test:
	$(PY) -m pytest tests/ -q

serve:
	$(PY) -m uvicorn server.main:app --host $(APP_HOST) --port $(APP_PORT)

inspect:
	$(PY) scripts/inspect_nodes.py

mcp:
	$(PY) -m server.mcp_server

smoke-mcp:
	$(PY) scripts/smoke_mcp.py
