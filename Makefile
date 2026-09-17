.PHONY: setup ingest index experiment answer-eval abstention manual-review regression audit test serve inspect mcp smoke-mcp help docker-build docker-serve docker-stop docker-logs docker-ps docker-smoke docker-clean

CFG ?= configs/experiments/struct_v1.yaml
ANSWER_CFG ?= configs/experiments/final_v1.yaml
SAMPLE ?=
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
	@echo "targets: setup | ingest/index/experiment CFG=... | answer-eval/abstention/manual-review | regression REG_ARGS='--only a,b' | test | serve | inspect | mcp | smoke-mcp | docker-build/docker-serve/docker-smoke/docker-stop"
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

# 回答侧评测（逐题生成 + judges 判分）。SAMPLE=30 只评前 30 题冒烟；
# 全量终跑 = make experiment CFG=$(ANSWER_CFG)（见 docs/reliability-report.md）
answer-eval:
	$(PY) scripts/run_experiment.py --config $(ANSWER_CFG) $(if $(SAMPLE),--sample $(SAMPLE))

# 20 题「不存在信息」拒答专项（全部合格则退出码 0）
abstention:
	$(PY) evaluation/runners/abstention_eval.py --config $(ANSWER_CFG)

# 人工抽检 30 题——生成六问检查清单 markdown 供评审人签署
manual-review:
	$(PY) scripts/sample_manual_review.py

# 回归机制：变更 → 一键跑相关实验 → 与历史/基准报告比对 → 退出码判定
regression:
	$(PY) scripts/run_regression.py $(REG_ARGS)

# 标注真值核对（§6.1/§9.3）：判据只来自 A 的产物；它是 regression --with-metrics 的前置门禁
audit:
	$(PY) scripts/audit_annotations.py --out-prefix evaluation/reports/annotation_audit

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

# ===== Docker 打包（交付形态）=====
# 镜像只装"代码 + 依赖"；模型权重（bge-m3 在 LlamaIndex 缓存、精排在 HF 缓存）、六套索引、
# HTML 原始快照全部经 docker-compose.yml 挂载复用宿主，因此重建镜像不需要重新下载模型或重建索引。
# 与 compose 同名变量在此 ?= 并 export：既让 compose 取到值，也让 `make docker-serve WEB_PORT=…`
# 这类命令行覆盖生效（冒烟脚本据此自动对齐端口，不必手填 --base）。
WEB_PORT ?= 5173
BACKEND_PORT ?= 8000
export WEB_PORT BACKEND_PORT
# 权重缓存位置覆盖（默认由 compose 按 Windows 用户目录推导；非 Windows 或缓存在他处时设这两个）
export HF_CACHE_HOST LLAMA_INDEX_CACHE_HOST
# mock 形态开关（默认 live，见 compose）；HF_OFFLINE=0 允许联网补权重
export CONTAINER_RAG_MODE HF_OFFLINE
# 镜像目标：selfcontained（默认，权重烘进镜像）/ slim（不带权重，首次启动下载）
IMAGE_TARGET ?= selfcontained
export IMAGE_TARGET
# MOUNTS=1 叠加开发形态覆盖文件：知识库与权重改读宿主，改完 make ingest/index 立即生效、无需重建镜像
MOUNTS ?=
COMPOSE := docker compose -f docker-compose.yml $(if $(MOUNTS),-f docker-compose.mounts.yml,)

docker-build:
	$(COMPOSE) build

docker-serve:
	$(COMPOSE) up -d --build
	@echo "frontend: http://127.0.0.1:$(WEB_PORT)    backend: http://127.0.0.1:$(BACKEND_PORT)/healthz"

docker-stop:
	$(COMPOSE) down

docker-logs:
	$(COMPOSE) logs -f backend

docker-ps:
	$(COMPOSE) ps

# 容器形态冒烟：健康检查 + 前端反代 + 真实问答（SSE，经 nginx）。需先 make docker-serve
docker-smoke:
	$(PY) scripts/smoke_docker.py --base http://127.0.0.1:$(WEB_PORT)

# 停栈并删除本机构建的镜像（不动宿主目录与权重缓存）
docker-clean:
	$(COMPOSE) down --rmi local
