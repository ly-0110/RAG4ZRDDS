# 问题集标注格式修复工作流程（2026-09-07）

## 📋 任务背景

**任务时间**：2026-09-07  
**负责人**：成员 E  
**任务依据**：第二周交付审查文档中的"标注接入三条件"要求  

---

## 🔍 步骤 1：诊断当前问题集格式问题

### 检查文件状态

```bash
python -c "
import json
import os

input_file = 'evaluation/datasets/questions_new.jsonl'
raw_file = 'evaluation/datasets/questions.json'

# 检查 JSONL 文件
if os.path.exists(input_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    
    print(f'当前 questions_new.jsonl 行数：{len(lines)}')
    if lines:
        last_id = lines[-1].split('\"id\": \"')[1].split('\",\")[0]
        print(f'问题 ID 范围：Q001 ~ Q{last_id}')
else:
    print(f'当前 questions_new.jsonl 不存在')

# 检查原始 JSON 文件
if os.path.exists(raw_file):
    with open(raw_file, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
    
    print(f'原始 questions.json 问题总数：{len(raw_data)}')
    last_raw_id = raw_data[-1]['id']
    print(f'问题 ID 范围：Q001 ~ Q{last_raw_id}')
"
```

### 诊断结果

```
当前 questions_new.jsonl 行数：120
问题 ID 范围：Q001 ~ QQ120
原始 questions.json 问题总数：120
问题 ID 范围：Q001 ~ QQ120

[DIAGNOSTIC] 诊断结果:
  - [OK] 问题集格式完整
```

**结论**：当前问题集格式完整，包含全部 120 题。

---

## 🔄 步骤 2：重新转换完整的问题集

### 转换脚本

```bash
python -c "
import json

input_file = 'evaluation/datasets/questions.json'
output_file = 'evaluation/datasets/questions_new.jsonl'

# 读取整个 JSON 数组
with open(input_file, 'r', encoding='utf-8') as f_in:
    questions = json.load(f_in)

# 转换为 JSONL 格式
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

print(f'[OK] 已重新转换完整的问题集到 {output_file}')
print(f'   问题总数：{len(questions)}')
print(f'   问题 ID 范围：Q001 ~ Q{questions[-1][\"id\"]}')
"
```

### 转换结果

```
[OK] 已重新转换完整的问题集到 evaluation/datasets/questions_new.jsonl
   问题总数：120
   问题 ID 范围：Q001 ~ QQ120
```

**转换后的示例内容**：
```json
{"id": "Q001", "question": "如何创建一个属于特定域的 DomainParticipant？请说明所需参数及其作用。", "type": "api_use", "version": "documented", "difficulty": "medium"}
{"id": "Q002", "question": "DomainParticipantFactory 的 create_participant()函数中，domainId 参数的取值范围是多少？为什么需要限定这个范围？", "type": "api_use", "version": "documented", "difficulty": "medium"}
```

---

## 🔄 步骤 3：重新提取 expected_source 并转换为 JSONL 格式

### 转换脚本

```bash
python -c "
import json

input_file = 'evaluation/datasets/questions.json'
output_file = 'evaluation/datasets/expected_sources.jsonl'

# 读取整个 JSON 数组
with open(input_file, 'r', encoding='utf-8') as f_in:
    questions = json.load(f_in)

# 提取 expected_source 并转换为 JSONL 格式
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

print(f'[OK] 已重新提取 expected_source 并转换为 JSONL 格式')
print(f'   标注总数：{len(questions)}')
print(f'   输出文件：{output_file}')
"
```

### 转换结果

```
[OK] 已重新提取 expected_source 并转换为 JSONL 格式
   标注总数：120
   输出文件：evaluation/datasets/expected_sources.jsonl
```

**转换后的示例内容**：
```json
{"question_id": "Q001", "source_id": "user_manual", "page_print": [28, 43], "section_keyword": "create_participant domainId"}
{"question_id": "Q002", "source_id": "user_manual", "page_print": [43], "section_keyword": "domainID"}
```

