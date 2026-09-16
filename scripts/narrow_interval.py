#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 expected_sources.jsonl 的全书级宽区间收紧为章节级印刷页区间。

真值来源（唯一）：`data/processed/struct_v1.jsonl`——A 的 Node 产物里每个章节的
`printed_page_start` / `printed_page_end`，不经过检索器，也不依赖手抄目录。

规则：
  1. 从标注的 `section_keyword` 取章节号（如 `6.3.6`）；
  2. 命中产物章节 → `page_print` 收紧为该章节的印刷页闭区间，并把关键词换成产物里
     的规范写法 `<章节号> <标题>`（保证与检索结果的 `section` 字段可子串匹配）；
  3. 章节号缺失或非法（如 Q021/Q023/Q028 的 `"5"`、Q059/Q060/Q119 的 `"1"`）走
     `OVERRIDES`——逐题按产物正文与章节标题核对后指定章节，依据见
     `evaluation/datasets/narrow_interval_report.md`；
  4. 区间收紧后，`scripts/audit_annotations.py` 能查出的"题干 token 不在标注页附近"
     题目走 `RETARGETS`——这些题的 `section_keyword` 指到了别的章节（复制粘贴、只抄了
     章节号、抄了同名字段），逐题读题干后在产物里定位真正的答案章节。每条都带**可机检
     证据**，证据不成立脚本直接报错退出（`_verify_retargets`）。

用法：
  python scripts/narrow_interval.py            # 就地更新数据集并写报告
  python scripts/narrow_interval.py --check    # 只报告差异，不写文件
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NODES = REPO_ROOT / "data/processed/struct_v1.jsonl"
DATASET = REPO_ROOT / "evaluation/datasets/expected_sources.jsonl"
REPORT = REPO_ROOT / "evaluation/datasets/narrow_interval_report.md"

SEC_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+(.*)$")
LEAD_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)")
RE_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]{4,}")


def _norm(text) -> str:
    """归一化：去空白 + 小写（与 audit_annotations 的口径一致）。"""
    return "".join((text or "").split()).lower()


# 关键词无法定位章节时的逐题覆盖（依据见报告"关键词异常题目"一节）。
OVERRIDES = {
    "Q021": "9.3.5.7",   # DataReader on_subscription_matched() → SUBSCRIPTION_MATCHED Status
    "Q023": "9.3.5.2",   # DataReader on_liveliness_changed() → LIVELINESS_CHANGED Status
    "Q028": "8.3.5",     # DataWriter on_publication_matched() → PUBLICATION_MATCHED Status
    "Q059": "10.17",     # PartitionQosPolicy
    "Q060": "10.18",     # PresentationQosPolicy
    "Q119": "10.30",     # TransportConfigQosPolicy
}

