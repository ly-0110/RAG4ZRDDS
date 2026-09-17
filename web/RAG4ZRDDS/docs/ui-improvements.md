# CitationsCard UI 功能完善记录

## 📋 任务概述

**任务目标**：完善 CitationsCard 组件的 UI 功能，包括来源徽标区分、HTML 引用点击跳转、反馈按钮等。

**完成时间**：2026-09-07  
**负责人**：成员 E

---

## ✅ 已完成功能

### 1. 来源徽标区分（已实现）

**功能说明**：
- PDF 来源显示 📕 图标，背景色 `#ffebee`（红色系）
- HTML 来源显示 📘 图标，背景色 `#e3f2fd`（蓝色系）
- 点击 HTML 引用可跳转到原文 URL

**实现位置**：
```vue
<!-- CitationsCard.vue:21-44 -->
<span v-if="s.source_type" :class="[
  'source-badge',
  s.source_type === 'PDF' ? 'badge-pdf' : 'badge-html'
]">
  <span class="source-badge-icon">
    {{ s.source_type === 'PDF' ? '📕' : '📘' }}
  </span>
  <span>{{ s.source_type === 'PDF' ? 'ZRDDS 用户手册' : 'Developer Guide' }}</span>
</span>

<a 
  v-if="s.source_type === 'HTML'" 
  :href="s.url" 
  target="_blank" 
  rel="noopener noreferrer"
  class="source-id"
  style="color: #1565c0; text-decoration: none;"
>
  → 查看原文
</a>
```

**样式类**：
- `.badge-pdf` - PDF 来源徽标样式
- `.badge-html` - HTML 来源徽标样式
- `.source-badge-icon` - 图标样式
- `.source-id` - HTML 原文链接样式

---

### 2. "有帮助/无帮助"反馈按钮（新增）

**功能说明**：
- 每个引用卡片底部添加 👍/👎 反馈按钮
- 点击后前端暂存反馈数据
- TODO: 调用后端 API 提交反馈数据

**实现位置**：
```vue
<!-- CitationsCard.vue:59-68 -->
<div class="feedback-actions" v-if="requestId && canFetchDetails">
  <button 
    class="feedback-btn helpful"
    @click="submitFeedback(s.node_id, true)"
    title="有帮助"
  >
    👍 有帮助
  </button>
  <button 
    class="feedback-btn unhelpful"
    @click="submitFeedback(s.node_id, false)"
    title="无帮助"
  >
    👎 无帮助
  </button>
</div>
```

**JavaScript 逻辑**：
```javascript
// CitationsCard.vue:116-138
const feedbacks = ref({})

const submitFeedback = async (nodeId, isHelpful) => {
  if (!canFetchDetails.value) return
  
  // 记录反馈（前端暂存，实际提交需后端 API）
  feedbacks.value[nodeId] = {
    helpful: isHelpful,
    timestamp: Date.now()
  }
  
  // TODO: 调用后端 API 提交反馈数据
  // await fetch(`/api/feedback/${nodeId}`, { method: 'POST', body: ... })
  
  console.log(`Feedback submitted for ${nodeId}: helpful=${isHelpful}`)
}
```

**样式类**：
- `.feedback-actions` - 反馈按钮容器
- `.feedback-btn` - 反馈按钮基础样式
- `.feedback-btn.helpful` - 有帮助按钮（绿色系）
- `.feedback-btn.unhelpful` - 无帮助按钮（红色系）

---

### 3. 详情面板优化（已实现）

**功能说明**：
- 每个来源卡片独立管理详情显示状态
- 点击"查看详情"按钮展开详情面板
- 点击"收起"按钮隐藏详情面板
- 详情面板包含类型、页码、相关度、ID、内容等信息

**实现位置**：
```vue
<!-- CitationsCard.vue:60-82 -->
<div 
  v-if="showDetails[s.node_id]" 
  class="details-panel"
  :key="activeSources[s.node_id]?.node_id"
>
  <div class="details-header">
    <h4 class="details-title">{{ activeSources[s.node_id]?.source_name }}</h4>
    <button 
      v-if="requestId && canFetchDetails"
      class="close-details-btn"
      @click="hideDetails(s.node_id)"
    >
      ✕ 收起
    </button>
  </div>
  <div class="details-content">
    <p><strong>类型：</strong>{{ activeSources[s.node_id]?.section || 'N/A' }}</p>
    <p><strong>页码：</strong>第 {{ activeSources[s.node_id]?.page_print }} 页（物理页 {{ activeSources[s.node_id]?.page_physical }}）</p>
    <p><strong>相关度：</strong>{{ Number(activeSources[s.node_id]?.score).toFixed(3) }}</p>
    <p v-if="activeSources[s.node_id]?.source_id"><strong>ID：</strong>{{ activeSources[s.node_id].source_id }}</p>
    <p v-if="activeSources[s.node_id]?.content" class="details-content-text">{{ activeSources[s.node_id].content }}</p>
  </div>
</div>
```

