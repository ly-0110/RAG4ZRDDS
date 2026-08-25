.PHONY: setup ingest index experiment serve inspect help

CFG ?= configs/experiments/example_v1.yaml

help:
	@echo "targets: setup | ingest/index/experiment CFG=... | serve | inspect"

setup:
	python -m venv .venv
	.venv/Scripts/python -m pip install -U pip
	.venv/Scripts/python -m pip install -r requirements.txt
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