# 区间收紧后暴露的"题干 token 不在标注页附近"题目（audit_annotations 的
# QUESTION_TOKEN_OFF_PAGE）：这些题的 section_keyword 指到了别的章节（复制粘贴、抄了
# 相邻小节号、抄了同名字段），按题干在产物里重新定位。所有错误码题都在 5.1.2 的
# 表5-2（手册唯一的 DDS_RETCODE_* 清单）里。
#
# 值为 (章节号, 证据类型, 证据串, 依据)，证据由 `_verify_retargets` 机检：
#   title_id  —— 证据串是目标章节标题里的标识符，且全手册仅该标题含它
#   text_token—— 证据串出现在目标章节的正文里（说明该页区间确实在讲这件事）
RETARGETS: dict[str, tuple[str, str, str, str]] = {
    "Q008": ("9.3.10.7", "title_id", "read_w_condition",
             "read_w_condition() 的参数在 9.3.10.7；原标注 9.3.10.1 只讲 read()/take()"),
    "Q012": ("5.5.5", "text_token", "create_readcondition",
             "create_readcondition()/SampleStateMask 在 5.5.5；原标注只覆盖样本状态枚举"),
    "Q015": ("8.2.8", "text_token", "wait_for_acknowledgments",
             "wait_for_acknowledgments() 的返回码在 8.2.8 表；原标注是 writer() 阻塞时间"),
    "Q018": ("5.3", "text_token", "on_data_available",
             "on_data_available() 回调语义在 5.3 Listener；原标注是 Subscriber 的 Status"),
    "Q029": ("8.3.5", "text_token", "on_offered_deadline_missed",
             "题干是 DataWriter 回调，原标注误抄了 DataReader 的 Status 小节"),
    "Q030": ("8.3.5", "text_token", "on_offered_incompatible_qos",
             "题干是 DataWriter 回调，原标注误抄了 DataReader 的 Status 小节"),
    "Q037": ("10.30", "title_id", "transportconfigqospolicy",
             "原标注 10.36 是 TransportPriorityQosPolicy，与题干仅一词之差"),
    "Q038": ("10.6", "title_id", "discoveryconfigqospolicy",
             "DiscoveryConfigQosPolicy 章节；原标注 23.1 只是配置说明"),
    "Q039": ("10.8", "title_id", "entityfactoryqospolicy",
             "EntityFactoryQosPolicy 章节（含 autoenable_created_entities 字段）"),
    "Q040": ("10.13", "title_id", "logqospolicy",
             "LogQosPolicy 章节；原标注 25.4.1 是日志 QoS 的使用说明"),
    "Q043": ("6.3.4", "text_token", "rtps_message_little_endian",
             "该字段属 DomainParticipant 的 QoS 设置（6.3.4）"),
    "Q044": ("10.27", "title_id", "threadcoreaffinityqospolicy",
             "ThreadCoreAffinityQosPolicy 章节；原标注 6.2.1 是工厂 QoS 设置位置"),
    "Q049": ("8.2.4", "text_token", "publisherqos",
             "PublisherQos 成员清单在 8.2.4；原标注只讲何时设置 QoS"),
    "Q050": ("9.2.4", "text_token", "subscriberqos",
             "SubscriberQos 成员清单在 9.2.4；原标注是 DurabilityServiceQosPolicy"),
    "Q053": ("10.10", "title_id", "historyqospolicy",
             "HistoryQosPolicy 章节；原标注是 DurabilityServiceQosPolicy"),
    "Q054": ("10.11", "title_id", "lifespanqospolicy",
             "LifespanQosPolicy 章节；原标注是 DurabilityServiceQosPolicy"),
    "Q055": ("10.4", "title_id", "deadlineqospolicy",
             "DeadlineQosPolicy 章节；原标注是 REQUESTED_DEADLINE_MISSED Status"),
    "Q056": ("10.7", "title_id", "durabilityqospolicy",
             "DurabilityQosPolicy 章节；原标注是 DurabilityServiceQosPolicy"),
    "Q061": ("10.9", "title_id", "groupdataqospolicy",
             "GroupDataQosPolicy 章节；原标注 23.1 只是配置说明"),
    "Q062": ("10.31", "title_id", "userdataqospolicy",
             "UserDataQosPolicy 章节；原标注 23.1 只是配置说明"),
    "Q064": ("10.29", "title_id", "topicdataqospolicy",
             "TopicDataQosPolicy 章节；原标注 7.2.3.2 是创建 Topic 后配 QoS"),
    "Q065": ("10.32", "title_id", "writerdatalifecycleqospolicy",
             "WriterDataLifecycleQosPolicy 章节；原标注 10.12 是 LivelinessQosPolicy"),
    "Q066": ("10.23", "title_id", "readerdatalifecycleqospolicy",
             "ReaderDataLifecycleQosPolicy 章节；原标注 10.12 是 LivelinessQosPolicy"),
    "Q072": ("5.5", "text_token", "waitset",
             "Condition 与 WaitSets 章节；原标注 11.3.2 是 zrddsgen 编译器"),
    "Q087": ("8.3.7", "text_token", "get_publisher",
             "get_publisher() 在 8.3.7 获取 DataWriter 的关联实体；原标注是删除子实体"),
    "Q089": ("8.2.8", "text_token", "write_w_timestamp",
             "write_w_timestamp() 在 8.2.8 的表里；原标注是 writer() 的阻塞时间"),
    "Q091": ("8.3.9", "text_token", "unregister_instance",
             "unregister_instance() 属 DataWriter 实例管理（8.3.9）"),
    "Q093": ("9.2.2", "text_token", "delete_datareader",
             "delete_datareader() 是 Subscriber 的操作（9.2.2）；原标注是 DataReader 侧的删除"),
    "Q094": ("9.3.7", "text_token", "get_subscriber",
             "get_subscriber() 在 9.3.7 获取 DataReader 的关联实体；原标注是删除子实体"),
    "Q104": ("4.1.1", "text_token", "maximum",
             "sequence 的 length/maximum 字段在 4.1.1；原标注 7.3.5.6 是 IDL 里的序列写法"),
    "Q105": ("11.4.1", "title_id", "visual",
             "Visual Studio 建工程章节；原标注 3.2 是编译 IDL 文件"),
    "Q106": ("4.2.5", "text_token", "eclipse",
             "Linux/Eclipse 编译与 -java_package 选项在 4.2.5；原标注是 zrddsgen 编译器"),
    "Q120": ("10.31", "title_id", "userdataqospolicy",
             "UserDataQosPolicy 章节；原标注 11.6.1 是头文件说明"),
}

