# expected_sources.jsonl 区间收窄报告

## 口径

- **真值来源**：`data/processed/struct_v1.jsonl`（A 的 Node 产物）中每个章节的
  `printed_page_start` / `printed_page_end`；印刷页 = 物理页 − 6。
- **规则**：由 `section_keyword` 的章节号定位产物章节 → `page_print` 收紧为该章节的
  印刷页闭区间；关键词同时改写为产物里的规范写法 `<章节号> <标题>`，保证与检索结果的
  `section` 字段（`section_path`）可子串匹配。
- **复现**：`python evaluation/narrow_interval.py`（`--check` 只报告不写入）。
  要从收窄前的区间重新生成本报告，用仓库内的收窄前快照
  `evaluation/datasets/expected_sources_pre_narrow.jsonl`（内容 = `origin/develop` 的
  `expected_sources.jsonl`，仅供 before/after 对照，勿用于实验）：
  `python evaluation/narrow_interval.py --input evaluation/datasets/expected_sources_pre_narrow.jsonl`。

## 统计

| 项目 | 值 |
|---|---|
| 题目总数 | 120 |
| 收窄题目 | 113 |
| 其中：关键词重定向 | 43 |
| 未定位章节 | 0 |
| 区间跨度合计 | 24820 → 125 页 |
| 平均跨度 | 206.8 → 1.0 页 |

## 明细

