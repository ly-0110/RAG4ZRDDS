# 标注真值核对报告

- 结论: **blocked**（阻断项 54，缺标注 0，多余 0）
- 题量: 问题集 120 / 标注 120
- 循环论证指纹: 与 evaluation\reports\struct_v1.json top-1 页码吻合 44/120（比例 0.3667，阈值 0.9） → 未见异常

> 判据全部来自 A 的产物与章节树（分块正文、printed_page_start/end、章节标题），**不调用检索器**——所以从检索结果反推的标注骗不过它。top-1 比对只用来抓"标注=检索回显"的指纹，不当真值用。

## 逐题判定（仅列有问题的题）

| 题号 | 页码 | 关键词 | 判定 | token 实况 |
|---|---|---|---|---|
| Q005 | 58 | 6.3.12 其他DomainParticipant操作 | CIRCULAR_TOP1 | — |
| Q007 | 108 | 9.3.10.2 read()和take()的区别 | CIRCULAR_TOP1 | — |
| Q008 | 108 | 9.3.10.1 使用read()和take()访问数据 | QUESTION_TOKEN_OFF_PAGE | read_w_condition→实际在 [40, 41, 97, 98] |
| Q009 | 41 | 5.5.6 GuardConditions | CIRCULAR_TOP1 | — |
| Q010 | 51 | 6.3.3 删除所有子实体 | CIRCULAR_TOP1 | — |
| Q011 | 51 | 6.3.3 删除所有子实体 | CIRCULAR_TOP1 | — |
| Q012 | 115 | 9.3.11.1 样本状态(Sample States) | QUESTION_TOKEN_OFF_PAGE | create_readcondition→实际在 [41, 97, 98, 99] |
| Q014 | 39 | 5.5.2 WaitSet的相关操作 | CIRCULAR_TOP1 | — |
| Q015 | 193 | 12.3.3 writer()阻塞时间 | QUESTION_TOKEN_OFF_PAGE | wait_for_acknowledgments→实际在 [73, 74, 75, 76] |
| Q017 | 64 | 7.2.5 设置Topic的Listener | CIRCULAR_TOP1 | — |
| Q018 | 97 | 9.2.6 关于Subscriber的Status | QUESTION_TOKEN_OFF_PAGE | create_datawriter→实际在 [25, 26, 29, 30] |
| Q020 | 97 | 9.2.6 关于Subscriber的Status | CIRCULAR_TOP1 | — |
| Q021 | 106 | 9.3.5.7 SUBSCRIPTION_MATCHED | QUESTION_TOKEN_ABSENT, CIRCULAR_TOP1 | matched_count→全书零命中 |
| Q022 | 85 | 8.3.6 获取DataWriter的Status | CIRCULAR_TOP1 | — |
| Q023 | 104 | 9.3.5 关于DataReader的Status | QUESTION_TOKEN_ABSENT | status_kind→全书零命中 |
| Q024 | 105 | 9.3.5.3 REQUESTED_DEADLINE_M | CIRCULAR_TOP1 | — |
| Q025 | 106 | 9.3.5.4 REQUESTED_INCOMPATIB | CIRCULAR_TOP1 | — |
| Q026 | 106 | 9.3.5.5 SAMPLE_LOST Status | QUESTION_TOKEN_OFF_PAGE, CIRCULAR_TOP1 | samplestatemask→实际在 [39, 40, 41, 42] |
| Q027 | 106 | 9.3.5.5 SAMPLE_LOST Status | CIRCULAR_TOP1 | — |
| Q028 | 106 | 9.3.5.7 SUBSCRIPTION_MATCHED | QUESTION_TOKEN_ABSENT, QUESTION_TOKEN_OFF_PAGE, CIRCULAR_TOP1 | matched_count→全书零命中; on_publication_matched→实际在 [34, 35, 84, 85] |
| Q029 | 106 | 9.3.5.7 SUBSCRIPTION_MATCHED | QUESTION_TOKEN_OFF_PAGE | on_offered_deadline_missed→实际在 [34, 35, 84, 85] |
| Q030 | 106 | 9.3.5.4 REQUESTED_INCOMPATIB | QUESTION_TOKEN_OFF_PAGE, CIRCULAR_TOP1 | on_offered_incompatible_qos→实际在 [34, 35, 84, 85] |
| Q034 | 56 | 6.3.8 查找Topic | CIRCULAR_TOP1 | — |
| Q035 | 56 | 6.3.7 查找Topic Description | CIRCULAR_TOP1 | — |
| Q037 | 163 | 10.36 TransportPriorityQosPo | QUESTION_TOKEN_OFF_PAGE | transportconfigqospolicy→实际在 [52, 53, 54, 81] |
| Q038 | 263 | 23.1 配置说明 | QUESTION_TOKEN_OFF_PAGE | discoveryconfigqospolicy→实际在 [52, 53, 54, 127] |
| Q039 | 46 | 6.2.1 DomainParticipantFacto | QUESTION_TOKEN_OFF_PAGE | autoenable_created_entities→实际在 [26, 27, 28, 53] |
| Q040 | 280 | 25.4.1 日志QoS | QUESTION_TOKEN_OFF_PAGE, CIRCULAR_TOP1 | logqospolicy→实际在 [46, 47, 135, 136] |
| Q042 | 148 | 10.22 RapidIOControllerQosPo | CIRCULAR_TOP1 | — |
| Q043 | 58 | 6.3.12 其他DomainParticipant操作 | QUESTION_TOKEN_OFF_PAGE | rtps_message_little_endian→实际在 [52, 53, 54] |
| Q044 | 46 | 6.2.1 DomainParticipantFacto | QUESTION_TOKEN_OFF_PAGE | threadcoreaffinityqospolicy→实际在 [52, 53, 54, 154] |
| Q045 | 150 | 10.24 ReceiverThreadConfigQo | CIRCULAR_TOP1 | — |
| Q049 | 30 | 5.1.4.3 在创建实体时设置QoS策略 | QUESTION_TOKEN_OFF_PAGE | publisherqos→实际在 [48, 49, 50, 51] |
| Q050 | 163 | 10.34 DurabilityServiceQosPo | QUESTION_TOKEN_OFF_PAGE | subscriberqos→实际在 [26, 27, 28, 48] |
| Q051 | 82 | 8.3.3.1 创建DataWriter时配置QoS策略 | CIRCULAR_TOP1 | — |
| Q052 | 191 | 12.3.1 选择通信模型 | CIRCULAR_TOP1 | — |
| Q053 | 163 | 10.34 DurabilityServiceQosPo | QUESTION_TOKEN_OFF_PAGE | depth→实际在 [28, 29, 30, 31] |
| Q054 | 163 | 10.34 DurabilityServiceQosPo | QUESTION_TOKEN_OFF_PAGE | lifespanqospolicy→实际在 [61, 62, 63, 64] |
| Q055 | 105 | 9.3.5.3 REQUESTED_DEADLINE_M | QUESTION_TOKEN_OFF_PAGE | period→实际在 [30, 31, 32, 33] |
| Q056 | 163 | 10.34 DurabilityServiceQosPo | QUESTION_TOKEN_OFF_PAGE | durabilityqospolicy→实际在 [61, 62, 63, 64] |
| Q057 | 129 | 10.8 EntityFactoryQosPolicy | CIRCULAR_TOP1 | — |
| Q058 | 139 | 10.16 OwnershipStrengthQosPo | CIRCULAR_TOP1 | — |
| Q059 | 46 | 6.2.1 DomainParticipantFacto | QUESTION_TOKEN_ABSENT, QUESTION_TOKEN_OFF_PAGE | keyindex→全书零命中; partitionqospolicy→实际在 [76, 77, 78, 94] |
| Q060 | 263 | 23.1 配置说明 | QUESTION_TOKEN_ABSENT, QUESTION_TOKEN_OFF_PAGE | encoding_vendor_id→全书零命中; presentationqospolicy→实际在 [76, 77, 78, 87] |
| Q061 | 263 | 23.1 配置说明 | QUESTION_TOKEN_OFF_PAGE | groupdataqospolicy→实际在 [76, 77, 78, 94] |
| Q062 | 263 | 23.1 配置说明 | QUESTION_TOKEN_OFF_PAGE | userdataqospolicy→实际在 [52, 53, 54, 81] |
| Q064 | 63 | 7.2.3.2 在创建Topic后配置Qos策略 | QUESTION_TOKEN_OFF_PAGE | value→实际在 [17, 18, 19, 20] |
| Q065 | 133 | 10.12 LivelinessQosPolicy | QUESTION_TOKEN_OFF_PAGE | writerdatalifecycleqospolicy→实际在 [81, 82, 83, 84] |
| Q066 | 133 | 10.12 LivelinessQosPolicy | QUESTION_TOKEN_OFF_PAGE | readerdatalifecycleqospolicy→实际在 [100, 101, 102, 103] |
| Q067 | 34 | 5.3 Listener | CIRCULAR_TOP1 | — |
| Q068 | 280 | 25.4.1 日志QoS | NO_TOKEN_PROBE | — |
| Q069 | 248 | 20.1 XML配置说明 | NO_TOKEN_PROBE, CIRCULAR_TOP1 | — |
| Q070 | 172 | 11.3.2 使用zrddsgen编译器 | NO_TOKEN_PROBE | — |
| Q071 | 289 | 27.3 日志类型IDL文件 | NO_TOKEN_PROBE | — |
| Q072 | 172 | 11.3.2 使用zrddsgen编译器 | QUESTION_TOKEN_OFF_PAGE | condition→实际在 [26, 27, 28, 38] |
| Q073 | 248 | 20.1 XML配置说明 | NO_TOKEN_PROBE, CIRCULAR_TOP1 | — |
| Q074 | 178 | 11.6.1 ZRDDS的头文件 | QUESTION_TOKEN_OFF_PAGE | dds_retcode_error→实际在 [26, 27, 28] |
| Q075 | 263 | 23.1 配置说明 | QUESTION_TOKEN_OFF_PAGE | dds_retcode_bad_parameter→实际在 [26, 27, 28, 111] |
| Q076 | 67 | 7.3.3 删除ContentFilteredTopic | QUESTION_TOKEN_OFF_PAGE, CIRCULAR_TOP1 | dds_retcode_already_deleted→实际在 [26, 27, 28] |
| Q077 | 193 | 12.3.3 writer()阻塞时间 | QUESTION_TOKEN_OFF_PAGE, CIRCULAR_TOP1 | dds_retcode_out_of_resources→实际在 [26, 27, 28] |
| … | | | | 另有 34 题同类问题 |

## 判定码计数

- `QUESTION_TOKEN_OFF_PAGE` = 48（阻断）
- `CIRCULAR_TOP1` = 44（指纹）
- `NO_TOKEN_PROBE` = 13（指纹）
- `QUESTION_TOKEN_ABSENT` = 6（阻断）

## 闸门含义

- `blocked` / `suspect_circular` → **不得**开 `make regression REG_ARGS=--with-metrics`，指标只记不判（宁缺毋滥）。
- `pass` → 指标通道方可启用，六份 void 报告才能刷新为可引用数字。