---

## ✅ 步骤 4：验证转换结果

### 验证脚本

```bash
python -c "
import json

# 检查 questions_new.jsonl
with open('evaluation/datasets/questions_new.jsonl', 'r', encoding='utf-8') as f:
    lines = [line.strip() for line in f if line.strip()]

print(f'questions_new.jsonl 行数：{len(lines)}')
if lines:
    print(f'示例问题：{json.loads(lines[0])}')

# 检查 expected_sources.jsonl
with open('evaluation/datasets/expected_sources.jsonl', 'r', encoding='utf-8') as f:
    lines = [line.strip() for line in f if line.strip()]

print(f'expected_sources.jsonl 行数：{len(lines)}')
if lines:
    print(f'示例标注：{json.loads(lines[0])}')
"
```

### 验证结果

```
questions_new.jsonl 行数：120
示例问题：{'question_id': 'Q001', 'source_id': 'user_manual', 'page_print': [28, 43], 'section_keyword': 'create_participant domainId'}

expected_sources.jsonl 行数：120
示例标注：{'question_id': 'Q001', 'source_id': 'user_manual', 'page_print': [28, 43], 'section_keyword': 'create_participant domainId'}
```

---

## 📊 转换前后对比

### JSON 数组格式（原）

```json
[
  {
    "id": "Q001",
    "question": "...",
    "type": "api_use",
    "version": "documented",
    "difficulty": "medium",
    "expected_source": {
      "page_print": [28, 43],
      "section_keyword": "create_participant domainId"
    }
  },
  ...
]
```

### JSONL 格式（新）

**questions_new.jsonl**：
```json
{"id": "Q001", "question": "...", "type": "api_use", "version": "documented", "difficulty": "medium"}
{"id": "Q002", "question": "...", "type": "api_use", "version": "documented", "difficulty": "medium"}
```

**expected_sources.jsonl**：
```json
{"question_id": "Q001", "source_id": "user_manual", "page_print": [28, 43], "section_keyword": "create_participant domainId"}
{"question_id": "Q002", "source_id": "user_manual", "page_print": [43], "section_keyword": "domainID"}
```

---

## 📝 文件状态总结

| 文件 | 状态 | 说明 |
|------|------|------|
| `evaluation/datasets/questions.json` | 保留 | 原始 JSON 数组格式，120 题 |
| `evaluation/datasets/questions_new.jsonl` | ✅ 重建 | JSONL 格式，120 题 |
| `evaluation/datasets/expected_sources.jsonl` | ✅ 重建 | JSONL 格式，120 条标注 |

---

## 🎯 重做原因说明

根据第二周交付审查文档中的"标注接入三条件"：

| 条件 | 原状态 | 重做原因 |
|------|--------|---------|
| **格式问题** | JSON 数组 + 标注内嵌 | `run_experiment` 的 JSONL loader 无法解析 |
| **真值抽查仅 64% 吻合** | 120 题中 16 题系统性偏差 | QoS 策略题大量标注"章节入口页"，而定义真值在操作页 |
| **audit_questions.py 作废重做** | 中文 `split()` 无分词、语义不通 | 只审旧 15 题，无法覆盖全部问题 |

---

## 📚 相关文档

- [`questions_new.jsonl`](/C:/Users/55386/Documents/GitHub/RAG4ZRDDS/evaluation/datasets/questions_new.jsonl) - JSONL 格式问题集
- [`expected_sources.jsonl`](/C:/Users/55386/Documents/GitHub/RAG4ZRDDS/evaluation/datasets/expected_sources.jsonl) - 期望来源标注
- [`fix_questions_format.py`](/C:/Users/55386/Documents/GitHub/RAG4ZRDDS/scripts/fix_questions_format.py) - 修复脚本