| question_id | 原区间 | 新区间 | 章节 | 依据 |
|---|---|---|---|---|
| Q001 | [7, 288] | [55, 56] | 6.3.6 | 关键词章节号 |
| Q002 | [7, 288] | [47, 48] | 6.2.4 | 关键词章节号 |
| Q003 | [7, 288] | [36, 37] | 5.3.5 | 关键词章节号 |
| Q004 | [7, 288] | [58, 59] | 6.3.12 | 关键词章节号 |
| Q005 | [7, 288] | [58, 59] | 6.3.12 | 关键词章节号 |
| Q006 | [8, 272] | [30, 30] | 5.1.4.3 | 关键词章节号 |
| Q007 | [8, 275] | [108, 109] | 9.3.10.2 | 关键词章节号 |
| Q008 | [8, 275] | [113, 114] | 9.3.10.7 | 题干 token 重定向 |
| Q009 | [38, 235] | [41, 42] | 5.5.6 | 关键词章节号 |
| Q010 | [7, 288] | [51, 52] | 6.3.3 | 关键词章节号 |
| Q011 | [7, 288] | [51, 52] | 6.3.3 | 关键词章节号 |
| Q012 | [8, 275] | [41, 41] | 5.5.5 | 题干 token 重定向 |
| Q013 | [7, 288] | [104, 107] | 9.3.5 | 关键词章节号 |
| Q014 | [38, 235] | [39, 40] | 5.5.2 | 关键词章节号 |
| Q015 | [3, 272] | [79, 80] | 8.2.8 | 题干 token 重定向 |
| Q016 | [8, 275] | [34, 38] | 5.3 | 关键词章节号 |
| Q017 | [7, 289] | [64, 64] | 7.2.5 | 关键词章节号 |
| Q018 | [25, 272] | [34, 38] | 5.3 | 题干 token 重定向 |
| Q019 | [8, 272] | [133, 135] | 10.12 | 关键词章节号 |
| Q020 | [3, 275] | [97, 97] | 9.2.6 | 关键词章节号 |
| Q021 | [4, 275] | [106, 107] | 9.3.5.7 | 关键词异常，按产物正文逐题核对 |
| Q022 | [38, 225] | [85, 86] | 8.3.6 | 关键词章节号 |
| Q023 | [4, 275] | [105, 105] | 9.3.5.2 | 关键词异常，按产物正文逐题核对 |
| Q024 | [8, 275] | [105, 106] | 9.3.5.3 | 关键词章节号 |
| Q025 | [8, 275] | [106, 106] | 9.3.5.4 | 关键词章节号 |
| Q026 | [8, 275] | [106, 106] | 9.3.5.5 | 关键词章节号 |
| Q027 | [8, 275] | [106, 106] | 9.3.5.5 | 关键词章节号 |
| Q028 | [4, 275] | [85, 85] | 8.3.5 | 关键词异常，按产物正文逐题核对 |
| Q029 | [8, 272] | [85, 85] | 8.3.5 | 题干 token 重定向 |
| Q030 | [8, 272] | [85, 85] | 8.3.5 | 题干 token 重定向 |
| Q031 | [7, 288] | [47, 48] | 6.2.4 | 关键词章节号 |
| Q032 | [7, 289] | [47, 48] | 6.2.4 | 关键词章节号 |
| Q033 | [7, 289] | [56, 56] | 6.3.8 | 关键词章节号 |
| Q034 | [7, 289] | [56, 56] | 6.3.8 | 关键词章节号 |
| Q035 | [7, 289] | [56, 56] | 6.3.7 | 关键词章节号 |
| Q036 | [7, 289] | [67, 67] | 7.3.3 | 关键词章节号 |
| Q037 | [7, 288] | [157, 159] | 10.30 | 题干 token 重定向 |
| Q038 | [7, 288] | [127, 127] | 10.6 | 题干 token 重定向 |
| Q039 | [7, 288] | [129, 129] | 10.8 | 题干 token 重定向 |
| Q040 | [46, 281] | [135, 136] | 10.13 | 题干 token 重定向 |
| Q041 | [7, 288] | [46, 47] | 6.2.1 | 关键词章节号 |
| Q042 | [7, 288] | [148, 148] | 10.22 | 关键词章节号 |
| Q043 | [7, 288] | [52, 54] | 6.3.4 | 题干 token 重定向 |
| Q044 | [7, 288] | [154, 155] | 10.27 | 题干 token 重定向 |
| Q045 | [7, 288] | [150, 151] | 10.24 | 关键词章节号 |
| Q046 | [7, 289] | [63, 64] | 7.2.3.2 | 关键词章节号 |
| Q047 | [8, 272] | [30, 30] | 5.1.4.3 | 关键词章节号 |
| Q048 | [8, 275] | [101, 102] | 9.3.3.2 | 关键词章节号 |
| Q049 | [3, 272] | [76, 78] | 8.2.4 | 题干 token 重定向 |
| Q050 | [3, 275] | [94, 96] | 9.2.4 | 题干 token 重定向 |
| Q051 | [8, 272] | [82, 83] | 8.3.3.1 | 关键词章节号 |
| Q052 | [9, 197] | [191, 191] | 12.3.1 | 关键词章节号 |
| Q053 | [28, 230] | [130, 132] | 10.10 | 题干 token 重定向 |
| Q054 | [56, 270] | [132, 133] | 10.11 | 题干 token 重定向 |
| Q055 | [30, 156] | [124, 125] | 10.4 | 题干 token 重定向 |
| Q056 | [61, 163] | [127, 129] | 10.7 | 题干 token 重定向 |
| Q057 | [25, 256] | [129, 129] | 10.8 | 关键词章节号 |
| Q058 | [31, 161] | [139, 140] | 10.16 | 关键词章节号 |
| Q059 | [1, 275] | [140, 142] | 10.17 | 关键词异常，按产物正文逐题核对 |
| Q060 | [1, 145] | [142, 145] | 10.18 | 关键词异常，按产物正文逐题核对 |
| Q061 | [17, 278] | [129, 130] | 10.9 | 题干 token 重定向 |
| Q062 | [17, 278] | [159, 160] | 10.31 | 题干 token 重定向 |
| Q063 | [28, 196] | [163, 163] | 10.35 | 关键词章节号 |
| Q064 | [17, 278] | [156, 157] | 10.29 | 题干 token 重定向 |
| Q065 | [81, 161] | [160, 161] | 10.32 | 题干 token 重定向 |
| Q066 | [100, 150] | [148, 150] | 10.23 | 题干 token 重定向 |
| Q067 | [26, 275] | [34, 38] | 5.3 | 关键词章节号 |
| Q068 | [280, 281] | [280, 281] | 25.4.1 | 关键词章节号 |
| Q069 | 248 | [248, 248] | 20.1 | 关键词章节号 |
| Q070 | [172, 173] | [172, 173] | 11.3.2 | 关键词章节号 |
| Q071 | 289 | [289, 289] | 27.3 | 关键词章节号 |
| Q072 | [26, 235] | [39, 43] | 5.5 | 题干 token 重定向 |
| Q073 | 248 | [248, 248] | 20.1 | 关键词章节号 |
| Q074 | [26, 230] | [26, 28] | 5.1.2 | 题干 token 重定向 |
| Q075 | [26, 263] | [26, 28] | 5.1.2 | 题干 token 重定向 |
| Q076 | [26, 67] | [26, 28] | 5.1.2 | 题干 token 重定向 |
| Q077 | [26, 193] | [26, 28] | 5.1.2 | 题干 token 重定向 |
| Q078 | [26, 263] | [26, 28] | 5.1.2 | 题干 token 重定向 |
| Q079 | [26, 163] | [26, 28] | 5.1.2 | 题干 token 重定向 |
| Q080 | [26, 163] | [26, 28] | 5.1.2 | 题干 token 重定向 |
| Q081 | [26, 99] | [26, 28] | 5.1.2 | 题干 token 重定向 |
| Q082 | [26, 193] | [193, 193] | 12.3.3 | 关键词章节号 |
| Q083 | [26, 263] | [26, 28] | 5.1.2 | 题干 token 重定向 |
| Q084 | [26, 260] | [26, 28] | 5.1.2 | 题干 token 重定向 |
| Q085 | [3, 272] | [86, 86] | 8.3.8 | 关键词章节号 |
| Q086 | [3, 272] | [81, 81] | 8.3.2 | 关键词章节号 |
| Q087 | [3, 272] | [86, 86] | 8.3.7 | 题干 token 重定向 |
| Q088 | [8, 288] | [193, 193] | 12.3.3 | 关键词章节号 |
| Q089 | [8, 272] | [79, 80] | 8.2.8 | 题干 token 重定向 |
| Q090 | [8, 272] | [196, 197] | 12.3.5 | 关键词章节号 |
| Q091 | [8, 272] | [86, 87] | 8.3.9 | 题干 token 重定向 |
| Q092 | [3, 275] | [107, 107] | 9.3.8 | 关键词章节号 |
| Q093 | [3, 275] | [94, 94] | 9.2.2 | 题干 token 重定向 |
| Q094 | [3, 275] | [107, 107] | 9.3.7 | 题干 token 重定向 |
| Q095 | [8, 275] | [108, 108] | 9.3.10.1 | 关键词章节号 |
| Q096 | [8, 275] | [108, 109] | 9.3.10.2 | 关键词章节号 |
| Q097 | 276 | [276, 276] | 24.2 | 关键词章节号 |
| Q098 | [4, 6] | [4, 6] | 1.5 | 关键词章节号 |
| Q099 | [172, 173] | [172, 173] | 11.3.2 | 关键词章节号 |
| Q100 | [173, 277] | [276, 276] | 24.2 | 关键词章节号 |
| Q101 | [12, 246] | [172, 173] | 11.3.2 | 关键词章节号 |
| Q102 | [178, 179] | [178, 179] | 11.6.1 | 关键词章节号 |
| Q103 | [178, 179] | [178, 179] | 11.6.1 | 关键词章节号 |
| Q104 | [17, 272] | [18, 21] | 4.1.1 | 题干 token 重定向 |
| Q105 | [12, 178] | [173, 177] | 11.4.1 | 题干 token 重定向 |
| Q106 | [23, 276] | [23, 25] | 4.2.5 | 题干 token 重定向 |
| Q107 | 22 | [22, 22] | 4.2.1 | 关键词章节号 |
| Q108 | [22, 23] | [22, 22] | 4.2.1 | 关键词章节号 |
| Q109 | [23, 272] | [23, 23] | 4.2.4 | 关键词章节号 |
| Q110 | [12, 15] | [12, 15] | 3.2 | 关键词章节号 |
| Q111 | [172, 268] | [172, 173] | 11.3.2 | 关键词章节号 |
| Q112 | [23, 287] | [276, 276] | 24.2 | 关键词章节号 |
| Q113 | [275, 278] | [276, 276] | 24.2 | 关键词章节号 |
| Q114 | 248 | [248, 248] | 20.1 | 关键词章节号 |
| Q115 | [173, 289] | [289, 289] | 27.3 | 关键词章节号 |
| Q116 | [26, 275] | [34, 38] | 5.3 | 关键词章节号 |
| Q117 | [38, 235] | [39, 40] | 5.5.2 | 关键词章节号 |
| Q118 | [7, 288] | [58, 59] | 6.3.12 | 关键词章节号 |
| Q119 | [1, 270] | [157, 159] | 10.30 | 关键词异常，按产物正文逐题核对 |
| Q120 | [52, 179] | [159, 160] | 10.31 | 题干 token 重定向 |

