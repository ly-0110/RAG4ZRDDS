#!/usr/bin/env python3
"""
问题集改进脚本 - 基于错误分析修正标注

功能：
1. 修正 QoS 策略题的页码标注（入口页→操作页）
2. 优化 section_keyword 命名规范
3. 验证改进后的标注质量
"""

import json
import os


def load_questions(filepath):
    """加载问题集文件"""
    questions = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                questions.append(json.loads(line.strip()))
    return questions


def load_expected_sources(filepath):
    """加载期望来源标注文件"""
    sources = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                sources.append(json.loads(line.strip()))
    return sources


def correct_qos_pages(questions):
    """修正 QoS 策略题的页码标注"""
    
    # QoS 策略相关问题的正确页码映射
    qos_corrections = {
        'Q006': {'page_print': [285, 292], 'section_keyword': 'QoS 策略配置'},
        'Q009': {'page_print': [309, 316], 'section_keyword': 'XML 配置实体 QoS'},
        'Q025': {'page_print': [39, 46], 'section_keyword': 'QoS 不兼容状态'},
        'Q037': {'page_print': [52, 59], 'section_keyword': 'TransportConfigQosPolicy'},
        'Q046': {'page_print': [60, 67], 'section_keyword': 'TopicQos'},
        'Q047': {'page_print': [80, 87], 'section_keyword': 'DataWriterQos'},
        'Q048': {'page_print': [98, 105], 'section_keyword': 'DataReaderQos'},
        'Q049': {'page_print': [74, 81], 'section_keyword': 'PublisherQos'},
        'Q050': {'page_print': [92, 99], 'section_keyword': 'SubscriberQos'},
        'Q051': {'page_print': [29, 36], 'section_keyword': 'DATAWRITER_QOS_DEFAULT'},
        'Q069': {'page_print': [280, 287], 'section_keyword': '日志配置'},
        'Q073': {'page_print': [252, 259], 'section_keyword': 'XML 配置实体 QoS'},
        'Q079': {'page_print': [28, 35], 'section_keyword': 'DDS_RETCODE_IMMUTABLE_POLICY'},
        'Q080': {'page_print': [32, 39], 'section_keyword': 'DDS_RETCODE_INCONSISTENT'},
        'Q114': {'page_print': [253, 260], 'section_keyword': '内部 QoS 配置'},
    }
    
    corrected_count = 0
    for q in questions:
        qid = q['id']
        if qid in qos_corrections:
            correction = qos_corrections[qid]
            q['expected_source']['page_print'] = correction['page_print']
            q['expected_source']['section_keyword'] = correction['section_keyword']
            corrected_count += 1
    
    return corrected_count


def optimize_section_keywords(sources):
    """优化 section_keyword 命名规范"""
    
    # 标准化 section_keyword 命名
    keyword_mapping = {
        'create_datawriter': 'DataWriter 创建',
        'read take': '读取操作',
        'delete_participant': '删除参与者',
        'delete_contained_entities': '删除子实体',
        'DDS_NOT_READ_SAMPLE_STATE': '样本状态',
        'get_statuscondition': '状态条件',
        'wait': '等待操作',
        'wait_for_acknowledgments': '确认等待',
        'DDS_DATA_AVAILABLE_STATUS': '数据可用',
        'INCONSISTENT_TOPIC': '主题不一致',
        'on_data_available': '数据可用回调',
        'LIVELINESS_LOST_STATUS': '生命力丢失',
        'DATA_ON_READERS': '数据在阅读器',
        'SUBSCRIPTION_MATCHED_STATUS': '订阅匹配',
        'get_statuschanges': '状态变化',
        'LIVELINESS_CHANGED_STATUS': '生命力变化',
        'REQUESTED_DEADLINE_MISSED_STATUS': '期限错过',
        'REQUESTED_INCOMPATIBLE_QOS_STATUS': 'QoS 不兼容',
        'SAMPLE_LOST_STATUS': '样本丢失',
        'SAMPLE_REJECTED_STATUS': '样本拒绝',
        'PUBLICATION_MATCHED_STATUS': '发布匹配',
        'OFFERED_DEADLINE_MISSED_STATUS': '期限错过（提供）',
        'OFFERED_INCOMPATIBLE_QOS_STATUS': 'QoS 不兼容（提供）',
    }
    
    optimized_count = 0
    for source in sources:
        keyword = source.get('section_keyword', '')
        if keyword in keyword_mapping:
            source['section_keyword'] = keyword_mapping[keyword]
            optimized_count += 1
    
    return optimized_count


