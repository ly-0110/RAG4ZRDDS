#!/usr/bin/env python3
"""
问题集格式修复工作流程
"""

import json
import os

# 步骤 1：诊断当前问题集格式问题
print("=" * 60)
print("步骤 1：诊断当前问题集格式问题")
print("=" * 60)

input_file = 'evaluation/datasets/questions_new.jsonl'
raw_file = 'evaluation/datasets/questions.json'

# 检查 JSONL 文件
if os.path.exists(input_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    
    print(f'\n当前 questions_new.jsonl 行数：{len(lines)}')
    if lines:
        last_id = lines[-1].split('"id": "')[1].split('",')[0]
        print(f'问题 ID 范围：Q001 ~ Q{last_id}')
else:
    print(f'\n当前 questions_new.jsonl 不存在')

# 检查原始 JSON 文件
if os.path.exists(raw_file):
    with open(raw_file, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
    
    print(f'原始 questions.json 问题总数：{len(raw_data)}')
    last_raw_id = raw_data[-1]['id']
    print(f'问题 ID 范围：Q001 ~ Q{last_raw_id}')
else:
    print(f'\n原始 questions.json 不存在')

# 诊断问题
print(f'\n[DIAGNOSTIC] 诊断结果:')
if len(lines) < len(raw_data):
    print(f'  - [WARNING] 当前 JSONL 文件只包含前{len(lines)}题（不完整）')
    print(f'  - [WARNING] 原始 JSON 文件包含{len(raw_data)}题（完整）')
    print(f'  - [WARNING] 需要重新转换完整的问题集')
else:
    print(f'  - [OK] 问题集格式完整')

print("\n" + "=" * 60)
print("步骤 2：重新转换完整的问题集")
print("=" * 60)

# 步骤 2：重新转换完整的问题集
if os.path.exists(raw_file):
    with open(raw_file, 'r', encoding='utf-8') as f_in:
        questions = json.load(f_in)
    
    # 转换为 JSONL 格式
    output_file = 'evaluation/datasets/questions_new.jsonl'
    with open(output_file, 'w', encoding='utf-8') as f_out:
        for q in questions:
            output_q = {
                'id': q.get('id', ''),
                'question': q.get('question', ''),
                'type': q.get('type', ''),
                'version': q.get('version', ''),
                'difficulty': q.get('difficulty', '')
            }
            f_out.write(json.dumps(output_q, ensure_ascii=False) + '\n')
    
    print(f'\n[OK] 已重新转换完整的问题集到 {output_file}')
    print(f'   问题总数：{len(questions)}')
    print(f'   问题 ID 范围：Q001 ~ Q{questions[-1]["id"]}')

# 步骤 3：重新提取 expected_source 并转换为 JSONL 格式
print("\n" + "=" * 60)
print("步骤 3：重新提取 expected_source 并转换为 JSONL 格式")
print("=" * 60)

if os.path.exists(raw_file):
    with open(raw_file, 'r', encoding='utf-8') as f_in:
        questions = json.load(f_in)
    
    # 提取 expected_source 并转换为 JSONL 格式
    output_file = 'evaluation/datasets/expected_sources.jsonl'
    with open(output_file, 'w', encoding='utf-8') as f_out:
        for q in questions:
            source = q.get('expected_source', {})
            annotation = {
                'question_id': q['id'],
                'source_id': source.get('source_id', 'user_manual'),
                'page_print': source.get('page_print', []),
                'section_keyword': source.get('section_keyword', '')
            }
            f_out.write(json.dumps(annotation, ensure_ascii=False) + '\n')
    
    print(f'\n[OK] 已重新提取 expected_source 并转换为 JSONL 格式')
    print(f'   标注总数：{len(questions)}')
    print(f'   输出文件：{output_file}')

# 步骤 4：验证转换结果
print("\n" + "=" * 60)
print("步骤 4：验证转换结果")
print("=" * 60)

# 检查 questions_new.jsonl
if os.path.exists(output_file):
    with open(output_file, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    
    print(f'\nquestions_new.jsonl 行数：{len(lines)}')
    if lines:
        print(f'示例问题：{json.loads(lines[0])}')

# 检查 expected_sources.jsonl
output_file = 'evaluation/datasets/expected_sources.jsonl'
if os.path.exists(output_file):
    with open(output_file, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    
    print(f'\nexpected_sources.jsonl 行数：{len(lines)}')
    if lines:
        print(f'示例标注：{json.loads(lines[0])}')

print("\n" + "=" * 60)
print("[OK] 问题集格式修复完成")
print("=" * 60)
