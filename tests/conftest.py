"""测试会话环境守卫：强制 RAG_MODE=mock。

server.main 在模块导入期即 create_app() 组装管线，settings 又读仓库根
.env；若开发机 .env 为 RAG_MODE=live，仅导入 server.main 就会触发真实
索引/预热并要求 LLM 配置，单测收集被本机环境状态连累（2026-08-31
C 接线生成后即发生：两个 server 测试文件收集期崩溃）。

本 conftest 在测试模块导入前执行，进程环境变量优先于 .env，故测试一律
走 mock 管线；live 端到端由 `make serve` 人工验收，不走单测。
"""

import os

os.environ["RAG_MODE"] = "mock"
