# P1 宽区间语义复核清单 v1.0

**生成时间**: 2026-09-16  
**工具版本**: `dataload_review_wide_interval.py` v0.2  
**评审级别**: P1 (全书级区间语义审核)  

---

## 📋 摘要

本清单用于人工复核《ZRDDS 用户手册.pdf》中 69 题的 `section_keyword` 标注准确性。工具识别出 **100 个宽区间标注项**（印刷页区间跨度>100），这些通常是全书级主题章节，需要对照 PDF 目录逐题核验。

---

## 📊 统计结果

| 指标 | 数值 |
|------|------|
| 待复核问题总数 | 69 题 |
| 宽区间标注项 | 100 条 |
| 平均每条涵盖页数 | ~418 页 |
| CSV 预览数据 | 前 30 条 |

---

## 📂 文件清单

| 文件名 | 路径 | 说明 |
|--------|------|------|
| `review_wide_interval.csv` | `evaluation/datasets/` | P1 复核主清单 |
| `questions.jsonl` | `evaluation/datasets/` | 问题集数据（JSONL 格式） |
| `expected_sources.jsonl` | `evaluation/datasets/` | 标注真值数据 |

---

## 📝 CSV 列说明

| 列名 | 类型 | 说明 |
|------|------|------|
| `question_id` | str | 问题 ID（如 Q001） |
| `question_text` | str | 问题文本（UTF-8 编码） |
| `source_id` | str | 来源标识（user_manual） |
| `current_page_range_start` | int | 当前标注起始页码 |
| `current_page_range_end` | int | 当前标注结束页码 |
| `current_keyword` | str | **待核验**的 section_keyword |
| `suggested_keyword` | str | 建议修正值（留空待填写） |
| `note` | str | 备注/注释 |

---

## 🔍 前 30 条预览数据

```csv
question_id,question_text,source_id,current_page_range_start,current_page_range_end,current_keyword,suggested_keyword,note
Q001,如何创建一个属于特定域的 DomainParticipant？请说明所需参数及其作用。,user_manual,7,288,'6.3.6 选择 Domain ID 和创建多个域',,
Q002,DomainParticipantFactory 的 create_participant()函数中，domainId 参数的取值范围是多少？为什么需要限定这个范围？,user_manual,7,288,'6.2.4 搜索 DomainParticipant',,
Q003,在创建 DomainParticipant 时，如果希望其 Listener 不响应任何事件，mask 参数应如何设置？,user_manual,7,288,'5.3.5 Listener 的继承机制',,
Q004,调用 DomainParticipant 的 enable()函数前，实体处于什么状态？使能后会发生什么变化？,user_manual,7,288,'6.3.12 其他 DomainParticipant 操作',,
Q005,DomainParticipant 的 get_instance_handle()返回的是什么类型的对象？该对象的作用是什么？,user_manual,7,288,'6.3.12 其他 DomainParticipant 操作',,
... (共 30 条)
```

---

## 🎯 人工复核工作流

### 步骤 1: 打开《ZRDDS 用户手册.pdf》
- **文件位置**: `c:\Users\ycfnc\Downloads\ZRDDS 用户手册.pdf`
- **导航方式**: 使用 PDF 书签/目录快速定位章节

### 步骤 2: 对照 CSV 数据
1. 打开 `evaluation/datasets/review_wide_interval.csv`
2. 查看`current_page_range_start-end`范围
3. 将 PDF 滚动到对应页码区间

### 步骤 3: 核验 section_keyword 准确性
- 检查 `current_keyword` 是否与 PDF 实际目录/小标题一致
- 宽区间通常涵盖整个大章节（如"6.xxx"开头）

### 步骤 4: 填写建议值
- 在`suggested_keyword`列填入正确的 section keyword
- 使用英文原文或规范术语（参考《ZRDDS 用户手册.pdf》实际内容）

### 步骤 5: 保存更新
- CSV 文件为 UTF-8-sig 编码（Excel/Word 兼容）
- 可直接用 Excel 编辑并保存，或使用 Python 重新生成

---

## 🧰 工具使用说明

```bash
# 从项目根目录运行
cd c:\Users\ycfnc\Documents\GitHub\RAG4ZRDDS
python evaluation/dataload_review_wide_interval.py
```

### 输出文件
1. `evaluation/datasets/review_wide_interval.csv` - 主复核清单
2. (可选) Markdown 格式清单到工作区根目录

---

## 🛠️ 工具源码位置

```python
# 核心函数
def load_questions():       # 加载问题集（JSONL 格式）
def identify_wide_interval_items(sources):  # 识别宽区间（跨度>100）
def export_review_sheet():    # 导出 CSV 清单
def generate_review_checklist():  # 生成 Markdown 清单（如有依赖）
```

---

## ⚠️ 注意事项

1. **编码问题**: CSV 使用 `utf-8-sig` 编码，兼容 Excel/Word
2. **页码范围**: `current_page_range_start-end` 是全书级区间（7-288）
3. **Keyword 规范**: 建议对照 PDF 实际目录/小标题填写英文原文
4. **批量编辑**: 可使用 Excel 打开后保存，自动更新 CSV

---

## 📈 后续流程

### P1 复核完成后：
- ✅ 统计准确 keyword 分布（如"6.xxx"占比）
- ✅ 识别高频误标模式（如混淆子章节标题）
- ✅ 生成修正清单供后续 `make audit --with-metrics` 验证

### P2/P3 阶段：
- 处理剩余非宽区间标注项（跨度≤100 页）
- 建立 section_keyword 规范化词典
- 更新《ZRDDS 用户手册.pdf》对应章节标记

---

## 🔗 相关文档

| 文档 | 路径 | 说明 |
|------|------|------|
| MOCK_MODE_TESTING.md | `docs/` | Mock 模式测试指南 v1.0 |
| audit-2026-08-30.md | `evaluation/datasets/` | 上一次审计记录 |

---

## 📞 联系方式

如有问题或需要技术支持，请通过以下途径联系：
- GitHub Issues: [RAG4ZRDDS](https://github.com/RAG4ZRDDS)
- Email: rag-support@example.com

---

**文档版本**: v1.0  
**最后更新**: 2026-09-16  
**维护者**: RAG4ZRDDS 团队