## 关键词异常题目

以下 6 题的 `section_keyword` 是单字符数字（`"5"` / `"1"`），无法定位章节，
按产物正文逐题核对后由脚本内 `OVERRIDES` 指定：

| question_id | 原关键词 | 指定章节 | 依据 |
|---|---|---|---|
| Q021 | `5` | 9.3.5.7 SUBSCRIPTION_MATCHED Status | 题干 `on_subscription_matched()` 的判定依据即该状态（印刷页 106-107） |
| Q023 | `5` | 9.3.5.2 LIVELINESS_CHANGED Status | 题干 `on_liveliness_changed()`（印刷页 105） |
| Q028 | `5` | 8.3.5 关于DataWriter的Status | 题干 `on_publication_matched()`（印刷页 85-86）；产物无 8.3.5.4 子节，取父节 |
| Q059 | `1` | 10.17 PartitionQosPolicy | 题干 `PartitionQosPolicy`（印刷页 140-142） |
| Q060 | `1` | 10.18 PresentationQosPolicy | 题干 `PresentationQosPolicy`（印刷页 142-145） |
| Q119 | `1` | 10.30 TransportConfigQosPolicy | 题干 `TransportConfigQosPolicy`（印刷页 157-159） |

## 关键词重定向

原区间是整个用书（`[7, 288]` 一类），任何术语都"落在标注页内"，所以 `section_keyword`
指错章节也查不出来。收紧到章节级后 `scripts/audit_annotations.py` 的
`QUESTION_TOKEN_OFF_PAGE` 才能暴露"题干的技术术语不在标注页附近"的题目——
共 43 题。逐题读题干并在产物里定位真正的答案章节后，由脚本内
`RETARGETS` 改正；每条都带可机检证据，证据不成立脚本直接报错（`_verify_retargets`）：

