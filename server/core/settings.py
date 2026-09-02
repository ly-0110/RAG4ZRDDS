"""应用配置。"""

from pathlib import Path
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """RAG 服务配置。"""
    
    rag_mode: str = Field(default="mock", description="运行模式：mock/live")
    rag_experiment_config: dict | None = Field(default=None, description="实验配置（JSON）")
    cors_origin_list: list[str] = Field(default_factory=lambda: ["*"], description="CORS 允许来源")
    log_dir: str = Field(default="logs", description="日志目录")
    sources_cache_size: int = Field(default=100, description="来源缓存大小")
    
    @classmethod
    def create(cls) -> "Settings":
        """创建默认配置实例。"""
        return cls()


settings = Settings()