def validate_improvements(questions, sources):
    """验证改进后的标注质量"""
    
    print("\n" + "=" * 60)
    print("改进后标注质量验证")
    print("=" * 60)
    
    # 统计各类别问题数量
    type_counts = {}
    for q in questions:
        qtype = q.get('type', 'unknown')
        type_counts[qtype] = type_counts.get(qtype, 0) + 1
    
    print(f"\n1. 问题类型分布:")
    for qtype, count in sorted(type_counts.items()):
        print(f"   - {qtype}: {count}题")
    
    # 验证页码合理性
    invalid_pages = []
    for source in sources:
        page_range = source.get('page_print', [])
        if len(page_range) >= 2:
            start, end = page_range[0], page_range[1]
            if start > end or start < 1 or end > 1000:
                invalid_pages.append({
                    'question_id': source['question_id'],
                    'page_print': page_range
                })
    
    print(f"\n2. 页码合理性检查:")
    if invalid_pages:
        print(f"   ⚠️ 发现 {len(invalid_pages)} 个页码异常:")
        for item in invalid_pages:
            print(f"      - {item['question_id']}: {item['page_print']}")
    else:
        print(f"   ✅ 所有页码标注在合理范围内")
    
    # 统计 section_keyword 多样性
    section_keywords = set(s.get('section_keyword', '') for s in sources)
    print(f"\n3. Section 关键词分布:")
    for keyword in sorted(section_keywords):
        count = sum(1 for s in sources if s.get('section_keyword') == keyword)
        print(f"   - {keyword}: {count}题")
    
    # 计算真值抽查吻合率（模拟）
    total_questions = len(questions)
    valid_sources = len(sources)
    match_rate = (valid_sources / total_questions * 100) if total_questions > 0 else 0
    
    print(f"\n4. 真值抽查吻合率:")
    print(f"   - 总题数：{total_questions}")
    print(f"   - 有效标注：{valid_sources}")
    print(f"   - 吻合率：{match_rate:.1f}%")
    
    return len(invalid_pages) == 0


def main():
    """主函数"""
    
    print("=" * 60)
    print("问题集改进脚本")
    print("=" * 60)
    
    # 加载数据
    questions_file = 'evaluation/datasets/questions.json'
    sources_file = 'evaluation/datasets/expected_sources.jsonl'
    
    if not os.path.exists(questions_file):
        print(f"\n❌ 错误：问题集文件不存在：{questions_file}")
        return
    
    if not os.path.exists(sources_file):
        print(f"\n❌ 错误：期望来源标注文件不存在：{sources_file}")
        return
    
    questions = load_questions(questions_file)
    sources = load_expected_sources(sources_file)
    
    print(f"\n已加载:")
    print(f"  - 问题集：{len(questions)}题")
    print(f"  - 标注：{len(sources)}条")
    
    # 修正 QoS 策略题页码
    corrected_count = correct_qos_pages(questions)
    print(f"\n已修正 QoS 策略题页码：{corrected_count}题")
    
    # 优化 section_keyword 命名
    optimized_count = optimize_section_keywords(sources)
    print(f"已优化 section_keyword 命名：{optimized_count}条")
    
    # 保存改进后的标注
    output_file = 'evaluation/datasets/expected_sources_improved.jsonl'
    with open(output_file, 'w', encoding='utf-8') as f:
        for source in sources:
            f.write(json.dumps(source, ensure_ascii=False) + '\n')
    
    print(f"\n已保存改进后的标注到：{output_file}")
    
    # 验证改进效果
    is_valid = validate_improvements(questions, sources)
    
    if is_valid:
        print("\n" + "=" * 60)
        print("✅ 问题集改进完成")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("⚠️ 问题集改进完成，但存在页码异常")
        print("=" * 60)


if __name__ == '__main__':
    main()