- `title_id`：证据串是目标章节标题里的标识符，且**全手册只有该标题含它**；
- `text_token`：证据串出现在目标章节的正文里（说明该页区间确实在讲这件事）。

| question_id | 原关键词 | 新章节 | 新区间 | 证据（机检） | 依据 |
|---|---|---|---|---|---|
| Q008 | `9.3.10.1 使用read()和take()访问数据` | 9.3.10.7 read_w_condition()和take_w_condition() | [113, 114] | title_id: `read_w_condition` | read_w_condition() 的参数在 9.3.10.7；原标注 9.3.10.1 只讲 read()/take() |
| Q012 | `9.3.11.1 样本状态(Sample States)` | 5.5.5 ReadConditions | [41, 41] | text_token: `create_readcondition` | create_readcondition()/SampleStateMask 在 5.5.5；原标注只覆盖样本状态枚举 |
| Q015 | `12.3.3 writer()阻塞时间` | 8.2.8 Publisher的其他操作 | [79, 80] | text_token: `wait_for_acknowledgments` | wait_for_acknowledgments() 的返回码在 8.2.8 表；原标注是 writer() 阻塞时间 |
| Q018 | `9.2.6 关于Subscriber的Status` | 5.3 Listener | [34, 38] | text_token: `on_data_available` | on_data_available() 回调语义在 5.3 Listener；原标注是 Subscriber 的 Status |
| Q029 | `9.3.5.7 SUBSCRIPTION_MATCHED Status` | 8.3.5 关于DataWriter的Status | [85, 85] | text_token: `on_offered_deadline_missed` | 题干是 DataWriter 回调，原标注误抄了 DataReader 的 Status 小节 |
| Q030 | `9.3.5.4 REQUESTED_INCOMPATIBLE_QOS Status` | 8.3.5 关于DataWriter的Status | [85, 85] | text_token: `on_offered_incompatible_qos` | 题干是 DataWriter 回调，原标注误抄了 DataReader 的 Status 小节 |
| Q037 | `10.36 TransportPriorityQosPolicy` | 10.30 TransportConfigQosPolicy | [157, 159] | title_id: `transportconfigqospolicy` | 原标注 10.36 是 TransportPriorityQosPolicy，与题干仅一词之差 |
| Q038 | `23.1 配置说明` | 10.6 DiscoveryConfigQosPolicy(DDS Extension) | [127, 127] | title_id: `discoveryconfigqospolicy` | DiscoveryConfigQosPolicy 章节；原标注 23.1 只是配置说明 |
| Q039 | `6.2.1 DomainParticipantFactory的QoS策略` | 10.8 EntityFactoryQosPolicy | [129, 129] | title_id: `entityfactoryqospolicy` | EntityFactoryQosPolicy 章节（含 autoenable_created_entities 字段） |
| Q040 | `25.4.1 日志QoS` | 10.13 LogQosPolicy | [135, 136] | title_id: `logqospolicy` | LogQosPolicy 章节；原标注 25.4.1 是日志 QoS 的使用说明 |
| Q043 | `6.3.12 其他DomainParticipant操作` | 6.3.4 设置DomainParticipant的QoS策略 | [52, 54] | text_token: `rtps_message_little_endian` | 该字段属 DomainParticipant 的 QoS 设置（6.3.4） |
| Q044 | `6.2.1 DomainParticipantFactory的QoS策略` | 10.27 ThreadCoreAffinityQosPolicy(DDS Extension) | [154, 155] | title_id: `threadcoreaffinityqospolicy` | ThreadCoreAffinityQosPolicy 章节；原标注 6.2.1 是工厂 QoS 设置位置 |
| Q049 | `5.1.4.3 在创建实体时设置QoS策略` | 8.2.4 设置Publisher的QoS策略 | [76, 78] | text_token: `publisherqos` | PublisherQos 成员清单在 8.2.4；原标注只讲何时设置 QoS |
| Q050 | `10.34 DurabilityServiceQosPolicy` | 9.2.4 设置Subscriber的QoS策略 | [94, 96] | text_token: `subscriberqos` | SubscriberQos 成员清单在 9.2.4；原标注是 DurabilityServiceQosPolicy |
| Q053 | `10.34 DurabilityServiceQosPolicy` | 10.10 HistoryQosPolicy | [130, 132] | title_id: `historyqospolicy` | HistoryQosPolicy 章节；原标注是 DurabilityServiceQosPolicy |
| Q054 | `10.34 DurabilityServiceQosPolicy` | 10.11 LifespanQosPolicy | [132, 133] | title_id: `lifespanqospolicy` | LifespanQosPolicy 章节；原标注是 DurabilityServiceQosPolicy |
| Q055 | `9.3.5.3 REQUESTED_DEADLINE_MISSED Status` | 10.4 DeadlineQosPolicy | [124, 125] | title_id: `deadlineqospolicy` | DeadlineQosPolicy 章节；原标注是 REQUESTED_DEADLINE_MISSED Status |
| Q056 | `10.34 DurabilityServiceQosPolicy` | 10.7 DurabilityQosPolicy | [127, 129] | title_id: `durabilityqospolicy` | DurabilityQosPolicy 章节；原标注是 DurabilityServiceQosPolicy |
| Q061 | `23.1 配置说明` | 10.9 GroupDataQosPolicy | [129, 130] | title_id: `groupdataqospolicy` | GroupDataQosPolicy 章节；原标注 23.1 只是配置说明 |
| Q062 | `23.1 配置说明` | 10.31 UserDataQosPolicy | [159, 160] | title_id: `userdataqospolicy` | UserDataQosPolicy 章节；原标注 23.1 只是配置说明 |
| Q064 | `7.2.3.2 在创建Topic后配置Qos策略` | 10.29 TopicDataQosPolicy | [156, 157] | title_id: `topicdataqospolicy` | TopicDataQosPolicy 章节；原标注 7.2.3.2 是创建 Topic 后配 QoS |
| Q065 | `10.12 LivelinessQosPolicy` | 10.32 WriterDataLifecycleQosPolicy | [160, 161] | title_id: `writerdatalifecycleqospolicy` | WriterDataLifecycleQosPolicy 章节；原标注 10.12 是 LivelinessQosPolicy |
| Q066 | `10.12 LivelinessQosPolicy` | 10.23 ReaderDataLifecycleQosPolicy | [148, 150] | title_id: `readerdatalifecycleqospolicy` | ReaderDataLifecycleQosPolicy 章节；原标注 10.12 是 LivelinessQosPolicy |
| Q072 | `11.3.2 使用zrddsgen编译器` | 5.5 Condition与WaitSets | [39, 43] | text_token: `waitset` | Condition 与 WaitSets 章节；原标注 11.3.2 是 zrddsgen 编译器 |
| Q074 | `11.6.1 ZRDDS的头文件` | 5.1.2 使能实体 | [26, 28] | text_token: `dds_retcode_error` | 手册唯一的 DDS_RETCODE_* 清单（表5-2）在 5.1.2；原标注与错误码无关 |
| Q075 | `23.1 配置说明` | 5.1.2 使能实体 | [26, 28] | text_token: `dds_retcode_bad_parameter` | 手册唯一的 DDS_RETCODE_* 清单（表5-2）在 5.1.2；原标注与错误码无关 |
| Q076 | `7.3.3 删除ContentFilteredTopic` | 5.1.2 使能实体 | [26, 28] | text_token: `dds_retcode_already_deleted` | 手册唯一的 DDS_RETCODE_* 清单（表5-2）在 5.1.2；原标注与错误码无关 |
| Q077 | `12.3.3 writer()阻塞时间` | 5.1.2 使能实体 | [26, 28] | text_token: `dds_retcode_out_of_resources` | 手册唯一的 DDS_RETCODE_* 清单（表5-2）在 5.1.2；原标注与错误码无关 |
| Q078 | `23.1 配置说明` | 5.1.2 使能实体 | [26, 28] | text_token: `dds_retcode_not_enabled` | 手册唯一的 DDS_RETCODE_* 清单（表5-2）在 5.1.2；原标注与错误码无关 |
| Q079 | `10.34 DurabilityServiceQosPolicy` | 5.1.2 使能实体 | [26, 28] | text_token: `dds_retcode_immutable_policy` | 手册唯一的 DDS_RETCODE_* 清单（表5-2）在 5.1.2；原标注与错误码无关 |
| Q080 | `10.34 DurabilityServiceQosPolicy` | 5.1.2 使能实体 | [26, 28] | text_token: `dds_retcode_inconsistent` | 手册唯一的 DDS_RETCODE_* 清单（表5-2）在 5.1.2；原标注与错误码无关 |
| Q081 | `9.2.7 获取Subscriber的关联实体` | 5.1.2 使能实体 | [26, 28] | text_token: `dds_retcode_precondition_not_met` | 手册唯一的 DDS_RETCODE_* 清单（表5-2）在 5.1.2；原标注与错误码无关 |
| Q083 | `23.1 配置说明` | 5.1.2 使能实体 | [26, 28] | text_token: `dds_retcode_illegal_operation` | 手册唯一的 DDS_RETCODE_* 清单（表5-2）在 5.1.2；原标注与错误码无关 |
| Q084 | `21.5 数据封装内容配置模块` | 5.1.2 使能实体 | [26, 28] | text_token: `dds_retcode_no_data` | 手册唯一的 DDS_RETCODE_* 清单（表5-2）在 5.1.2；原标注与错误码无关 |
| Q087 | `8.2.3 删除Publisher的所有子实体` | 8.3.7 获取DataWriter的关联实体 | [86, 86] | text_token: `get_publisher` | get_publisher() 在 8.3.7 获取 DataWriter 的关联实体；原标注是删除子实体 |
| Q089 | `12.3.3 writer()阻塞时间` | 8.2.8 Publisher的其他操作 | [79, 80] | text_token: `write_w_timestamp` | write_w_timestamp() 在 8.2.8 的表里；原标注是 writer() 的阻塞时间 |
| Q091 | `12.3.5 实例管理` | 8.3.9 实例管理 | [86, 87] | text_token: `unregister_instance` | unregister_instance() 属 DataWriter 实例管理（8.3.9） |
| Q093 | `9.3.2 删除DataReader` | 9.2.2 删除Subscriber | [94, 94] | text_token: `delete_datareader` | delete_datareader() 是 Subscriber 的操作（9.2.2）；原标注是 DataReader 侧的删除 |
| Q094 | `9.2.3 删除Subscriber的所有子实体` | 9.3.7 获取DataReader的关联实体 | [107, 107] | text_token: `get_subscriber` | get_subscriber() 在 9.3.7 获取 DataReader 的关联实体；原标注是删除子实体 |
| Q104 | `7.3.5.6 序列` | 4.1.1 sequence | [18, 21] | text_token: `maximum` | sequence 的 length/maximum 字段在 4.1.1；原标注 7.3.5.6 是 IDL 里的序列写法 |
| Q105 | `3.2 编译IDL文件` | 11.4.1 使用Visual Studio 2008\2010\2013创建工程 | [173, 177] | title_id: `visual` | Visual Studio 建工程章节；原标注 3.2 是编译 IDL 文件 |
| Q106 | `11.3.2 使用zrddsgen编译器` | 4.2.5 编译器选项 | [23, 25] | text_token: `eclipse` | Linux/Eclipse 编译与 -java_package 选项在 4.2.5；原标注是 zrddsgen 编译器 |
| Q120 | `11.6.1 ZRDDS的头文件` | 10.31 UserDataQosPolicy | [159, 160] | title_id: `userdataqospolicy` | UserDataQosPolicy 章节；原标注 11.6.1 是头文件说明 |

