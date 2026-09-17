"""来源类别标签与优先级。

source_id → 中文文档类别的单一事实源：context_builder（来源标签注入）与
prompts/v2（来源优先级话术）共用，保证两处口径一致。

默认优先级序：
    API 参考 > 开发者指南 > 用户手册 > FAQ > 非官方资料
已知 source_id 为 user_manual / zrdds_dev_guide；HTML 源接入
HTML 后按实际注册名补齐，并用 §7.5 场景实测校准。
"""

from __future__ import annotations

SOURCE_CATEGORY: dict[str, str] = {
    "user_manual": "用户手册",
    "zrdds_dev_guide": "开发者指南",
    # 预留（A 接入后补充）：
    # "api_reference": "API 参考",
    # "faq": "FAQ",
}

# 草案优先级（高→低）：开发者指南（HTML，含 API 签名/参数）优先于用户手册。
DEFAULT_PRIORITY: list[str] = ["zrdds_dev_guide", "user_manual"]
