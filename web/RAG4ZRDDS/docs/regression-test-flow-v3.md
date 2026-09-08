# 回归测试全过程流记录（第三次尝试）

## 📋 测试配置

### 实验配置
- **实验 ID**：struct_v1（结构分块基线）
- **阶段**：baseline
- **知识库来源**：ZRDDS 用户手册.pdf（PDF-only）
- **检索模式**：vector（向量语义匹配）
- **Top-K**：5

### 评测数据集
- **问题集**：`evaluation/datasets/questions.jsonl`（15 题）
- **期望来源**：`evaluation/datasets/expected_sources.jsonl`（刚标注完成）
- **基线报告**：`evaluation/reports/struct_v1.json`（Week 2 原始报告）

---

## 🚀 测试执行流程

### 步骤 1：检查前置条件

```bash
# 检查问题集
ls evaluation/datasets/questions.jsonl
# ✅ 存在（15 题）

# 检查期望来源标注
ls evaluation/datasets/expected_sources.jsonl
# ⚠️ 同步后被删除，需要重新创建

# 检查 PDF 文档
ls data/raw/ZRDDS\用户手册.pdf
# ✅ 存在（295 页）
```

### 步骤 2：运行回归测试

```bash
python scripts/run_experiment.py \
  --config configs/experiments/struct_v1.yaml
```

**预期输出**：
- 重建索引（如果不存在）
- 对 15 题进行检索评测
- 计算 hit_rate@5、mrr@5 等指标
- 生成报告 `evaluation/reports/struct_v1.json`

---

## 📝 实际执行记录

### Phase 0: 环境准备（依赖检查）

**问题 1**：缺少 `rank_bm25` 模块

```bash
python scripts/run_experiment.py --config configs/experiments/struct_v1.yaml
# → ModuleNotFoundError: No module named 'rank_bm25'
```

**解决 1**：安装缺失的依赖包

```bash
pip install rank_bm25
# ✅ 完成
```

**问题 2**：缺少 `llama_index` 模块

```bash
python scripts/run_experiment.py --config configs/experiments/struct_v1.yaml
# → ModuleNotFoundError: No module named 'llama_index'
```

**解决 2**：安装 llama_index

```bash
pip install llama_index
# ✅ 完成
```

### Phase 1: 第一次执行回归测试（路径错误）

**测试结果**：✅ 测试完成（0.7 秒），但所有检索结果为空

```
[experiment] 实验=struct_v1 hash8=47950b94 问题=15 指标=['hit_rate@5', 'mrr@5']
[experiment] 索引已存在，复用：indexes\struct_bge-m3_47950b94
[experiment] 开始检索（top_k=5）…
[experiment]   检索 Q001 → 0 条引用
... (共 15 题)
[experiment] ✓ 完成，耗时 0.7s
[experiment]   hit_rate@5     = 0.0000
[experiment]   mrr@5          = 0.0000
```

**问题诊断**：配置文件中的 PDF 路径错误（`data/raw/manuals/` → `data/raw/`）

### Phase 2: 修复配置并重新执行回归测试

**修改**：修复 configs/experiments/struct_v1.yaml 中的 PDF 路径

```yaml
# 原路径（错误）
path: data/raw/manuals/ZRDDS 用户手册.pdf

# 新路径（正确）
path: data/raw/ZRDDS 用户手册.pdf
```

### Phase 3: 第二次执行回归测试（依赖安装冲突）

**新问题**：缺少 `llama_index.embeddings.huggingface` 模块，安装遇到依赖冲突

```bash
pip install llama-index-embeddings-huggingface
# → ERROR: ResolutionImpossible (依赖冲突)
```

### Phase 4: 同步 develop 分支后重新执行回归测试

**新发现**：期望来源标注文件被删除

```
[experiment] 警告：期望来源标注不存在 evaluation/datasets/expected_sources.jsonl——本次只记录检索结果，不计算指标。
```

**根本原因**：
- 依赖包版本冲突导致无法安装 embedding 模块
- 同步后 `expected_sources.jsonl` 被删除（可能是 merge 冲突解决时的副作用）

### Phase 5: 当前状态分析

**问题汇总**：
1. ❌ 缺少 `llama_index.embeddings.huggingface` 模块（安装冲突）
2. ⚠️ `expected_sources.jsonl` 文件被删除（需要重新标注）
3. ⏸️ 冒烟测试因 mock 模式限制无法通过

**可行方案**：
1. **方案 A（推荐）**：等待成员 B/C 完成真实检索/生成实现后，使用 live 模式测试
2. **方案 B**：手动构建 cleaned 数据（需要 PDF 解析工具）
3. **方案 C**：使用 mock 模式进行单元测试（当前已支持 CitationsCard 组件）

### Phase 6: 重新创建期望来源标注

**操作**：创建 `expected_sources.jsonl`（15 题）

```bash
# 创建文件（已在执行）
# ✅ 完成
```

### Phase 7: 第三次执行回归测试（已恢复 expected_sources.jsonl）

**测试结果**：✅ 测试完成（0.9 秒），但所有检索结果为空

```
[experiment] 实验=struct_v1 hash8=d652378f 问题=15 指标=['hit_rate@5', 'mrr@5']
[experiment] 索引已存在，复用：indexes\struct_bge-m3_d652378f
[experiment] 开始检索（top_k=5）…
[experiment]   检索 Q001 → 0 条引用
... (共 15 题)
[experiment] ✓ 完成，耗时 0.9s
[experiment]   hit_rate@5     = 0.0000
[experiment]   mrr@5          = 0.0000
```

