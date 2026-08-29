# 前后端联调测试手册（web/ ↔ FastAPI）

> 维护人：成员 D。适用于 `web/RAG4ZRDDS`（Vue 3 + Vite）与 `server/`（FastAPI SSE）的手动联调。
> 2026-08-29 版：前端四处接线缺陷已修复并双模式实测通过，本手册即按修复后行为编写。

## 1. 架构与请求路径

```
浏览器 ──/query（相对路径）──▶ Vite dev server(:5173) ──代理──▶ FastAPI(:8000)
```

- 前端只发**相对路径**请求（`/query`、`/sources`、`/healthz`），由 `vite.config.js`
  的 `server.proxy` 转发到后端，避免跨域。后端端口非 8000 时用环境变量覆盖：
  `RAG_BACKEND_URL=http://127.0.0.1:9000 npm run dev`。
- SSE 事件协议见 `docs/api.md`：`sources → token×N → done`，流中错误走 `error` 事件。
- 双页码约定：印刷页 = 物理页 + 7（2026-08-28 会签定值）。

## 2. 环境前置

| 项 | 要求 | 检查命令 |
|---|---|---|
| Node | **≥22.18**（Vite 8 硬约束；低于此版本启动即报 `node:util.styleText` 缺失） | `node --version` |
| 后端依赖 | requirements.txt 已装（`python -c "import fastapi, chromadb"` 无报错） | — |
| 索引（仅 live 模式） | `make index` 已完成（`indexes/` 下有 `struct_bge-m3_*` 目录） | `python scripts/build_index.py --list` |

Node 版本切换（本机为 nvm4w）：`nvm install 24 && nvm use 24.x`；切回 `nvm use 16.14.0`。

## 3. 启动

```bash
# 终端 1：后端（二选一）
make serve                                    # mock 模式：确定性假数据，随时可用
RAG_MODE=live make serve                      # live 模式：真实检索（须先 make index）

# 终端 2：前端
cd web/RAG4ZRDDS
npm install --registry=https://registry.npmmirror.com   # 首次
npm run dev                                            # 默认 http://localhost:5173
```

浏览器打开 **http://localhost:5173**，先访问 `http://localhost:5173/healthz`
应返回 `{"status":"ok","mode":"mock|live"}`——能返回即代理链路通。

## 4. 测试用例

### 4.1 mock 模式（无需任何数据产物）

| 步骤 | 操作 | 预期 |
|---|---|---|
| 1 | 页面加载 | 输入框 + 字数 0/200 + "提问"按钮禁用 + 提问示例提示 |
| 2 | 输入"如何创建 DataWriter？" | 计数变 16/200，按钮转亮 |
| 3 | 按 Enter（或点"提问"；Shift+Enter 是换行） | 先显示"正在检索..."，随后引用卡片与流式答案出现 |
| 4 | 检查引用卡片 | 5 张卡片；第 1 张为 `第 81 页（物理页 74）`（81=74+7）、章节 9.7.1、相关度 0.950 |
| 5 | 检查答案 | "【Mock 模式回答】……"完整渲染（含代码块文本），非原始 JSON 报文 |
| 6 | 输入超 200 字 | 自动截断到 200，提示"请精简问题内容" |
| 7 | 回答进行中再点"提问" | 按钮为"回答中..."禁用态，不可重复提交 |

### 4.2 live 模式（真实检索）

前置：`make index` 成功（真实建索引约 12 分钟，见 `scripts/build_index.py` 心跳）。

| 步骤 | 操作 | 预期 |
|---|---|---|
| 1 | `/healthz` 返回 `mode=live` | 后端启动即校验了索引存在 |
| 2 | 提问"如何创建 DataWriter？" | **首问约 16 秒**（加载 bge-m3 模型），期间显示"正在检索..." |
| 3 | 检查引用卡片 | 真实章节：`8.3.1 创建DataWriter` 居首，`第 92 页（物理页 85）`，相关度约 0.76 |
| 4 | 检查答案区 | 红色错误框："生成实现尚未合入：等待成员 C 的 generation/ 包……" —— **这是预期行为**（C 未交付，evidence-first：引用先到、答案缺口可读） |
| 5 | 第二问起 | 秒级响应（模型已驻留） |

### 4.3 异常路径

| 场景 | 预期 |
|---|---|
| 后端未启动时提问 | 红色错误框"请求失败：……（请确认后端已启动：make serve）"，不弹浏览器 alert |
| 问题为纯空白 | 按钮禁用，无法提交 |
| 后端 422/400（非法请求体） | 错误框展示后端返回的中文可读错误 |

## 5. 排错（FAQ）

| 症状 | 原因与处置 |
|---|---|
| `npm run dev` 报 `node:util.styleText` 缺失 | Node <22.18。`nvm use 24.x` 后重装 `rm -rf node_modules && npm install` |
| 页面正常但提问后转圈不出结果，`/healthz` 也不通 | 后端未启动，或代理目标端口不对（`RAG_BACKEND_URL`） |
| 提问弹"请求异常，请检查后端服务是否启动" | 旧版前端行为（请求打到 Vite 自己）。确认代码含 2026-08-29 修复（`vite.config.js` 有 `server.proxy`、ChatInput 只 `emit('submit')`） |
| 答案区显示原始 `event:/data:` 文本 | 旧版 SSE 解析。确认 `App.vue` 为按帧解析版本（`handleFrame`） |
| live 首问超过 30 秒无响应 | 查后端终端是否在加载模型权重；仍无输出看 `indexes/` 是否有内容（`--list`） |
| 控制台中文乱码 | 请求体须为 UTF-8（curl 用 `--data-binary @文件`；Windows 终端先 `chcp 65001`） |

## 6. 修复记录（2026-08-29，D 依联调探测问题集修复）

| # | 缺陷 | 修复 |
|---|---|---|
| 1 | `ChatInput.vue` 请求发到相对路径 `/query`，打到 Vite 自己（404），后端实际在 8000 | `vite.config.js` 增加 `server.proxy`（/query、/sources、/healthz → 后端，可用 `RAG_BACKEND_URL` 覆盖） |
| 2 | `App.vue` 的 `streamResponse`/`handleQuery` 从未被调用——`<ChatInput />` 无事件绑定，组件内部又自发请求，两套逻辑互不相通 | `ChatInput` 改为纯输入组件 `emit('submit')`；`App` 监听并统一发起请求；loading/hasAnswer 经 props 回传 |
| 3 | SSE 仅剥离开头一个 `data: ` 前缀，不解析事件帧，答案会渲染成原始报文 | 按 `\n\n` 分帧、解析 `event:/data:` 四类事件（sources/token/done/error），跨 chunk 半帧缓冲 |
| 4 | 无引用卡片、无 error 事件展示、`isLoading` 永不复位（首帧后卡死在"正在检索"） | 引用卡片（章节+双页码+相关度）、红色错误框、`finally` 复位 loading；Enter 提交 / Shift+Enter 换行 |

实测证据：2026-08-29 双模式全流程通过——mock 流式答案到 `done`；live 真实引用
（8.3.1 节居首，92=85+7）+ 生成缺口可读错误框。