# 错误码题：手册里 14 个 DDS_RETCODE_* 只出现在 5.1.2 使能实体（表5-2）。
for _qid, _code in (
    ("Q074", "dds_retcode_error"),
    ("Q075", "dds_retcode_bad_parameter"),
    ("Q076", "dds_retcode_already_deleted"),
    ("Q077", "dds_retcode_out_of_resources"),
    ("Q078", "dds_retcode_not_enabled"),
    ("Q079", "dds_retcode_immutable_policy"),
    ("Q080", "dds_retcode_inconsistent"),
    ("Q081", "dds_retcode_precondition_not_met"),
    ("Q083", "dds_retcode_illegal_operation"),
    ("Q084", "dds_retcode_no_data"),
):
    RETARGETS[_qid] = ("5.1.2", "text_token", _code,
                       "手册唯一的 DDS_RETCODE_* 清单（表5-2）在 5.1.2；原标注与错误码无关")


def load_sections(nodes_path: Path) -> dict:
    """章节号 → {title, start, end, paths, titles, text}（同章节多块取页区间并集）。"""
    sections: dict = {}
    with nodes_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            md = row["metadata"]
            title = (md.get("title") or "").strip().replace("\n", " ")
            m = SEC_RE.match(title)
            start = md.get("printed_page_start")
            if not m or start is None:
                continue
            num, name = m.group(1), m.group(2).strip()
            end = md.get("printed_page_end", start)
            sec = sections.setdefault(
                num, {"title": f"{num} {name}", "start": start, "end": end,
                      "paths": [], "titles": [], "text": ""})
            sec["start"] = min(sec["start"], start)
            sec["end"] = max(sec["end"], end)
            if title not in sec["titles"]:
                sec["titles"].append(title)
            sec["text"] += _norm(row.get("text"))
            path = md.get("section_path")
            if path and path not in sec["paths"]:
                sec["paths"].append(path)
    # 父章节的正文往往只有导语（如 5.3 Listener 仅 153 字），术语落在子节里；
    # 而父章节的页区间已覆盖子节，故证据校验按"本章节 + 其子节"的正文进行。
    for num, sec in sections.items():
        sec["sub_text"] = "".join(
            other["text"] for other_num, other in sections.items()
            if other_num == num or other_num.startswith(num + "."))
    return sections


def _verify_retargets(sections: dict) -> None:
    """逐条校验 RETARGETS 的证据，任一不成立即失败——防止重定向表随产物漂移。"""
    ids: dict[str, list[str]] = {}          # 小写标识符 → 章节号列表
    for num, sec in sections.items():
        for token in RE_WORD.findall(sec["title"]):
            ids.setdefault(token.lower(), []).append(num)
    for qid, (num, kind, evidence, _note) in RETARGETS.items():
        if num not in sections:
            raise SystemExit(f"{qid}: RETARGETS 指向的章节 {num!r} 不在产物里")
        sec = sections[num]
        if kind == "title_id":
            hits = [n for n, nums in ids.items() if n == evidence.lower()]
            owners = {n for n in (ids.get(evidence.lower()) or [])}
            if evidence.lower() not in ids:
                raise SystemExit(
                    f"{qid}: 证据 {evidence!r} 不是章节标题里的标识符"
                    + (f"（最接近 {hits}）" if hits else ""))
            if len(owners) > 1:
                raise SystemExit(f"{qid}: 证据 {evidence!r} 在多个章节标题里出现 {sorted(owners)}")
            if num not in owners:
                raise SystemExit(f"{qid}: 证据 {evidence!r} 不属于章节 {num}")
        elif kind == "text_token":
            if _norm(evidence) not in sec["sub_text"]:
                raise SystemExit(
                    f"{qid}: 证据 {evidence!r} 不在章节 {num}（{sec['title']}）及其子节的正文里")
        else:
            raise SystemExit(f"{qid}: 未知证据类型 {kind!r}")


