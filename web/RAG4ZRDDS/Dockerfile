# 前端容器：Node 构建 → nginx 托管静态产物并反代后端（含 SSE）
#
# 构建上下文 = 本目录；根目录 .dockerignore 不适用于此（Docker 只读上下文根部的 .dockerignore）。
#
# 构建与起停由根目录 docker-compose.yml 统一驱动：
#   docker compose up -d --build
#
# 说明：前端全部 API 调用走相对路径（/query /sources /nodes /documents /healthz /feedback），
# 生产形态下由本镜像内的 nginx 反代到后端容器，故构建期无需注入后端地址。

# ---- 构建阶段 ----
# node 24 对齐本机实测通过的版本（package-lock 的 engines 要求 ^22.13.0 || >=24.0.0）
FROM node:24-alpine AS build

WORKDIR /app

ARG NPM_REGISTRY=https://registry.npmmirror.com

# Cypress 浏览器二进制在容器里用不到（会从 download.cypress.io 拉 100MB+，拖慢且易失败）；
# 仅跳过二进制下载，其余包的安装脚本照常执行（esbuild/rollup 的原生依赖需要）。
ENV CYPRESS_INSTALL_BINARY=0

COPY package.json package-lock.json ./
RUN npm config set registry "$NPM_REGISTRY" \
 && npm ci

COPY . .
RUN npm run build

# ---- 运行阶段 ----
FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
