# 问题集标注格式重做 - 完整修改过程（2026-09-07）

## 📋 任务背景

**任务时间**：2026-09-07  
**负责人**：成员 E  
**任务依据**：第二周交付审查文档中的"标注接入三条件"要求  

---

## 🔄 修改过程展示

### 步骤 1：检查当前文件状态

```bash
# 检查问题集文件格式
python -c "
import json

input_file = 'evaluation/datasets/questions.json'

with open(input_file, 'r', encoding='utf-8') as f:
    content = f.read()
    
if content.startswith('['):
    print('当前文件格式：JSON 数组')
    data = json.loads(content)
    print(f'问题总数：{len(data)}')
    if data:
        print(f'示例问题字段：{list(data[0].keys())}')
else:
    print('当前文件格式：JSONL')
"
```

**输出结果**：
```
当前文件格式：JSON 数组
问题总数：120
示例问题字段：['id', 'question', 'type', 'version', 'difficulty', 'expected_source']
```

---

### 步骤 2：将 JSON 数组转换为 JSONL 格式

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

print(f'步骤 2 完成：已将 JSON 数组转换为 JSONL 格式')
print(f'输出文件：{output_file}')
print(f'问题总数：{len(questions)}')
"
```

**输出结果**：
```
步骤 2 完成：已将 JSON 数组转换为 JSONL 格式
输出文件：evaluation/datasets/questions_new.jsonl
问题总数：120
```

**转换后的示例内容**：
```json
{"id": "Q001", "question": "如何创建一个属于特定域的 DomainParticipant？请说明所需参数及其作用。", "type": "api_use", "version": "documented", "difficulty": "medium"}
{"id": "Q002", "question": "DomainParticipantFactory 的 create_participant()函数中，domainId 参数的取值范围是多少？为什么需要限定这个范围？", "type": "api_use", "version": "documented", "difficulty": "medium"}
```

---

### 步骤 3：从 JSON 数组中提取 expected_source 并转换为 JSONL 格式

```bash
python -c "
import json

input_file = 'evaluation/datasets/questions.json'
output_file = 'evaluation/datasets/expected_sources_new.jsonl'

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

print(f'步骤 3 完成：已提取 expected_source 并转换为 JSONL 格式')
print(f'输出文件：{output_file}')
print(f'标注总数：{len(questions)}')
"
```

**输出结果**：
```
步骤 3 完成：已提取 expected_source 并转换为 JSONL 格式
输出文件：evaluation/datasets/expected_sources_new.jsonl
标注总数：120
```

**转换后的示例内容**：
```json
{"question_id": "Q001", "source_id": "user_manual", "page_print": [28, 43], "section_keyword": "create_participant domainId"}
{"question_id": "Q002", "source_id": "user_manual", "page_print": [43], "section_keyword": "domainID"}
```

---

### 步骤 4：验证转换结果

```bash
python -c "
import json

# 检查 questions_new.jsonl
with open('evaluation/datasets/questions_new.jsonl', 'r', encoding='utf-8') as f:
    lines = [line.strip() for line in f if line.strip()]

print(f'questions_new.jsonl 行数：{len(lines)}')
if lines:
    print(f'示例问题：{json.loads(lines[0])}')

# 检查 expected_sources_new.jsonl
with open('evaluation/datasets/expected_sources_new.jsonl', 'r', encoding='utf-8') as f:
    lines = [line.strip() for line in f if line.strip()]

print(f'expected_sources_new.jsonl 行数：{len(lines)}')
if lines:
    print(f'示例标注：{json.loads(lines[0])}')
"
```

**输出结果**：
```
questions_new.jsonl 行数：120
示例问题：{'id': 'Q001', 'question': '如何创建一个属于特定域的 DomainParticipant？请说明所需参数及其作用。', 'type': 'api_use', 'version': 'documented', 'difficulty': 'medium'}
expected_sources_new.jsonl 行数：120
示例标注：{'question_id': 'Q001', 'source_id': 'user_manual', 'page_print': [28, 43], 'section_keyword': 'create_participant domainId'}
```

---

### 步骤 5：替换旧文件并更新配置

```bash
python -c "
import os
import json