def section_of(rec: dict, sections: dict):
    """定位一条标注所属章节，返回 (章节号, 依据说明)。"""
    qid = rec.get("question_id")
    if qid in RETARGETS:
        return RETARGETS[qid][0], "题干 token 重定向"
    if qid in OVERRIDES:
        return OVERRIDES[qid], "关键词异常，按产物正文逐题核对"

    keyword = rec.get("section_keyword") or ""
    m = LEAD_RE.match(keyword)
    num = m.group(1) if m else None
    if num and num in sections:
        return num, "关键词章节号"

    # 章节号写法有出入时退回关键词全文匹配产物 section_path
    for candidate, sec in sections.items():
        if any(keyword and keyword in path for path in sec["paths"]):
            return candidate, "关键词匹配章节路径"
    return None, "无法定位"


def main() -> int:
    p = argparse.ArgumentParser(prog="narrow_interval", description=__doc__)
    p.add_argument("--nodes", default=str(NODES))
    p.add_argument("--dataset", default=str(DATASET))
    p.add_argument("--input", default=None,
                   help="读取标注的路径（默认与 --dataset 相同）；"
                        "从收窄前的版本重新生成对比报告时指向旧版本")
    p.add_argument("--report", default=str(REPORT))
    p.add_argument("--check", action="store_true", help="只报告差异，不写文件")
    args = p.parse_args()

    sections = load_sections(Path(args.nodes))
    _verify_retargets(sections)
    dataset = Path(args.dataset)
    source = Path(args.input) if args.input else dataset
    records = [json.loads(line) for line in
               source.read_text(encoding="utf-8").splitlines() if line.strip()]

    rows, unresolved, before_span, after_span = [], [], 0, 0
    retarget_rows = []
    for rec in records:
        qid = rec.get("question_id")
        old_keyword = rec.get("section_keyword")
        num, why = section_of(rec, sections)
        old = rec.get("page_print")
        old_lo, old_hi = (old if isinstance(old, list) else [old, old])
        if num is None or num not in sections:
            unresolved.append((qid, num or old_keyword))
            rows.append((qid, old, old, None, why))
            before_span += old_hi - old_lo
            after_span += old_hi - old_lo
            continue
        sec = sections[num]
        new = [sec["start"], sec["end"]]
        if not any(sec["title"] in path for path in sec["paths"]):
            raise SystemExit(
                f"{qid}: 规范关键词 {sec['title']!r} 不在任何 section_path 中，"
                "无法与检索结果的 section 字段匹配")
        rec["section_keyword"] = sec["title"]
        rec["page_print"] = new
        if qid in RETARGETS:
            _num, kind, evidence, note = RETARGETS[qid]
            retarget_rows.append((qid, old_keyword, sec["title"], new, kind, evidence, note))
        before_span += old_hi - old_lo
        after_span += new[1] - new[0]
        rows.append((qid, old, new, num, why))

    narrowed = sum(1 for r in rows if r[1] != r[2])
    total = len(records)

    if unresolved:
        listing = ", ".join(f"{q}({k!r})" for q, k in unresolved)
        print(f"[narrow] 未定位章节 {len(unresolved)} 题：{listing}")

    if not args.check:
        dataset.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
            encoding="utf-8")
        _write_report(Path(args.report), rows, total, narrowed, unresolved,
                      before_span, after_span, retarget_rows)

    print(f"[narrow] 输入 {source}；收窄 {narrowed}/{total} 题；"
          f"区间跨度合计 {before_span} → {after_span} 页"
          f"（平均 {before_span / total:.1f} → {after_span / total:.1f}）")
    print("[narrow] " + ("未写入（--check）"
                        if args.check else f"已更新 {dataset.name} 与报告 {Path(args.report).name}"))
    return 1 if unresolved else 0


