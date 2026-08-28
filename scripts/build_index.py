#!/usr/bin/env python3
"""
scripts/build_index.py — processed + config → indexes/ 索引构建门面

职责（成员 D · 集成与实验平台）:
  * 按实验配置派生索引目录 indexes/{method}_{embed}_{hash8}（同名可回切）
  * 实际建库委托成员 B 交付物 retrieval.index.build_index（幂等覆盖重建）
  * 构建成功后写 manifest.json：实验身份、配置 hash、节点数、模型、耗时
  * --list 盘点既有索引与各自对应的实验配置（回切/审计入口）
  * --fake-embed 用确定性假向量只验结构（CI/无模型环境冒烟，产物不可用于服务）

用法:
  make index                                   # 默认配置（struct_v1 基线）
  python scripts/build_index.py --config configs/experiments/<实验>.yaml
  python scripts/build_index.py --list

依赖: scripts/experiment_config.py · retrieval/*（B 交付物）· chromadb
      真实 embedding 首次运行需联网下载模型（HF_ENDPOINT=https://hf-mirror.com）
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import experiment_config as ec  # noqa: E402

MANIFEST_NAME = "manifest.json"


def _fake_embed(texts: list[str]) -> list[list[float]]:
    """确定性假向量：仅验证结构通路，无检索语义。"""
    return [
        [((len(t) * 3 + i) % 11) / 11 + 0.1, ((len(t) + 5 * i) % 7) / 7 + 0.1]
        for i, t in enumerate(texts)
    ]


def _write_manifest(index_path: Path, cfg, nodes_count: int, build_seconds: float,
                    fake: bool) -> Path:
    manifest = {
        "experiment": cfg.experiment.name,
        "config_hash8": ec.config_hash8(cfg),
        "chunking": f"{cfg.chunking.method}_{cfg.chunking.version}",
        "embedding": (
            {"model": cfg.embedding.model, "provider": cfg.embedding.provider,
             "device": cfg.embedding.device}
            if not fake else {"model": "FAKE-embed (结构冒烟，不可用于服务)"}
        ),
        "index": {"backend": cfg.index.backend, "metric": cfg.index.metric},
        "nodes_file": str(ec.nodes_path(cfg).relative_to(REPO_ROOT)),
        "nodes_count": nodes_count,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "build_seconds": round(build_seconds, 1),
        "fake_embed": fake,
    }
    p = index_path / MANIFEST_NAME
    p.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                 encoding="utf-8")
    return p


def _count_nodes(cfg) -> int:
    """从产物 jsonl 统计非空文本节点数（与 add_nodes 的跳过规则一致）。"""
    n = 0
    with ec.nodes_path(cfg).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rec = json.loads(line)
                if (rec.get("text") or "").strip():
                    n += 1
    return n


def cmd_build(config_path: str, fake: bool) -> int:
    cfg = ec.load(config_path)

    nodes_file = ec.nodes_path(cfg)
    if not nodes_file.exists():
        print(f"[index] 错误: Node 集不存在 {nodes_file}（先运行 make ingest）",
              file=sys.stderr)
        return 1

    from retrieval.index import build_index

    target = ec.index_dir(cfg)
    print(f"[index] 实验={cfg.experiment.name} hash8={ec.config_hash8(cfg)} "
          f"→ {target.relative_to(REPO_ROOT)}")
    t0 = time.monotonic()
    index_path = build_index(cfg, embed_fn=_fake_embed if fake else None)
    elapsed = time.monotonic() - t0
    n = _count_nodes(cfg)
    manifest = _write_manifest(Path(index_path), cfg, n, elapsed, fake)
    print(f"[index] ✓ 完成：{n} 节点，耗时 {elapsed:.1f}s"
          + ("（fake-embed 冒烟，勿用于服务）" if fake else ""))
    print(f"[index] manifest → {manifest.relative_to(REPO_ROOT)}")
    return 0


def cmd_list(config_path: str | None) -> int:
    root = REPO_ROOT / "indexes"
    current = None
    if config_path:
        cfg = ec.load(config_path)
        current = ec.index_dirname(cfg)
    if not root.exists() or not any(root.iterdir()):
        print("[index] indexes/ 为空——先运行 make index")
        return 0
    rows = []
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        m = d / MANIFEST_NAME
        if m.exists():
            try:
                info = json.loads(m.read_text(encoding="utf-8"))
                desc = (f"{info.get('experiment', '?')} nodes={info.get('nodes_count')}"
                        f" built={info.get('built_at', '?')[:10]}"
                        + (" [FAKE]" if info.get("fake_embed") else ""))
            except json.JSONDecodeError:
                desc = "manifest 损坏"
        else:
            desc = "无 manifest（非本脚本构建或旧版）"
        mark = "*" if d.name == current else " "
        rows.append(f"  {mark} {d.name:<40} {desc}")
    print(f"[index] indexes/ 盘点（* = 当前配置 {config_path or '未指定'} 的目标索引）:")
    print("\n".join(rows))
    print("[index] 回切方法：改 configs/experiments/*.yaml 的对应实验名重跑 "
          "make index CFG=...；服务按配置 hash 自动定位目录，换配置即换索引。")
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):  # Windows 控制台默认 GBK
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="build_index", description=__doc__)
    parser.add_argument("--config", default="configs/experiments/struct_v1.yaml",
                        help="实验配置 yaml（默认 struct_v1 基线）")
    parser.add_argument("--list", action="store_true",
                        help="盘点 indexes/ 既有索引（不构建）")
    parser.add_argument("--fake-embed", action="store_true",
                        help="用确定性假向量只验结构（无模型环境冒烟）")
    args = parser.parse_args(argv)

    if args.list:
        cfg_path = args.config if Path(args.config).exists() else None
        return cmd_list(cfg_path)
    return cmd_build(args.config, args.fake_embed)


if __name__ == "__main__":
    raise SystemExit(main())
