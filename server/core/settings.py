"""运行时配置：基于 pydantic-settings，读取进程环境变量与仓库根 .env。

约定：
  * 字段名即环境变量名（不区分大小写），如 RAG_MODE / APP_HOST；
  * default_top_k 经 validation_alias 映射到 QUERY_TOP_K；
  * .env 不存在时全部使用默认值；.env 不入 Git（见 .env.example 模板）。
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """服务运行时配置。各变量含义见 .env.example 与 docs/api.md。"""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_host: str = "127.0.0.1"
    app_port: int = 8000
    rag_mode: str = "mock"  # mock | live；live 需先 make index（pipeline.build_pipeline 按配置接线 B 检索）
    rag_experiment_config: str = "configs/experiments/struct_v1.yaml"  # live 模式的实验配置（相对仓库根）
    default_top_k: int = Field(default=5, ge=1, le=20, validation_alias="QUERY_TOP_K")
    cors_origins: str = "*"  # 逗号分隔；上线前收紧为前端实际来源
    log_dir: str = "logs"  # 三级日志 JSONL 落盘目录（相对仓库根或绝对路径；不入 Git）
    sources_cache_size: int = 100  # /sources 持久化存储的内存读取窗口上限（全量记录在 {log_dir}/sources.jsonl）

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
