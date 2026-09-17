# RAG4ZRDDS 后端服务镜像：FastAPI（REST + SSE）+ MCP Server
#
# 口径：镜像只装"代码 + 依赖"。大资产一律经 docker-compose.yml 挂载复用宿主：
#   bge-m3 权重（约 2.2GB）、六套向量/BM25 索引、HTML 原始快照。
# 因此本镜像不含任何模型权重与索引，干净机器构建后带上这三样即可运行。
#
# 构建：docker build -t rag4zrdds-backend:latest .
# 起停：docker compose up -d --build
#
# 依赖层与代码层分离：改代码不触发重装依赖，requirements.txt 变了才重建该层。

FROM python:3.13-slim

# 国内 pip 源（团队约定）；海外网络可 --build-arg PIP_INDEX=https://pypi.org/simple
ARG PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
# PyTorch CPU 专用源：PyPI 默认轮子会拖入 CUDA/nvidia-* 依赖（+2~3GB），
# 本项目本机实测为 CPU 推理，装 CPU 轮子即可。版本仍由 requirements.txt 锁定。
ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/root/.cache/huggingface \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

WORKDIR /app

# ---- 依赖层 ----
COPY requirements.txt ./
# torch 先行（CPU 轮子，版本 2.13.0+cpu 满足 requirements 的 ==2.13.0），
# 随后整份 requirements 安装时该项已满足、不会从 PyPI 重装带 CUDA 的版本。
RUN pip install --no-cache-dir --upgrade pip -i "$PIP_INDEX" \
 && pip install --no-cache-dir torch==2.13.0 --index-url "$TORCH_INDEX" \
 && pip install --no-cache-dir -r requirements.txt -i "$PIP_INDEX"

# ---- 代码层 ----
COPY . .

EXPOSE 8000

# 解释器与宿主一致（Python 3.13.2 / CPU）；live 模式启动期完成 bge-m3 预热后才开始服务
CMD ["python", "-m", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