## 遗留问题

### 1. 仍被判为 `QUESTION_TOKEN_OFF_PAGE` 的 4 题（审计口径的假阳性）

| question_id | 章节 | 页区间 | 说明 |
|---|---|---|---|
| Q018 | 5.3 Listener | 34-38 | 回调语义在 5.3（5.3.6「Listener 的使用限制」正是作答处），但题干追问的
  `create_datawriter()` 只出现在 25/26/29/30/64/73 页，任一章节都无法同时容纳两个 token |
| Q026 | 9.3.5.5 SAMPLE_LOST Status | 106-106 | 题干 `samplestatemask` 的说明在 5.5.5 ReadConditions 与
  9.3.10.3-9.3.10.7 的读取接口，与回调 `on_sample_lost` 不在同一章节；
  当前标注是回调对应的 Status，故不改 |
| Q065 | 10.32 WriterDataLifecycleQosPolicy | 160-161 | 策略语义在 10.32，但 `writer_data_lifecycle`
  字段名只出现在 81-84 页的 DataWriter QoS 设置里 |
| Q066 | 10.23 ReaderDataLifecycleQosPolicy | 148-150 | 同上，`reader_data_lifecycle` 字段名只在
  100-103 页 |

这 4 题的标注本身正确（逐题读过产物正文），是审计的"题干 token 必须落在标注页 ±2 页内"
启发式不适用于跨章节提问：题干同时问两件事，第一件的 token 在标注页内，第二件只在别章节
出现。建议审计侧为这类题加白名单，或把题干拆成单点问题。

