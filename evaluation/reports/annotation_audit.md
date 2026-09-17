# 标注真值核对报告

- 结论: **pass**（阻断项 0，缺标注 0，多余 0）
- 题量: 问题集 120 / 标注 120
- 循环论证指纹: 与 evaluation\reports\struct_v1.json top-1 页码吻合 0/120（比例 0.0，阈值 0.9） → 未见异常

> 判据全部来自 Node 产物与章节树（分块正文、printed_page_start/end、章节标题），**不调用检索器**——所以从检索结果反推的标注骗不过它。top-1 比对只用来抓"标注=检索回显"的指纹，不当真值用。

## 逐题判定（仅列有问题的题）

| 题号 | 页码 | 关键词 | 判定 | token 实况 |
|---|---|---|---|---|
| Q018 | [34, 38] | 5.3 Listener | TOKEN_PARTIAL_OFF_PAGE | create_datawriter→实际在 [25, 26, 29, 30] |
| Q026 | [106, 106] | 9.3.5.5 SAMPLE_LOST Status | TOKEN_PARTIAL_OFF_PAGE | samplestatemask→实际在 [39, 40, 41, 42] |
| Q065 | [160, 161] | 10.32 WriterDataLifecycleQos | TOKEN_PARTIAL_OFF_PAGE | writer_data_lifecycle→实际在 [81, 82, 83, 84] |
| Q066 | [148, 150] | 10.23 ReaderDataLifecycleQos | TOKEN_PARTIAL_OFF_PAGE | reader_data_lifecycle→实际在 [100, 101, 102, 103] |
| Q068 | [280, 281] | 25.4.1 日志QoS | NO_TOKEN_PROBE | — |
| Q069 | [248, 248] | 20.1 XML配置说明 | NO_TOKEN_PROBE | — |
| Q070 | [172, 173] | 11.3.2 使用zrddsgen编译器 | NO_TOKEN_PROBE | — |
| Q071 | [289, 289] | 27.3 日志类型IDL文件 | NO_TOKEN_PROBE | — |
| Q073 | [248, 248] | 20.1 XML配置说明 | NO_TOKEN_PROBE | — |
| Q097 | [276, 276] | 24.2 Licence授权方式 | NO_TOKEN_PROBE | — |
| Q098 | [4, 6] | 1.5 ZRDDS概述 | NO_TOKEN_PROBE | — |
| Q099 | [172, 173] | 11.3.2 使用zrddsgen编译器 | NO_TOKEN_PROBE | — |
| Q102 | [178, 179] | 11.6.1 ZRDDS的头文件 | NO_TOKEN_PROBE | — |
| Q103 | [178, 179] | 11.6.1 ZRDDS的头文件 | NO_TOKEN_PROBE | — |
| Q107 | [22, 22] | 4.2.1 @key标注 | NO_TOKEN_PROBE | — |
| Q110 | [12, 15] | 3.2 编译IDL文件 | NO_TOKEN_PROBE | — |
| Q114 | [248, 248] | 20.1 XML配置说明 | NO_TOKEN_PROBE | — |

## 判定码计数

- `NO_TOKEN_PROBE` = 13（指纹）
- `TOKEN_PARTIAL_OFF_PAGE` = 4（非阻断（留痕））

## 闸门含义

- `blocked` / `suspect_circular` → **不得**开 `make regression REG_ARGS=--with-metrics`，指标只记不判（无有效标注不算指标）。
- `pass` → 指标通道方可启用，报告里的指标数字才可作为结论引用。