**问题诊断**：索引中存在节点但检索结果为空

### Phase 8: 强制重建索引（--rebuild）

**操作**：删除旧索引并重新构建

```bash
python scripts/run_experiment.py --config configs/experiments/struct_v1.yaml --rebuild
# → Traceback (most recent call last):
#    ModuleNotFoundError: No module named 'llama_index.embeddings.huggingface'
```

**根本原因**：缺少 `llama_index.embeddings.huggingface` 模块（依赖冲突）

### Phase 9: 当前状态分析

**问题汇总**：
1. ❌ 缺少 `llama_index.embeddings.huggingface` 模块（安装冲突）
2. ✅ `expected_sources.jsonl` 已恢复（15 题）
3. ✅ cleaned/pages.jsonl 存在（需要 PDF 解析流水线）
4. ⏸️ 冒烟测试因 mock 模式限制无法通过

**可行方案**：
1. **方案 A（推荐）**：等待成员 B/C 完成真实检索/生成实现后，使用 live 模式测试
2. **方案 B**：手动构建 cleaned 数据（需要 PDF 解析工具）
3. **方案 C**：使用 mock 模式进行单元测试（当前已支持 CitationsCard 组件）

### Phase 10: 回归测试结论

**结论**：在当前环境下无法完成完整的回归测试流程。

**建议行动**：
1. 成员 B/C 优先完成真实检索/生成实现
2. 配置 `.env` 文件（LLM API 密钥等）
3. 重新运行回归测试

---

## 📋 待办事项清单

- [ ] 解决依赖冲突问题（或等待 live 管线就绪）
- [ ] 成员 B/C 完成真实检索/生成实现
- [ ] 配置 `.env` 环境变量
- [ ] 重新执行回归测试
- [ ] 分析测试结果并对比 Week 2 基线

---

## 📊 项目状态总览

### ✅ 已完成工作（第三周）

1. **CitationsCard 组件**：功能完整，UI 升级实施完成
2. **期望来源标注**：`expected_sources.jsonl`（15 题）已创建并标注
3. **问题集扩展**：`questions.jsonl` 从空更新为 15 题正式问题集
4. **文档产出**：
   - `UI_UPGRADE_IMPLEMENTATION.md` - UI 升级实施记录
   - `cross-source-questions-plan.md` - 跨来源问题集扩展方案
   - `regression-test-guide.md` - 回归测试指南
   - `expected-sources-annotation-work.md` - 期望来源标注工作记录
   - `regression-test-flow-v3.md` - 回归测试全过程流记录（v3）

### ⏸️ 进行中/阻塞任务

1. **回归测试**：依赖冲突阻塞，等待 live 管线就绪
2. **冒烟测试**：mock 模式限制，等待后端 live 管线

### 📁 重要文件清单

- `web/RAG4ZRDDS/src/components/CitationsCard.vue` - Citations 卡片组件
- `evaluation/datasets/questions.jsonl` - 15 题正式问题集
- `evaluation/datasets/expected_sources.jsonl` - 期望来源标注（15 题）
- `evaluation/reports/struct_v1.json` - Week 2 基线评测报告
- `configs/experiments/struct_v1.yaml` - 实验配置（路径已修复）

---

## 🎯 项目目标与职责

**项目定位**：RAG4ZRDDS - 基于 ZRDDS 用户手册的 RAG 问答系统

**成员分工**：
- **A**：质量检查、文档编写
- **B**：真实检索实现
- **C**：真实生成实现、Prompt 设计、LLM-as-judge 判分
- **D**：流水线维护、指标口径定义
- **E**（当前）：前端开发、回归测试执行

**第三周核心任务**：
1. UI 视觉升级 ✅
2. 期望来源标注 ✅
3. 回归测试验证 ⏸️（依赖阻塞）

---

## 🔄 替代工作清单（回归测试阻塞时）

根据指导文档，成员 E 的第三周任务包括：

### 可执行的其他任务

1. **问题集扩展**（跨来源题目）
   - 编写两来源联合类题目（PDF + HTML）
   - 编写版本差异类题目（对比不同版本的回答）
   - 需要 HTML 开发指南源文件（应在 `data/raw/developer-guides/cdoc_html/`）

2. **UI 功能完善**
   - 来源徽标区分 PDF / HTML
   - HTML 引用点击跳转 URL
   - "有帮助/无帮助"反馈按钮与数据落库
   - 全量回归与兼容性检查

3. **文档工作**
   - 编写 Demo README
   - 整理测试报告
   - 准备汇报材料（Baseline → 结构分块 → Hybrid → Reranker 的指标证据链）

4. **质量保障**
   - Node 抽查视图（基于 `scripts/inspect_nodes.py`）
   - 冒烟测试用例编写（10 个基础问题）
   - 人工盲评抽检（20 题主观体感证据）

### 优先级建议

- **高优先级**：UI 功能完善、文档工作
- **中优先级**：质量保障（Node 抽查、冒烟测试）
- **低优先级**：问题集扩展（等待 HTML 源文件）

---

## 📝 下一步行动

1. **短期**：完善 UI 功能、编写文档
2. **中期**：准备冒烟测试用例
3. **长期**：等待 live 管线就绪后执行回归测试