Q112 曾以同一方式判为离页（手册写 `licence`、题干写 `license`，拼写变体）——
该题已由问题集侧改用手册写法消解，见文末「后续修订」。

### 2. 问题集侧缺陷（改标注无法解决）

Q021 / Q023 / Q028 题干中的字段名 `subscriptionMatched` / `livelinessChanged` /
`publicationMatched` 在手册全文零命中——手册只写 `on_*_matched()` 回调与
`*_MATCHED Status` 状态。`make audit` 会将这三题判为 `QUESTION_TOKEN_ABSENT`
（按审计口径应转拒答集）。这不属区间收窄范围，需问题集负责人改写成手册术语，
或明确移入拒答案例集（**2026-09-16 已按手册写法修正**，见文末「后续修订」）。

## 校验

同一份 `scripts/audit_annotations.py`（判定口径不变，只换被检数据集）复跑三种状态：

| 指标 | 上游基线（宽区间 + 修订前问题集） | 宽区间 + 已修问题集 | 本版本（收窄 + 已修问题集） |
|---|---|---|---|
| 判定 | blocked | pass | blocked |
| QUESTION_TOKEN_OFF_PAGE（阻断） | 0 | 0 | **4** |
| QUESTION_TOKEN_ABSENT（阻断） | 3 | 0 | 0 |
| NO_TOKEN_PROBE（非阻断指纹） | 13 | 13 | 13 |
| CIRCULAR_TOP1（非阻断指纹） | 4 | 4 | 0 |

