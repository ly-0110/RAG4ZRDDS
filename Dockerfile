# RAG4ZRDDS 后端服务镜像 —— 自包含交付形态
#
# 口径：镜像内自带全部运行要素，换台机器 / 换系统只要装了 Docker 就能起：
#   ① 代码与依赖  ② 统一 Node 产物（data/processed）  ③ 六套索引（indexes/）
#   ④ PDF 与 HTML 原文（data/raw）  ⑤ 模型权重缓存（bge-m3 + bge-reranker-v2-m3）
#
# 留在镜像外的只有两类，且都不是"运行要素"：
#   * LLM 后端 —— 天然是外部服务（云端 API 或宿主上的 Ollama），靠 .env 指向；
#   * logs/    —— 运行期输出，落宿主便于回查，容器重建不丢。
#
# 分层（自下而上、越靠上越常变；重建只重跑变化的那层）：
#   1 依赖 → 2 代码 → 3 知识库（Node 产物 / 索引 / 原文）→ 4 权重（4.4GB，置底）
# 因此改代码重建只多跑第 2 层，知识库与权重层直接命中缓存。
#
# 构建（默认目标 = selfcontained）：
#   docker compose build
# 仅用 docker 时需显式给出权重来源（compose 用 additional_contexts 传的正是这两个）：
#   docker build --build-context llama-cache="<本机 LlamaIndex 缓存>" \
#                --build-context hf-cache="<本机 HF 缓存的 hub 目录>" \
#                -t rag4zrdds-backend:latest .
#
# 两个目标：
#   selfcontained（默认，文件末尾）—— 权重烘进镜像，任何机器开箱即用
#   slim                          —— 不带权重（镜像小 4.4GB），首次启动联网下载进命名卷

# ==================== 1. 依赖层 ====================
FROM python:3.13-slim AS base

# 国内 pip 源（团队约定）；海外网络可 --build-arg PIP_INDEX=https://pypi.org/simple
ARG PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
# PyTorch CPU 专用源：PyPI 默认轮子会拖入 CUDA/nvidia-* 依赖（+2~3GB），
# 本项目实测为 CPU 推理，装 CPU 轮子即可。版本仍由 requirements.txt 锁定。
ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/root/.cache/huggingface \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

WORKDIR /app

COPY requirements.txt ./
# torch 先行（CPU 轮子，版本 2.13.0+cpu 满足 requirements 的 ==2.13.0），
# 随后整份 requirements 安装时该项已满足、不会从 PyPI 重装带 CUDA 的版本。
RUN pip install --no-cache-dir --upgrade pip -i "$PIP_INDEX" \
 && pip install --no-cache-dir torch==2.13.0 --index-url "$TORCH_INDEX" \
 && pip install --no-cache-dir -r requirements.txt -i "$PIP_INDEX"

# 依赖装完再补环境变量：ENV 写在 pip 之上会改掉该层的父层哈希，导致整层缓存失效
# （实测踩过——网络差时重装依赖要 30 分钟以上）。新增 ENV 一律加在这个位置之后。
ENV LLAMA_INDEX_CACHE_DIR=/root/.cache/llama_index

# ==================== 2. 代码层 + 3. 知识库层 ====================
# 知识库（data/processed、indexes、data/raw）随 `COPY . .` 一同进入：构建上下文不再排除它们。
# 构建期把自带要素清点一遍——资产漏带在这里就能看见，而不是等演示时才发现。
FROM base AS app
COPY . .
RUN python -c "from pathlib import Path; \
n=lambda p,s: len(list(p.glob(s))); \
print('[build] Node 产物 %d 个 | 索引 %d 套 | 原文 %d 个文件' % (n(Path('data/processed'),'*.jsonl'), n(Path('indexes'),'*/'), n(Path('data/raw'),'**/*')))"

# ==================== 目标 A：精简（不带权重）====================
# 首次启动由容器自行下载（需可直连 huggingface.co），落点必须是命名卷，否则容器重建即丢。
# compose 侧用法见 README「精简形态」：IMAGE_TARGET=slim + HF_OFFLINE=0 + 两个命名卷。
FROM app AS slim
ENV HF_HUB_OFFLINE=0 \
    TRANSFORMERS_OFFLINE=0
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ==================== 目标 B：自包含（默认）====================
# 权重来源两个 build context（由 compose 的 additional_contexts 提供）：
#   llama-cache → 本机 LlamaIndex 缓存（embedding 权重在此：LlamaIndex 会显式传自己的 cache_dir）
#   hf-cache    → 本机 HF 缓存的 hub 目录（精排权重在此：CrossEncoder 走 HF 默认缓存）
FROM app AS selfcontained
COPY --from=llama-cache models--BAAI--bge-m3 /root/.cache/llama_index/models--BAAI--bge-m3
COPY --from=hf-cache models--BAAI--bge-reranker-v2-m3 /root/.cache/huggingface/hub/models--BAAI--bge-reranker-v2-m3
# 权重自检：快照条目是指向 blobs/ 的符号链接，若拷贝过程未保留会成坏链——这里当场验证可读性。
RUN python -c "from pathlib import Path; \
m=Path('/root/.cache/llama_index/models--BAAI--bge-m3/snapshots'); \
r=Path('/root/.cache/huggingface/hub/models--BAAI--bge-reranker-v2-m3/snapshots'); \
emb=[p for p in m.glob('*/pytorch_model.bin')] + [p for p in m.glob('*/model.safetensors')]; \
rr=[p for p in r.glob('*/model.safetensors')] + [p for p in r.glob('*/pytorch_model.bin')]; \
assert emb and rr, '权重未随镜像落入（快照符号链接可能未被保留）'; \
print('[build] 权重自检通过：embedding %d 项 / reranker %d 项，合计 %.2f GB' \
      % (len(emb), len(rr), sum(p.stat().st_size for p in emb+rr)/2**30))"
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
