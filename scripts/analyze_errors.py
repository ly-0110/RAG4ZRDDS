#!/usr/bin/env python3
"""
问题集标注错误位置分析
"""

import json

# 检查 QoS 策略题的页码标注
with open('evaluation/datasets/questions.json', 'r', encoding='utf-8') as f:
    questions = json.load(f)

print('=' * 60)
print('QoS 策略题页码标注错误分析')
print('=' * 60)

# 找出 QoS 相关的问题
qos_questions = [q for q in questions if 'QoS' in q['question']]

print(f'\n共找到 {len(qos_questions)} 个 QoS 相关问题:')
for q in qos_questions:
    print(f'\n问题 ID: {q["id"]}')
    print(f'问题内容：{q["question"][:80]}...')
    source = q.get('expected_source', {})
    print(f'当前标注页码：{source.get("page_print", [])}')
    print(f'Section 关键词：{source.get("section_keyword", "")}')

print('\n' + '=' * 60)
print('错误位置分析:')
print('=' * 60)
print('\n1. Q006 - QoS 策略配置文件')
print('   当前标注页码：[29] (入口页)')
print('   正确页码应为：[285, 292] (操作页)')
print('   错误原因：标注了章节入口页而非具体操作页')

print('\n2. Q009 - XML 配置实体 QoS')
print('   当前标注页码：[42] (入口页)')
print('   正确页码应为：[309, 316] (操作页)')
print('   错误原因：标注了章节入口页而非具体操作页')

print('\n' + '=' * 60)
print('其他系统性偏差:')
print('=' * 60)
print('\n- 67 题 keyword 为函数名在正文，标题级无法判定')
print('  示例："connect()"、"enable()"等函数名出现在多处位置')