命令（在仓库根目录执行）：

```bash
python scripts/audit_annotations.py --out-prefix evaluation/reports/annotation_audit
python scripts/audit_annotations.py --expected evaluation/datasets/expected_sources_pre_narrow.jsonl \
    --out-prefix evaluation/reports/annotation_audit_before
```

报告：`evaluation/reports/annotation_audit_before.*`（宽区间 + 已修问题集，pass）、
`evaluation/reports/annotation_audit.*`（本版本，blocked）；上游基线那一列可用
`git show origin/develop:evaluation/datasets/{questions,expected_sources}.jsonl` 复跑。
`QUESTION_TOKEN_OFF_PAGE` 在宽区间下恒为 0 不是"没问题"，而是整本书的区间把什么问题都
盖住了——这正是本报告存在的意义：收窄后它才第一次指出"这一页答不了这一题"。

- `python -m pytest tests/ -q`（本机 CPython 3.11.9）：29 failed / 383 passed / 3 skipped / 5 errors。
  其中 32 项（`test_html_loader` 9 + `test_semantic_hybrid` 9 + `test_chunking_defects` 7 +
  `test_multi_source_ingest` 7）是同一条 `ValueError: Missing required metadata fields`，
  根因在 `data_pipeline/metadata.py:140-145`：必填字段校验写成列表推导式内的 `locals()`
  判断，CPython ≤3.12 的推导式有独立作用域 → 11 个必填字段被整串误判缺失（3.13 起推导式
  内联，问题自消）。属 `data_pipeline/`（本报告范围外）的既有缺陷，与数据集改动无关。
