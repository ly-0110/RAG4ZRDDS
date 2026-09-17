"""生成与可靠性域：Prompt / Context 组装 / LLM 调用 / 最小 query_engine。

模块构成：
  * 确定 LLM 与调用方式：OpenAI 兼容 /chat/completions 流式接口，密钥走 .env
    （LLM_PROVIDER / LLM_BASE_URL / LLM_API_KEY / LLM_MODEL，前缀见实验配置
    generation.llm_env_prefix，默认 LLM_）；openai SDK 延迟导入。
    经 OpenAI 兼容协议调大模型（云端 API 或本地部署皆可），示例配置为 OpenRouter 免费档
    （minimax/minimax-m3:free；免费档清单变动频繁，DeepSeek/Qwen/Llama 免费档
    已下架，换模型见 .env.example 的 LLM 段）。
  * Baseline Prompt v0：只含两条硬规则——“仅依据检索内容作答”“回答必须给出来源”
  * 连接 Retriever 与 LLM 的最小 query_engine（generation/query_engine.py，实现
    AnswerStream 协议），定义 context 格式（generation/context_builder.py）

边界：不实现检索组件、不编写/标注问题集、不改分块代码；
Citation 字段与 Grounding / Abstention 规则见 docs/api.md 与 generation/prompts/。
"""
