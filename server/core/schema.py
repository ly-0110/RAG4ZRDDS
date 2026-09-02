"""API 契约模型 —— 请求/响应/引用字段的单一事实源。

字段变更规则：新增可选字段随时可以；修改/删除既有字段须同步更新 docs/api.md
并知会前端（成员 E）。Citation 的双页码约定：page_print = page_physical − 6
（2026-08-29 以 PDF 页眉印刷页码逐页核对定值；手册前 6 页为封面/罗马数字
前言不编页码，印刷第 1 页 = 物理第 7 页。旧约定 +7 为方向错误，已作废）。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class QueryRequest(BaseModel):
    """POST /query 请求体。"""

    question: str = Field(min_length=1, max_length=2000, description="用户问题")
    top_k: int | None = Field(
        default=None, ge=1, le=20, description="检索条数；缺省用服务端 QUERY_TOP_K"
    )


class SourceRef(BaseModel):
    """一条引用（对应知识库中的一个 Node）。

    mock 模式下即演示数据；live 模式由检索器填充同样字段。
    """

    node_id: str = Field(description="Node 全局唯一 ID")
    source_id: str = Field(description="来源短名，对应实验配置 sources[].id")
    source_name: str = Field(description="来源显示名，如 ZRDDS用户手册.pdf")
    section: str = Field(description="章节号，如 3.4.2")
    page_print: int | None = Field(default=None, description="印刷页码（手册上印的）")
    page_physical: int | None = Field(default=None, description="PDF 物理页码")
    score: float = Field(description="相关性得分，越高越相关")


class SourcesEvent(BaseModel):
    """SSE event=sources 的 data。检索完成即推送（evidence first）。"""

    request_id: str
    sources: list[SourceRef]


class TokenEvent(BaseModel):
    """SSE event=token 的 data。答案的一个文本增量。"""

    request_id: str
    text: str


class DoneEvent(BaseModel):
    """SSE event=done 的 data。完整答案 + 引用汇总，流正常结束的标志。"""

    request_id: str
    answer: str
    sources: list[SourceRef]


class ErrorEvent(BaseModel):
    """SSE event=error 的 data。流已开始后发生错误的唯一上报通道。"""

    request_id: str
    error: str


class ErrorResponse(BaseModel):
    """流开始前的 HTTP 错误体（400/404/500 等）。"""

    model_config = ConfigDict(extra="allow")

    error: str = Field(description="人类可读的错误说明")
