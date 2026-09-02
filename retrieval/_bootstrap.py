"""统一引导 scripts/ 目录下的 experiment_config 模块（scripts/ 无 __init__.py）。

所有需要 D 的配置派生函数的代码统一从这里拿模块，保证 sys.modules 中
只有一个 experiment_config 实例（monkeypatch 与派生常量不会分叉）。
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import experiment_config  # noqa: E402  (经上方路径引导)

__all__ = ["experiment_config"]
