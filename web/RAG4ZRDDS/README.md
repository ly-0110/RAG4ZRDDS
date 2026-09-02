# RAG4ZRDDS 前端

## 启动步骤

### 1. 安装依赖（首次）

```bash
npm install --registry=https://registry.npmmirror.com
```

### 2. 启动后端服务

在另一个终端窗口运行：

```bash
make serve
# 或
uvicorn server.main:app --host 127.0.0.1 --port 8000
```

### 3. 启动前端开发服务器

```bash
npm run dev
```

浏览器打开 http://localhost:5173

## 常见问题

### Q: 提示"后端服务未启动"？

**原因：**
- 后端服务（`make serve`）没有运行
- 后端端口不是默认的 8000
- 环境变量 `RAG_BACKEND_URL` 配置错误

**解决方法：**

1. **确认后端已启动**：在另一个终端运行 `make serve`，看到类似输出：
   ```
   INFO:     Started server process [12345]
   INFO:     Waiting for application startup.
   INFO:     Application startup complete.
   ```

2. **检查端口**：访问 http://localhost:8000/healthz 应该返回 `{"status":"ok","mode":"mock"}`

3. **修改后端端口**（如果需要）：
   ```bash
   RAG_BACKEND_URL=http://127.0.0.1:9000 npm run dev
   ```

4. **检查 Makefile**：确保 `make serve` 命令正确配置

### Q: 如何启动 mock 模式？

直接运行 `make serve` 即可，不需要先运行 `make index`。

### Q: 如何启动 live 模式（真实检索）？

```bash
# 先建索引
make index

# 再启动后端
RAG_MODE=live make serve
```

## 架构说明

- 前端：Vue 3 + Vite，运行在 http://localhost:5173
- 后端：FastAPI，运行在 http://localhost:8000（默认）
- 代理配置：`vite.config.js` 中的 `server.proxy` 将 `/query`、`/sources`、`/healthz` 转发到后端