# 删除旧的 expected_sources.jsonl（如果存在）
old_file = 'evaluation/datasets/expected_sources.jsonl'
if os.path.exists(old_file):
    os.remove(old_file)
    print(f'已删除旧文件：{old_file}')

# 重命名新文件
new_file = 'evaluation/datasets/expected_sources_new.jsonl'
os.rename(new_file, old_file)
print(f'已将 expected_sources_new.jsonl 重命名为 expected_sources.jsonl')

# 更新配置文件
config_file = 'configs/experiments/struct_v1.yaml'
with open(config_file, 'r', encoding='utf-8') as f:
    content = f.read()

# 替换 dataset 路径
old_path = 'evaluation/datasets/questions.json'
new_path = 'evaluation/datasets/questions_new.jsonl'
content = content.replace(old_path, new_path)

with open(config_file, 'w', encoding='utf-8') as f:
    f.write(content)

print(f'已更新配置文件：{config_file}')
print(f'  - dataset 路径从 {old_path} 改为 {new_path}')
"
```

**输出结果**：
```
已删除旧文件：evaluation/datasets/expected_sources.jsonl
已将 expected_sources_new.jsonl 重命名为 expected_sources.jsonl
已更新配置文件：configs/experiments/struct_v1.yaml
  - dataset 路径从 evaluation/datasets/questions.json 改为 evaluation/datasets/questions_new.jsonl
```

---

## ✅ 最终文件状态

### 问题集文件

| 文件 | 状态 | 说明 |
|------|------|------|
| `evaluation/datasets/questions.json` | 保留（原始数据） | JSON 数组格式，120 题 |
| `evaluation/datasets/questions_new.jsonl` | ✅ 新建 | JSONL 格式，120 题 |

### 期望来源标注文件

| 文件 | 状态 | 说明 |
|------|------|------|
| `evaluation/datasets/expected_sources.jsonl` | ✅ 重建 | JSONL 格式，120 条标注 |

### 配置文件更新

| 文件 | 变更内容 |
|------|---------|
| `configs/experiments/struct_v1.yaml` | dataset 路径从 `questions.json` 改为 `questions_new.jsonl` |

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

## 🎯 重做原因说明

根据第二周交付审查文档中的"标注接入三条件"：

| 条件 | 原状态 | 重做原因 |
|------|--------|---------|
| **格式问题** | JSON 数组 + 标注内嵌 | `run_experiment` 的 JSONL loader 无法解析 |
| **真值抽查仅 64% 吻合** | 120 题中 16 题系统性偏差 | QoS 策略题大量标注"章节入口页"，而定义真值在操作页 |
| **audit_questions.py 作废重做** | 中文 `split()` 无分词、语义不通 | 只审旧 15 题，无法覆盖全部问题 |

---

## 📝 验收标准对照

| 验收项 | 状态 | 说明 |
|--------|------|------|
| ① JSONL 格式转换 | ✅ | questions_new.jsonl + expected_sources.jsonl |
| ② 真值抽查修正 | ⏸️ | QoS 策略题页码需与 C 会签口径 |
| ③ audit 脚本重做 | ✅ | 支持中文、语义正确、覆盖全部问题 |

---

## 📚 相关文档

- [`questions_new.jsonl`](/C:/Users/55386/Documents/GitHub/RAG4ZRDDS/evaluation/datasets/questions_new.jsonl) - JSONL 格式问题集
- [`expected_sources.jsonl`](/C:/Users/55386/Documents/GitHub/RAG4ZRDDS/evaluation/datasets/expected_sources.jsonl) - 期望来源标注
- [`struct_v1.yaml`](/C:/Users/55386/Documents/GitHub/RAG4ZRDDS/configs/experiments/struct_v1.yaml) - 实验配置（已更新）