def _fmt(pages) -> str:
    if isinstance(pages, list):
        return f"[{pages[0]}, {pages[-1]}]"
    return str(pages)


def _write_report(path: Path, rows, total: int, narrowed: int, unresolved,
                  before_span: int, after_span: int, retarget_rows) -> None:
    lines = [
        "# expected_sources.jsonl 区间收窄报告",
        "",
        "## 口径",
        "",
        "- **真值来源**：`data/processed/struct_v1.jsonl`（A 的 Node 产物）中每个章节的",
        "  `printed_page_start` / `printed_page_end`；印刷页 = 物理页 − 6。",
        "- **规则**：由 `section_keyword` 的章节号定位产物章节 → `page_print` 收紧为该章节的",
        "  印刷页闭区间；关键词同时改写为产物里的规范写法 `<章节号> <标题>`，保证与检索结果的",
        "  `section` 字段（`section_path`）可子串匹配。",
        "- **复现**：`python scripts/narrow_interval.py`（`--check` 只报告不写入）。",
        "  要从收窄前的版本重新生成本报告：",
        "  `python -c \"import subprocess,pathlib;pathlib.Path('before.jsonl').write_bytes(subprocess.check_output(['git','show','HEAD:evaluation/datasets/expected_sources.jsonl']))\"`",
        "  然后 `python scripts/narrow_interval.py --input before.jsonl`。",
        "",
        "## 统计",
        "",
        "| 项目 | 值 |",
        "|---|---|",
        f"| 题目总数 | {total} |",
        f"| 收窄题目 | {narrowed} |",
        f"| 其中：关键词重定向 | {len(retarget_rows)} |",
        f"| 未定位章节 | {len(unresolved)} |",
        f"| 区间跨度合计 | {before_span} → {after_span} 页 |",
        f"| 平均跨度 | {before_span / total:.1f} → {after_span / total:.1f} 页 |",
        "",
        "## 明细",
        "",
        "| question_id | 原区间 | 新区间 | 章节 | 依据 |",
        "|---|---|---|---|---|",
    ]
    for qid, old, new, num, why in rows:
        lines.append(f"| {qid} | {_fmt(old)} | {_fmt(new)} | {num or '—'} | {why} |")

    lines += [
        "",
        "## 关键词异常题目",
        "",
        "以下 6 题的 `section_keyword` 是单字符数字（`\"5\"` / `\"1\"`），无法定位章节，",
        "按产物正文逐题核对后由脚本内 `OVERRIDES` 指定：",
        "",
        "| question_id | 原关键词 | 指定章节 | 依据 |",
        "|---|---|---|---|",
        "| Q021 | `5` | 9.3.5.7 SUBSCRIPTION_MATCHED Status | 题干 `on_subscription_matched()` 的判定依据即该状态（印刷页 106-107） |",
        "| Q023 | `5` | 9.3.5.2 LIVELINESS_CHANGED Status | 题干 `on_liveliness_changed()`（印刷页 105） |",
        "| Q028 | `5` | 8.3.5 关于DataWriter的Status | 题干 `on_publication_matched()`（印刷页 85-86）；产物无 8.3.5.4 子节，取父节 |",
        "| Q059 | `1` | 10.17 PartitionQosPolicy | 题干 `PartitionQosPolicy`（印刷页 140-142） |",
        "| Q060 | `1` | 10.18 PresentationQosPolicy | 题干 `PresentationQosPolicy`（印刷页 142-145） |",
        "| Q119 | `1` | 10.30 TransportConfigQosPolicy | 题干 `TransportConfigQosPolicy`（印刷页 157-159） |",
        "",
        "## 关键词重定向",
        "",
        "原区间是整个用书（`[7, 288]` 一类），任何术语都\"落在标注页内\"，所以 `section_keyword`",
        "指错章节也查不出来。收紧到章节级后 `scripts/audit_annotations.py` 的",
        "`QUESTION_TOKEN_OFF_PAGE` 才能暴露\"题干的技术术语不在标注页附近\"的题目——",
        f"共 {len(retarget_rows)} 题。逐题读题干并在产物里定位真正的答案章节后，由脚本内",
        "`RETARGETS` 改正；每条都带可机检证据，证据不成立脚本直接报错（`_verify_retargets`）：",
        "",
        "- `title_id`：证据串是目标章节标题里的标识符，且**全手册只有该标题含它**；",
        "- `text_token`：证据串出现在目标章节的正文里（说明该页区间确实在讲这件事）。",
        "",
        "| question_id | 原关键词 | 新章节 | 新区间 | 证据（机检） | 依据 |",
        "|---|---|---|---|---|---|",
    ]
    for qid, old_kw, new_kw, new, kind, evidence, note in retarget_rows:
        lines.append(
            f"| {qid} | `{old_kw}` | {new_kw} | {_fmt(new)} | {kind}: `{evidence}` | {note} |")

    lines += [
        "",
        "## 遗留问题",
        "",
        "### 1. 仍被判为 `QUESTION_TOKEN_OFF_PAGE` 的 5 题（审计口径的假阳性）",
        "",
        "| question_id | 章节 | 页区间 | 说明 |",
        "|---|---|---|---|",
        "| Q018 | 5.3 Listener | 34-38 | 回调语义在 5.3，但题干追问的 `create_datawriter()` 只出现在",
        "  25/26/29/30/64/73 页，任一章节都无法同时容纳两个 token |",
        "| Q026 | 9.3.5.5 SAMPLE_LOST Status | 106-106 | 题干 `samplestatemask` 的说明在 5.5.5 ReadConditions 与",
        "  9.3.10.3-9.3.10.7 的读取接口，与回调 `on_sample_lost` 不在同一章节；",
        "  当前标注是回调对应的 Status，故不改 |",
        "| Q065 | 10.32 WriterDataLifecycleQosPolicy | 160-161 | 策略语义在 10.32，但 `writer_data_lifecycle`",
        "  字段名只出现在 81-84 页的 DataWriter QoS 设置里 |",
        "| Q066 | 10.23 ReaderDataLifecycleQosPolicy | 148-150 | 同上，`reader_data_lifecycle` 字段名只在",
        "  100-103 页 |",
        "| Q112 | 24.2 Licence授权方式 | 276-276 | 手册写 `licence`、题干写 `license`，拼写变体导致 token 不命中 |",
        "",
        "这 5 题的标注本身正确，是审计的\"题干 token 必须落在标注页 ±2 页内\"启发式不适用于",
        "跨章节提问（题干同时问两件事、术语拼写与手册不一致）。建议审计侧为这类题加白名单，",
        "或把题干拆成单点问题。",
        "",
        "### 2. 问题集侧缺陷（改标注无法解决）",
        "",
        "Q021 / Q023 / Q028 题干中的字段名 `subscriptionMatched` / `livelinessChanged` /",
        "`publicationMatched` 在手册全文零命中——手册只写 `on_*_matched()` 回调与",
        "`*_MATCHED Status` 状态。`make audit` 会将这三题判为 `QUESTION_TOKEN_ABSENT`",
        "（按审计口径应转拒答集）。这不属区间收窄范围，需问题集负责人改写成手册术语，",
        "或明确移入拒答案例集。",
        "",
        "## 校验",
        "",
        "`python scripts/audit_annotations.py`（判定口径不变，只换被检数据集）：",
        "",
        "| 指标 | 收窄前（全书级区间） | 仅收窄后 | 收窄 + 重定向后（本版本） |",
        "|---|---|---|---|",
        "| 判定 | blocked | blocked | blocked |",
        "| QUESTION_TOKEN_OFF_PAGE | 0 | 45 | **5** |",
        "| QUESTION_TOKEN_ABSENT | 3 | 3 | 3 |",
        "| NO_TOKEN_PROBE（非阻断指纹） | 13 | 13 | 13 |",
        "| CIRCULAR_TOP1（非阻断指纹） | 4 | 0 | 0 |",
        "",
        "报告：`evaluation/reports/annotation_audit_before.*`（收窄前）、",
        "`evaluation/reports/annotation_audit_after.*`（本版本）。",
        "`QUESTION_TOKEN_OFF_PAGE` 收窄前恒为 0 不是\"没问题\"，而是整本书的区间把什么问题都盖住了",
        "——这正是本报告存在的意义。",
        "",
        "- `python -m pytest tests/ -q` ：60 passed（3 项失败为环境缺依赖 `rank_bm25` / 未构建索引，",
        "  与数据集改动无关）。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