**样式类**：
- `.details-panel` - 详情面板容器
- `.details-header` - 详情头部（标题 + 收起按钮）
- `.close-details-btn` - 收起按钮
- `.details-content` - 详情内容区域
- `.details-content-text` - 回答内容文本

---

## 📊 代码变更统计

| 文件 | 变更类型 | 行数变化 |
|------|---------|---------|
| `web/RAG4ZRDDS/src/components/CitationsCard.vue` | 新增功能 | +30 行 |

**总变更**：+30 行（新增反馈按钮及相关逻辑）

---

## 🎨 UI 设计说明

### 颜色规范

| 元素 | 背景色 | 文字色 | 边框色 |
|------|--------|--------|--------|
| PDF 徽标 | `#ffebee` | `#c62828` | - |
| HTML 徽标 | `#e3f2fd` | `#1565c0` | - |
| 有帮助按钮（悬停） | `#e8f5e9` | `#2e7d32` | `#4caf50` |
| 无帮助按钮（悬停） | `#ffebee` | `#c62828` | `#f44336` |

### 交互效果

- **悬停阴影**：卡片 hover 时显示 `box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08)`
- **上移动画**：hover 时 `transform: translateY(-1px)`
- **淡入动画**：详情面板展开时 `animation: fadeIn 0.3s ease`

---

## 📝 待办事项

### 后端 API（已接线）

需要成员 B/C 实现以下 API：

1. **反馈提交接口**
   - Endpoint: `POST /feedback`（以回答为单位归属，故不再按 `{node_id}` 记点击）
   - Body: `{ "request_id": string, "rating": "up" | "down", "comment"?: string, "node_ids"?: string[] }`
   - Response: `{ "status": "recorded", "feedback_id": string, "request_id": string, "rating": string }`
   - 未知 `request_id` → `404`；`node_ids` 不属于该次引用 → `400`

2. **反馈查询接口（可选）**
   - 未实现；当前无消费方

### 数据落库（已落地：方案 B，`{log_dir}/feedback.jsonl`）

需要设计反馈数据存储方案：

**方案 A**：SQLite 表
```sql
CREATE TABLE feedback (
  node_id TEXT PRIMARY KEY,
  helpful BOOLEAN NOT NULL,
  timestamp INTEGER NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**方案 B**：JSONL 文件
```json
{"node_id": "xxx", "helpful": true, "timestamp": 1234567890}
{"node_id": "yyy", "helpful": false, "timestamp": 1234567891}
```

---

## 📈 验收标准

- [x] 来源徽标区分 PDF/HTML ✅
- [x] HTML 引用点击跳转 URL ✅
- [x] "有帮助/无帮助"反馈按钮 ✅
- [x] 反馈数据落库（`POST /feedback` → `{log_dir}/feedback.jsonl`）
- [x] 全量回归与兼容性检查（待执行）
  - 可离线复现部分已完成并出报告：[week4_regression_compat.md](../../../evaluation/reports/week4_regression_compat.md)（vitest 25/25、cypress 4/4、ESLint、build、浏览器/视口矩阵、标注审计）
  - 仍待解锁：10 题冒烟矩阵、检索矩阵重建基准（D）、答案侧指标（需 LLM 与定版标注）

---

## 📚 相关文档

- [`CitationsCard.vue`](/C:/Users/55386/Documents/GitHub/RAG4ZRDDS/web/RAG4ZRDDS/src/components/CitationsCard.vue) - 组件源码
- [`UI_UPGRADE_IMPLEMENTATION.md`](/C:/Users/55386/Documents/GitHub/RAG4ZRDDS/web/RAG4ZRDDS/UI_UPGRADE_IMPLEMENTATION.md) - UI 升级实施记录
- [`regression-test-flow-v3.md`](/C:/Users/55386/Documents/GitHub/RAG4ZRDDS/web/RAG4ZRDDS/docs/regression-test-flow-v3.md) - 回归测试流程

---

## 🎯 下一步行动

1. **成员 B/C**：实现反馈提交 API
2. **成员 E**：完善数据落库逻辑
3. **全员**：执行全量回归测试

---

## 📊 UI 功能完善简报

### ✅ 完成情况

**任务目标**：完善 CitationsCard 组件的 UI 功能，包括来源徽标区分、HTML 引用点击跳转、反馈按钮等。

**完成时间**：2026-09-07  
**负责人**：成员 E

### 🎉 新增功能清单

1. **来源徽标区分**（已实现）
   - PDF 来源显示 📕 图标，背景色 `#ffebee`
   - HTML 来源显示 📘 图标，背景色 `#e3f2fd`
   - HTML 引用点击可跳转到原文 URL

2. **"有帮助/无帮助"反馈按钮**（新增）
   - 每个引用卡片底部添加 👍/👎 反馈按钮
   - 点击后前端暂存反馈数据
   - TODO: 调用后端 API 提交反馈数据

