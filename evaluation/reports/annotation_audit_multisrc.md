# 标注真值核对报告

- 结论: **pass**（阻断项 0，缺标注 0，多余 0）
- 题量: 问题集 12 / 标注 25
- 循环论证指纹: 与 evaluation\reports\struct_multisrc_v1.json top-1 页码吻合 0/0（比例 None，阈值 0.9） → 未见异常

> 判据全部来自 A 的产物与章节树（分块正文、printed_page_start/end、章节标题），**不调用检索器**——所以从检索结果反推的标注骗不过它。top-1 比对只用来抓"标注=检索回显"的指纹，不当真值用。

## 逐题判定（仅列有问题的题）

| 题号 | 页码 | 关键词 | 判定 | token 实况 |
|---|---|---|---|---|

## 判定码计数


## 闸门含义

- `blocked` / `suspect_circular` → **不得**开 `make regression REG_ARGS=--with-metrics`，指标只记不判（宁缺毋滥）。
- `pass` → 指标通道方可启用，六份 void 报告才能刷新为可引用数字。
