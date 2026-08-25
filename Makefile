.PHONY: setup ingest index experiment serve inspect help

CFG ?= configs/experiments/example_v1.yaml
APP_HOST ?= 127.0.0.1
APP_PORT ?= 8000
# pip 国内镜像源（团队约定默认走国内源；可按网络环境替换为阿里云等）
PIP_INDEX ?= https://pypi.tuna.tsinghua.edu.cn/simple

help:
	@echo "targets: setup | ingest/index/experiment CFG=... | serve | inspect"

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

serve:
	uvicorn server.main:app --host $(APP_HOST) --port $(APP_PORT)

inspect:
	python scripts/inspect_nodes.py