3. **详情面板优化**（已实现）
   - 每个来源卡片独立管理详情显示状态
   - 点击"查看详情"按钮展开详情面板
   - 点击"收起"按钮隐藏详情面板
   - 详情面板包含类型、页码、相关度、ID、内容等信息

### 📊 代码变更统计

| 文件 | 变更类型 | 行数变化 |
|------|---------|---------|
| `web/RAG4ZRDDS/src/components/CitationsCard.vue` | 新增功能 | +30 行 |

**总变更**：+30 行（新增反馈按钮及相关逻辑）

### 🎨 UI 设计说明

#### 颜色规范

| 元素 | 背景色 | 文字色 | 边框色 |
|------|--------|--------|--------|
| PDF 徽标 | `#ffebee` | `#c62828` | - |
| HTML 徽标 | `#e3f2fd` | `#1565c0` | - |
| 有帮助按钮（悬停） | `#e8f5e9` | `#2e7d32` | `#4caf50` |
| 无帮助按钮（悬停） | `#ffebee` | `#c62828` | `#f44336` |

#### 交互效果

- **悬停阴影**：卡片 hover 时显示 `box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08)`
- **上移动画**：hover 时 `transform: translateY(-1px)`
- **淡入动画**：详情面板展开时 `animation: fadeIn 0.3s ease`

### 📝 待办事项

#### 后端 API（已接线：D 侧 `server/api/feedback.py`）

反馈以**回答**为单位归属（脱离具体回答的"整体满意度"无法归因），因此落地口径与本节最初设想的「按 node_id 记一次点击」不同：

1. **反馈提交接口**
   - Endpoint: `POST /feedback`
   - Body: `{ "request_id": string, "rating": "up" | "down", "comment"?: string, "node_ids"?: string[] }`
   - Response: `{ "status": "recorded", "feedback_id": string, "request_id": string, "rating": string }`
   - 错误：未知 `request_id` → `404`（拒绝孤儿记录）；`node_ids` 不属于该次引用 → `400`
   - 前端调用点：`src/App.vue` 的 `submitFeedback()`，`request_id` 取自 SSE `done` 帧

2. **反馈查询接口**：未实现（可选，当前无消费方）

> 会签状态：字段表（`rating` 两档 + `comment` 自由文本 + 可选 `node_ids`）为提案，待 E/C 会签。

#### 数据落库（已落地：方案 B）

追加到 `{log_dir}/feedback.jsonl`，与 `requests.jsonl` / `retrievals.jsonl` / `sources.jsonl` 同目录同格式，可离线聚合：

```json
{"feedback_id": "a1b2c3d4e5f6", "request_id": "rid-...", "rating": "up", "question": "如何创建 DataWriter？", "answer_present": true, "cited_nodes": 3}
```

只落问题摘要、不落答案正文（答案已在 `sources.jsonl`，避免重复膨胀）。

#### 测试验证（TODO）

- [x] 反馈链路单测（`src/__tests__/App.spec.js`：面板显隐、提交体、后端 `detail` 透出）
- [x] 前端全量回归（vitest 25/25、cypress 4/4、ESLint 0 warning、生产构建通过）
- [x] 兼容性检查（不同浏览器/设备）：Chromium(Electron 146) + Edge 153 通过，视口 1280×720 / 1920×1080 / 390×844 三档通过；Firefox/Safari 因本机未安装未覆盖
- [ ] 执行冒烟测试（10 个基础问题，需 live 管线）
- [ ] 检索/答案侧全量回归（等待 live 管线与定版标注就绪）

### 📈 验收标准

- [x] 来源徽标区分 PDF/HTML ✅
- [x] HTML 引用点击跳转 URL ✅
- [x] "有帮助/无帮助"反馈按钮 ✅
- [x] 反馈数据落库（`POST /feedback` → `{log_dir}/feedback.jsonl`）
- [ ] 全量回归与兼容性检查（待执行）
  - 可离线复现部分已完成并出报告：[week4_regression_compat.md](../../../evaluation/reports/week4_regression_compat.md)（vitest 25/25、cypress 4/4、ESLint、build、浏览器/视口矩阵、标注审计）
  - 仍待解锁：10 题冒烟矩阵、检索矩阵重建基准（D）、答案侧指标（需 LLM 与定版标注）

### 📚 相关文档

- [`CitationsCard.vue`](/C:/Users/55386/Documents/GitHub/RAG4ZRDDS/web/RAG4ZRDDS/src/components/CitationsCard.vue) - 组件源码
- [`UI_UPGRADE_IMPLEMENTATION.md`](/C:/Users/55386/Documents/GitHub/RAG4ZRDDS/web/RAG4ZRDDS/UI_UPGRADE_IMPLEMENTATION.md) - UI 升级实施记录
- [`regression-test-flow-v3.md`](/C:/Users/55386/Documents/GitHub/RAG4ZRDDS/web/RAG4ZRDDS/docs/regression-test-flow-v3.md) - 回归测试流程