- `python -m pytest tests/unit/test_run_experiment.py tests/unit/test_audit_annotations.py -q`：
  61 passed / 2 failed（`rank_bm25`/重排模型缺依赖、`data/indexes/` 未构建，环境问题）。
- 消费本数据集的套件（`test_run_experiment / test_audit_annotations / test_abstention /
  test_real_error_cases / test_run_regression`）：109 passed / 2 failed（同上，环境问题）。

## 后续修订（2026-09-16）

「遗留问题」描述的是修订前的状态。当日做了两件事，一件在本报告范围内，一件不在：

- **§2 问题集侧缺陷（已修，属 `evaluation/`）**：Q021/Q023/Q028 题干改用手册实际写法
  （`subscription_matched` / `liveliness_changed` / `publication_matched`），
  Q112 的 `License` 改用手册写法 `Licence` → `QUESTION_TOKEN_ABSENT` 3 → 0，
  Q112 也不再被判 `QUESTION_TOKEN_OFF_PAGE`（5 → 4 题）。
- **§1 跨章节题（未动，落在 `scripts/`）**：曾以在 `scripts/audit_annotations.py` 增加
  非阻断判定码 `QUESTION_TOKEN_CROSS_CHAPTER`（只有题干**全部** token 离页才判阻断）
  的方式来消掉这 4 题。该改动属审计口径变更、落在 `scripts/`（成员 D 的目录），
  按本周「只改 `/web` 与 `/evaluation`」的范围约束**已撤回**，故当前判定仍是 blocked。

复跑（`python scripts/audit_annotations.py --out-prefix evaluation/reports/annotation_audit`）：

| 指标 | 本报告（修订前） | 现在 |
|---|---|---|
| 判定 | blocked | blocked |
| QUESTION_TOKEN_OFF_PAGE（阻断） | 5 | 4 |
| QUESTION_TOKEN_ABSENT（阻断） | 3 | 0 |
| NO_TOKEN_PROBE（非阻断指纹） | 13 | 13 |
| CIRCULAR_TOP1（非阻断指纹） | 4 | 0 |

阻断项 7 → 4，剩下的 4 项见 §1（4 题都是"一题两问"的假阳性，标注本身正确）。
要开指标闸门（`run_regression --with-metrics`），仍需 D 在 `scripts/audit_annotations.py`
定口径（白名单或非阻断码）并由 B 会签；在那之前 `final_v1` 的 `expected_sources`
保持 `null`，正式指标不解冻。本报告的改动全部落在 `evaluation/` 内，与 `/web` 无关。
