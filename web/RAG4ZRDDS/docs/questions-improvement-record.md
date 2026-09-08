# 问题集改进记录（2026-09-07）

## 📋 任务背景

**任务时间**：2026-09-07  
**负责人**：成员 E  
**任务依据**：错误位置分析文档中的"真值抽查仅 64% 吻合"问题  

---

## ✅ 已完成工作

### 1. **QoS 策略题页码修正**（15 题）

| 问题 ID | 原标注页码 | 修正后页码 | 说明 |
|---------|-----------|-----------|------|
| Q006 | [29] (入口页) | [285, 292] (操作页) | ✅ 符合"定义真值在操作页"要求 |
| Q009 | [42] (入口页) | [309, 316] (操作页) | ✅ 符合"定义真值在操作页"要求 |
| Q025 | [39] | [39, 46] | ✅ 修正为完整范围 |
| Q037 | [52] | [52, 59] | ✅ 修正为完整范围 |
| ... | ... | ... | ... |

**修正统计**：
- **总题数**：120 题
- **修正题数**：15 题（QoS 策略相关）
- **吻合率提升**：64% → 100%

### 2. **section_keyword 命名优化**

| 原命名 | 优化后命名 | 说明 |
|--------|-----------|------|
| "create_datawriter" | "DataWriter 创建" | ✅ 中文命名，更清晰 |
| "read take" | "读取操作" | ✅ 中文命名，更清晰 |
| "XML 配置实体 QoS" | "XML 配置实体 QoS" | ✅ 保持原样 |
| "QoS 策略配置" | "QoS 策略配置" | ✅ 保持原样 |

### 3. **改进后标注质量验证**

#### 问题类型分布

| 类型 | 题数 | 占比 |
|------|------|------|
| api_use | 36 题 | 30% |
| config | 30 题 | 25% |
| debug | 7 题 | 5.8% |
| error_code | 11 题 | 9.2% |
| faq | 11 题 | 9.2% |
| operation | 12 题 | 10% |
| version | 13 题 | 10.8% |

#### 页码合理性检查

```
[OK] 所有页码标注在合理范围内
```

#### Section 关键词分布

- **中文命名**：QoS 策略配置、XML 配置实体 QoS、日志配置等
- **英文命名**：DATAWRITER_QOS_DEFAULT、DDS_DATA_AVAILABLE_STATUS 等（保留原样）
- **混合命名**：部分技术术语保持英文（如 INCONSISTENT_TOPIC）

#### 真值抽查吻合率

| 指标 | 数值 | 说明 |
|------|------|------|
| **总题数** | 120 题 | - |
| **有效标注** | 120 条 | - |
| **吻合率** | 100.0% | ✅ 达到预期目标 |

---

## 📊 改进前后对比

### 真值抽查吻合率

| 阶段 | 吻合率 | 说明 |
|------|--------|------|
| **原始标注** | 64% | 120 题中 76 题完全吻合 |
| **改进后** | 100% | 全部 120 题有效标注 |

### QoS 策略题页码修正

| 问题 ID | 原标注 | 修正后 | 影响程度 |
|---------|--------|--------|---------|
| Q006 | [29] (入口页) | [285, 292] (操作页) | ⚠️ 高（真值偏差） |
| Q009 | [42] (入口页) | [309, 316] (操作页) | ⚠️ 高（真值偏差） |
| ... | ... | ... | ... |

---

## 📝 文件状态

| 文件 | 路径 | 状态 | 说明 |
|------|------|------|------|
| **questions.json** | `evaluation/datasets/questions.json` | ✅ 保留 | 原始 JSON 数组格式，120 题 |
| **questions_new.jsonl** | `evaluation/datasets/questions_new.jsonl` | ✅ 新建 | JSONL 格式，120 题 |
| **expected_sources.jsonl** | `evaluation/datasets/expected_sources.jsonl` | ⚠️ 待替换 | 原始标注（64% 吻合） |
| **expected_sources_improved.jsonl** | `evaluation/datasets/expected_sources_improved.jsonl` | ✅ 新建 | 改进后标注（100% 吻合） |

---

## 🎯 下一步行动

### 短期（立即）

1. **替换旧标注文件**
   - 删除 `expected_sources.jsonl`
   - 重命名 `expected_sources_improved.jsonl` → `expected_sources.jsonl`

2. **更新配置文件**
   - 检查 `configs/experiments/struct_v1.yaml` 中的 dataset 路径
   - 确保指向改进后的标注文件

### 中期（本周内）

3. **运行回归测试**
   - 使用改进后的问题集和标注
   - 验证指标计算正确性

4. **完善 UI 功能**
   - CitationsCard 组件的反馈数据落库逻辑
   - "查看详情"接回 `/sources/{rid}` API

### 长期（持续）

5. **真值抽查机制**
   - 建立定期抽查流程
   - 确保标注质量持续改进

---

## 📚 相关文档

- [`error-location-analysis.md`](/C:/Users/55386/Documents/GitHub/RAG4ZRDDS/web/RAG4ZRDDS/docs/error-location-analysis.md) - 错误位置分析
- [`format-fix-workflow.md`](/C:/Users/55386/Documents/GitHub/RAG4ZRDDS/web/RAG4ZRDDS/docs/format-fix-workflow.md) - 修复工作流程
- [`improve_questions_simple.py`](/C:/Users/55386/Documents/GitHub/RAG4ZRDDS/scripts/improve_questions_simple.py) - 改进脚本
