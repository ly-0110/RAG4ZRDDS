# 人工抽检 30 题（指南 §9.3）

- 抽样：30 题，固定种子 0，确定性可复现
- 检查人：成员 C　·　日期：待填
- 六问逐题勾选；任一问题答「否」需在备注说明原因与处置。

| 题号 | 问题 | 是否回答了问题 | 技术事实是否正确 | 是否有文档依据 | Citation 是否准确 | 是否出现虚构 API | 是否混用了版本 |
|---|---|---|---|---|---|---|
| Q006 | 如何在创建 DataWriter 时传入自定义的 QoS 策略？请写出函数原型。 |  |  |  |  |  |  |
| Q013 | 如何获取 DomainParticipant 的 StatusCondition？为什么要使用 StatusCondition 而不是直接调用 Listener？ |  |  |  |  |  |  |
| Q018 | DataReaderListener 的 on_data_available()回调函数的作用是什么？该函数能否调用 create_datawriter()？为什么？ |  |  |  |  |  |  |
| Q019 | DataWriter 的 on_liveliness_lost()回调函数在什么情况下会被触发？触发后 DataWriter 处于什么状态？ |  |  |  |  |  |  |
| Q028 | DataWriter 的 on_publication_matched()回调函数被触发时，该 DataWriter 处于什么状态？该 Listener 的 publication_matched 字段是什么类型？ |  |  |  |  |  |  |
| Q033 | Topic 的 create_topic()函数中，如果返回 NULL 表示什么？可能的原因有哪些？ |  |  |  |  |  |  |
| Q034 | 如何查找同一域下的 Topic？find_topic()函数的返回类型是什么？ |  |  |  |  |  |  |
| Q037 | 如何配置 DomainParticipant 的 TransportConfigQosPolicy 以指定接收地址？该配置的 QoS 策略类型是什么？ |  |  |  |  |  |  |
| Q039 | 如何配置 DomainParticipant 的 EntityFactoryQosPolicy？该配置中的 autoenable_created_entities 字段的作用是什么？ |  |  |  |  |  |  |
| Q040 | 如何配置 LogQosPolicy 以控制 ZRDDS 日志级别？日志级别有哪些可选值？ |  |  |  |  |  |  |
| Q046 | 如何设置 Topic 的 QoS 策略？TopicQos 结构中包含哪些成员？ |  |  |  |  |  |  |
| Q050 | 如何设置 Subscriber 的 QoS 策略？SubscriberQos 结构中包含哪些成员？ |  |  |  |  |  |  |
| Q052 | 如何设置 ReliabilityQosPolicy 的 kind 字段？该字段有哪些可选值？分别代表什么可靠性策略？ |  |  |  |  |  |  |
| Q054 | 如何设置 LifespanQosPolicy 的 duration 字段？该配置对过期数据处理的作用是什么？ |  |  |  |  |  |  |
| Q062 | 如何设置 UserDataQosPolicy 的 value 字段？该配置对附加信息的作用是什么？最大长度是多少？ |  |  |  |  |  |  |
| Q063 | 如何设置 ResourceLimitsQosPolicy 的 max_samples？该配置对系统内存的作用是什么？ |  |  |  |  |  |  |
| Q065 | 如何设置 WriterDataLifecycleQosPolicy 的 writer_data_lifecycle？该配置对数据实例生命周期管理的作用是什么？ |  |  |  |  |  |  |
| Q066 | 如何设置 ReaderDataLifecycleQosPolicy 的 reader_data_lifecycle？该配置对数据实例生命周期管理的作用是什么？ |  |  |  |  |  |  |
| Q069 | 如何配置 ZRDDS 日志风格？有哪些可选风格？如何使用 XML 配置实体 QoS？ |  |  |  |  |  |  |
| Q075 | 如何区分 DDS_RETCODE_BAD_PARAMETER 和 DDS_RETCODE_UNSUPPORTED？两者的返回场景有什么区别？ |  |  |  |  |  |  |
| Q078 | 如何处理 DDS_RETCODE_NOT_ENABLED 错误？该错误表示什么含义？如何使能实体？ |  |  |  |  |  |  |
| Q080 | 如何处理 DDS_RETCODE_INCONSISTENT 错误？该错误表示什么含义？如何确保 QoS 策略相容性？ |  |  |  |  |  |  |
| Q091 | 如何使用 DataWriter 的 unregister_instance()函数注销实例？该函数在什么情况下会失败？ |  |  |  |  |  |  |
| Q097 | 如何获取 ZRDDS 版本信息？用户手册中提到的版本号是什么？该版本编译日期是什么时候？ |  |  |  |  |  |  |
| Q098 | ZRDDS 遵循的 DDS 规范版本是什么？RTPS 规范版本是多少？这些规范的 URL 是什么？ |  |  |  |  |  |  |
| Q101 | 如何生成 DDS 编译器 zrddsgen.exe？编译后生成的文件有哪些？C/C++后缀名有什么区别？ |  |  |  |  |  |  |
| Q102 | ZRDDS 的 DDS 编译器版本是多少？如何查看编译器的帮助信息？ |  |  |  |  |  |  |
| Q107 | @key 标注在 IDL 文件中的作用是什么？标注后面能否跟其他注释？为什么？ |  |  |  |  |  |  |
| Q109 | @spare 标注的作用是什么？稀疏数据类型在什么 Extensibility 配置下生效？支持的编程语言有哪些？ |  |  |  |  |  |  |
| Q114 | 如何管理 ZRDDS 内部 QoS 仓库？QoS 设置相关接口有哪些？如何使用 XML 示例配置实体 QoS？ |  |  |  |  |  |  |

> 由 `scripts/sample_manual_review.py` 生成。勾选后回填本文件作为人工评测证据。
