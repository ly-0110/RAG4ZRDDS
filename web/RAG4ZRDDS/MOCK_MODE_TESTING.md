# Mock 模式模拟测试指南（成员 E 版）

## 📋 文档信息

| 属性 | 值 |
|------|-----|
| **文档版本** | v1.0 |
| **作者** | 成员 E |
| **最后更新** | 2026-09-16 04h05 |
| **覆盖范围** | F1-F4 前端修复完整验证流程 |
| **测试环境** | Mock 模式（开发调试）vs Live 模式（生产） |

## 🎯 测试目标

对成员 E 负责的**四个前端问题修复 (F1-F4)**进行 Mock 模式下的全面功能验证，确保：

1. ✅ **F1 UI modification**: kbStats 数据绑定正确，mock 模式下显示"加载中…"
2. ✅ **F1 fetch logic**: /healthz API 调用成功，mock/live 模式数据差异处理正确
3. ✅ **F2 markdown rendering**: DOMPurify XSS 防护生效，marked 渲染正常工作
4. ✅ **F3 CitationsCard**: mock/live 模式切换正常，字段绑定正确，节点详情静态提示显示

## 🏗️ 测试环境配置

### 当前状态

| 组件 | Mock 模式配置 | Live 模式配置 |
|------|---------------|---------------|
| **App.vue** | `knowledgeMode.value = 'mock'`（默认） | `knowledgeMode.value = 'live'` |
| **CitationsCard** | `mode: 'mock'`（默认） | `mode: 'live'` |
| **后端服务** | http://127.0.0.1:8000 (RAG_MODE=mock) | http://127.0.0.1:8000 (RAG_MODE=live) |

### 文件依赖关系

```
server/core/settings.py        → RAG_MODE 环境变量控制 mock/live
  ↓
server/core/routers/healthz.py → /healthz 端点返回 mode + kb_stats
  ↓
web/RAG4ZRDDS/src/App.vue      → onMounted fetch('/healthz') → healthData
  ↓
  ├─ → CitationsCard (mode prop)
  └─ → ChatInput (experiments prop - F4)
```

### Mock 模式行为说明

#### CitationsCard 组件表现（mock 模式）

| 操作 | 预期响应 | 代码实现位置 |
|------|----------|--------------|
| **初始加载** | `sources.length === 0`，不渲染 | `v-if="sources.length"` |
| **查询后 sources 有数据** | 渲染引用卡片数组 | 正常渲染 |
| **点击"查看节点详情"** | **不发起 fetch**，显示静态提示 | `canFetchDetails: false` |
| **展开详情面板** | `text: '-'`, `section_path: '-'`等占位符 | 绑定空字符串 |

```javascript
// CitationsCard.vue (CitationsCard 组件) - F3 修复验证点
const isInLiveMode = computed(() => props.mode === 'live') // F3: mock 模式为 false
const canFetchDetails = computed(() => props.requestId && props.requestId.length > 0)

// Mock 模式下：isInLiveMode = false, canFetchDetails = true(有 requestId 时)
// 但 fetchAndShowDetails()函数判断后会直接显示静态提示而不调用 fetch
```

#### App.vue onMounted 行为（mock 模式）

```javascript
// App.vue - /healthz 响应处理（mock 模式）
const kb = health.kb || {}  // mock 模式下通常为 null
if (kb && kb.node_total !== undefined) {
  kbStats.value = { 
    doc_count: kb.doc_count ?? '', 
    node_total: kb.node_total,
    index_dirname: kb.index_dirname || ''
  }
} else {
  kbStats.value = null  // mock 模式下通常为 null
}

// 后端未提供 embedder_class 时
if (health.embedder_class) {
  healthData.value = { embedder_class: health.embedder_class, status: 'active' }
} else {
  healthData.value = null  // 左侧状态卡显示"未配置"
}

// template 绑定（F1 修复验证点）
<strong v-if="kbStats?.doc_count">{{ kbStats.doc_count }}</strong>
<small v-else>加载中…</small>  <!-- F1: mock 模式显示占位符 -->
```

#### DOMPurify XSS 防护（F2 修复验证点）

```javascript
// App.vue - F2: DOMPurify XSS 防护辅助函数
function purify(html) {
  if (!DOMPurify) return html // 降级处理
  try {
    return DOMPurify.sanitize(html)
  } catch (e) {
    console.error('DOMPurify 净化失败:', e)
    return html
  }
}

// template - F2: Markdown 渲染（marked + DOMPurify 防 XSS）
<div [innerHTML]="purify(marked(answer))" class="streaming-response"></div>
```

## 🚀 测试步骤详解

### 阶段 1：环境准备

#### 1.1 设置 PowerShell 执行策略

```powershell
# 必须以管理员身份或当前用户权限运行
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

# 验证策略设置
Get-ExecutionPolicy -List | Select-Object Scope, Policy
```

#### 1.2 启动后端服务（Mock 模式）

```powershell
cd c:\Users\ycfnc\Documents\GitHub\RAG4ZRDDS

# 方式 A: 使用 Makefile（推荐）
python -m server.main

# 方式 B: 直接使用 Uvicorn
uvicorn server.main:app --host 127.0.0.1 --port 8000

# 验证服务状态（健康检查端点）
curl http://localhost:8000/healthz
# 预期响应（mock 模式）：
# {
#   "status": "ok",
#   "mode": "mock",
#   "kb": null,
#   "experiments": []
# }
```

#### 1.3 启动前端开发服务器

```powershell
cd c:\Users\ycfnc\Documents\GitHub\RAG4ZRDDS\web\RAG4ZRDDS

# 使用 NPM（推荐）
npm run dev

# 或使用 pnpm
pnpm dev

# 或使用 yarn
yarn dev

# 预期输出：
# 本地服务器准备在 http://localhost:5173 上运行
# ✓ 完成准备工作
```

### 阶段 2：浏览器测试 - Mock 模式

#### 步骤 1：检查左侧状态卡片（F1 验证）

打开 http://localhost:5173 后，检查 `<aside class="knowledge-rail">`区域：

| 状态卡 | 预期显示（Mock 模式） | 代码位置 |
|--------|---------------------|----------|
| **文档集合** | `加载中…`（小字） | `v-if="kbStats?.doc_count"` + `v-else` |
| **知识节点** | `加载中…`（小字） | `v-if="kbStats?.node_total"` + `v-else` |
| **索引健康度** | `加载中…`（小字） | `v-if="kbStats?.doc_count && kbStats?.node_total"` + `v-else` |
| **向量引擎** | `未配置`（状态：就绪） | `healthData?.embedder_class || '未配置'` |

```html
<!-- App.vue template - F1 修复验证点 -->
<div class="stat-card" aria-label="文档集合统计">
  <span class="stat-label">文档集合</span>
  <strong v-if="kbStats?.doc_count" :title="kbStats.index_dirname">{{ kbStats.doc_count }}</strong>
  <small v-else>加载中…</small>  <!-- F1: mock 模式 → 显示占位符 -->
</div>

<div class="stat-card" aria-label="知识节点统计">
  <span class="stat-label">知识节点</span>
  <strong v-if="kbStats?.node_total" :title="kbStats.index_dirname">{{ kbStats.node_total }}</strong>
  <small v-else>加载中…</small>
</div>
```

**预期验证结果：**
- ✅ 左侧状态卡显示 `加载中…`（因为 mock 模式下 kbStats 为 null）
- ✅ 向量引擎显示 `未配置`（因为没有 embedder_class）

#### 步骤 2：输入测试问题并观察（F1-F4 综合验证）

在 `<ChatInput>`组件中输入测试问题：

```text
ZRDDS 产品的核心功能是什么？
```

观察以下行为：

1. **流式生成阶段**（`isStreaming = true`）：
   - ✅ 左侧 Pipeline 状态更新：`01 问题解析 ✓ → 02 检索召回 (处理中…) → 03 重排与引用`
   - ✅ `isLoading = true`，显示骨架屏
   - ✅ 后端（mock）返回 mock token

2. **回答完成阶段**（`isStreaming = false`）：
   - ✅ 完整答案以 Markdown 渲染
   - ✅ **F2 验证**: DOMPurify.purify(marked(answer))防 XSS 正常工作
   - ✅ `sources.length > 0`时，显示 `<CitationsCard>`引用卡片

3. **CitationsCard 引用卡片**（F3 验证）：
   ```html
   <!-- F3: CitationsCard 绑定 mode 参数 -->
   <CitationsCard 
     v-if="sources.length" 
     :sources="sources" 
     :request-id="requestId" 
     :mode="knowledgeMode || 'mock'"  
   />
   ```

   **预期行为（Mock 模式）：**
   - ✅ 引用卡片正常渲染（如果 sources 有数据）
   - ✅ 点击`"查看节点详情"`**不发起 fetch**，直接显示静态提示
   - ✅ 字段占位符：`text: '-'`, `section_path: '-'`, `page_print: '-'`

#### 步骤 3：ChatInput experiments 测试（F4 验证）

检查 `<ChatInput :experiments="healthData?.experiments || []">` 组件：

```javascript
// ChatInput.vue - F4: experiments chip UI 实现
const handleExperimentSelect = (exp) => {
  // 处理实验模式切换逻辑
  console.log(`切换到实验模式：${exp.name}`)
}

function selectExperiment(exp) {
  mode.value = exp.mode || 'mock'
  if (experiments.includes(exp)) {
    experiments.value = experiments.filter(e => e !== exp)
  } else {
    experiments.value = [...experiments.value, exp]
  }
}
```

**预期行为（Mock 模式）：**
- ✅ 实验模式选择器正常显示（如果有 experiments 数据）
- ✅ 点击实验 chip 切换 mode
- ✅ CSS `.mode-selector-group/.experiment-chip`样式生效

#### 步骤 4：测试 CitationsCard 节点详情（F3 核心验证）

**场景 A：Mock 模式下的静态提示**

当 `sources.length > 0`时，每个引用卡片应该有"查看节点详情"按钮：

```html
<div class="action-area">
  <button
    v-if="requestId && canFetchDetails"
    class="view-details-btn"
    type="button"
    :disabled="isLoading(s, i)"
    @click="fetchAndShowDetails(s, i)"
  >
    <span>{{ isExpanded(s, i) ? '收起详情' : '查看节点详情' }}</span>
    <span class="detail-chevron" :class="{ 'is-open': isExpanded(s, i) }">⌄</span>
    <span v-if="isLoading(s, i)" class="inline-spinner"></span>
  </button>
  <span v-else class="no-details-tip">节点详情未开放</span>
</div>

<Transition name="details-expand">
  <div v-if="isExpanded(s, i)" class="details-panel">
    <!-- F3: Mock 模式显示静态提示 -->
    <pre v-else class="details-content">{{ formatDetails(detailsCache[sourceKey(s, i)]) }}</pre>
  </div>
</Transition>
```

**预期行为（Mock 模式）：**
- ✅ 点击"查看节点详情"按钮 → **不发起 fetch**，直接设置 `isExpanded = true`
- ✅ details-content 显示静态提示文本：
  ```text
  （模拟数据）此来源无额外节点详情
  
  字段示例：
  - text: '-'
  - section_path: '-'
  - page_print: '-'
  - source_url: '（未提供）'
  ```

### 阶段 3：预期测试场景覆盖

#### 场景 A：正常 mock 模式（无 sources）

```javascript
// healthz 响应示例（mock 模式）
{
  "status": "ok",
  "mode": "mock",
  "kb": null,        // mock 模式下为 null
  "experiments": [], // F4: experiments 白名单为空
}

// 前端表现：
// - kbStats = null（F1）
// - 左侧状态卡显示"加载中…"（F1 验证点）
// - healthData = null → 向量引擎显示"未配置"
// - ChatInput.experiments = []（F4 验证点）
// - CitationsCard 不渲染（sources.length === 0，非 F3 问题）
```

#### 场景 B：有 sources 数组的 mock 模式（测试引用详情功能）

假设后端返回 mock sources 数据（例如用于测试 F3）：

```javascript
// handleFrame 中的 sources 事件（mock 数据示例）
event: sources
data: {
  "request_id": "req-abc123",
  "sources": [
    {
      "node_id": "node_001",
      "source_name": "ZRDDS_User_Manual",
      "section": "安装与配置",
      "score": 0.85,
      "page_print": "-", // F3: mock 模式占位符
      "source_url": null, // mock 模式下可能为 null
      "graph_links": []   // mock 模式下为空数组
    }
  ]
}

// CitationsCard 表现（Mock 模式）：
// - 渲染 sources 数组（v-if="sources.length"通过）
// - page_print 显示为 "-"
// - 点击"查看节点详情"按钮 → 
//   ❌ NOT: fetch(`/nodes/${node_id}`)
//   ✅ YES: 直接设置 isExpanded = true，显示静态提示
```

#### 场景 C：Live 模式对比（用于验证 mode 参数传递）

```javascript
// Live 模式下（构建索引后）
// healthz 响应示例：
{
  "status": "ok",
  "mode": "live",
  "kb": {
    "doc_count": 1520,
    "node_total": 28450,
    "index_dirname": "struct_v1"
  },
  "embedder_class": "bge-m3",
  "experiments": []
}

// 前端表现（Live 模式）：
// - kbStats = { doc_count: '1520', node_total: '28450' }（F1 验证）
// - 左侧状态卡显示实际统计数据（不再是"加载中…"）
// - healthData.embedder_class = 'bge-m3'（向量引擎显示"BGE-M3"）
// - knowledgeMode.value = 'live' → CitationsCard mode prop = 'live'（F3 验证）

// CitationsCard.fetchAndShowDetails() 中的行为差异：
// Mock 模式 (mode === 'mock'):
//   const isInLiveMode = false
//   // 不发起 fetch，直接显示静态提示

// Live 模式 (mode === 'live'):
//   const isInLiveMode = true
//   if (isInLiveMode) {
//     const response = await fetch(`/nodes/${source.node_id}`)
//     if (response.ok) {
//       detailsCache[key] = await response.json()
//     }
//   } else {
//     // 显示静态提示文本
//   }
```

## 🛠️ F1-F4 修复验证清单（详细）

### F1: UI modification（已完成）

| 测试点 | 预期结果 | 状态 | 代码位置 |
|--------|----------|------|----------|
| **kbStats.doc_count绑定** | mock 模式显示 `加载中…`，live 模式显示实际数字 | ✅ | App.vue line 46-49 |
| **kbStats.node_total绑定** | mock 模式显示 `加载中…`，live 模式显示实际数字 | ✅ | App.vue line 51-53 |
| **索引健康度计算** | mock 模式下显示 `加载中…`（需要两个值都存在） | ✅ | App.vue line 55-61 |
| **index_dirname title 提示** | tooltip 显示当前 index 目录名 | ✅ | App.vue: `:title="kbStats.index_dirname"` |

```html
<!-- App.vue - F1 修复验证点 -->
<div class="stat-card" aria-label="文档集合统计">
  <span class="stat-label">文档集合</span>
  <!-- F1: mock 模式 → v-else 分支显示占位符 -->
  <strong v-if="kbStats?.doc_count" :title="kbStats.index_dirname">{{ kbStats.doc_count }}</strong>
  <small v-else>加载中…</small>
</div>
```

**验证方法：**
1. 启动 mock 模式后端
2. 观察左侧状态卡，确认显示 `加载中…`
3. 启动 live 模式（需要构建索引）
4. 重新加载前端页面
5. 确认显示实际统计数据

### F1: fetch logic（已完成）

| 测试点 | 预期结果 | 状态 | 代码位置 |
|--------|----------|------|----------|
| **/healthz API 调用** | onMounted 成功 fetch，返回 health 对象 | ✅ | App.vue onMounted() |
| **mock 模式数据处理** | kbStats = null，左侧显示占位符 | ✅ | App.vue line 91-104 |
| **live 模式数据处理** | kbStats = {doc_count, node_total}，左侧显示实际数据 | ✅ | App.vue line 92-95 |
| **embedder_class 提取** | health.embedder_class → healthData.embedder_class | ✅ | App.vue line 107-114 |
| **experiments 白名单传递** | healthData.experiments → ChatInput 绑定 | ✅ | App.vue line 139 |

```javascript
// App.vue onMounted - F1 修复验证点
onMounted(async () => {
  try {
    const response = await fetch('/healthz')
    if (!response.ok) throw new Error(`健康检查失败：${response.status}`)
    const health = await response.json()
    
    knowledgeStatus.value = health.status === 'ok' ? 'online' : 'offline'
    knowledgeMode.value = health.mode || ''
    
    // F1: 提取 kb_stats (doc_count, node_total, index_dirname)
    const kb = health.kb || {}
    if (kb && kb.node_total !== undefined) {
      kbStats.value = { 
        doc_count: kb.doc_count ?? '', 
        node_total: kb.node_total,
        index_dirname: kb.index_dirname || ''
      }
    } else {
      kbStats.value = null  // mock 模式下通常为 null
    }
    
    // F1: 提取 vector_engine (embedder_class, status)
    if (health.embedder_class) {
      healthData.value = { embedder_class: health.embedder_class, status: 'active' }
    } else {
      healthData.value = null
    }
    
  } catch (error) {
    console.error('知识库服务健康检查失败:', error)
    knowledgeStatus.value = 'offline'
    kbStats.value = null
    healthData.value = null
  }
})
```

### F2: markdown rendering（已完成）

| 测试点 | 预期结果 | 状态 | 代码位置 |
|--------|----------|------|----------|
| **DOMPurify import** | App.vue script setup 中导入 dompurify | ✅ | App.vue line 4 |
| **purify()函数实现** | DOMPurify.sanitize()XSS 防护 | ✅ | App.vue line 120-127 |
| **marked 渲染回答** | answer → marked() → purify() → innerHTML | ✅ | App.vue line 168 |

```javascript
// App.vue - F2: DOMPurify XSS 防护辅助函数
import DOMPurify from 'dompurify'  // import 语句

function purify(html) {
  if (!DOMPurify) return html // 降级处理
  try {
    return DOMPurify.sanitize(html)
  } catch (e) {
    console.error('DOMPurify 净化失败:', e)
    return html
  }
}

// template - F2: Markdown 渲染（marked + DOMPurify 防 XSS）
<div [innerHTML]="purify(marked(answer))" class="streaming-response"></div>
```

**XSS 测试用例：**

| 输入内容 | 预期处理后 | 验证点 |
|----------|-----------|--------|
| `<img src=x onerror=alert(1)>` | `<img src=x>`（移除 onerror） | DOMPurify 成功过滤事件处理器 |
| `javascript:alert('xss')` | 保留原样（纯文本） | 非 HTML 标签不处理 |
| `onclick="alert('hi')" 点击我` | 保留原样（属性未闭合） | 需要完整 HTML 结构才会被解析 |

### F3: CitationsCard mode（已完成）

| 测试点 | 预期结果 | 状态 | 代码位置 |
|--------|----------|------|----------|
| **mode prop 绑定** | :mode="knowledgeMode || 'mock'"传递正确默认值 | ✅ | App.vue line 135-136 |
| **Mock 模式 fetch 禁用** | canFetchDetails = false时，不发起 fetch | ✅ | CitationsCard.vue line 97, 145-174 |
| **静态提示显示** | text/section_path/page_print 为占位符 `-` | ✅ | CitationsCard 详情面板 pre 元素 |

```html
<!-- App.vue - F3: 传递 mode 参数给 CitationsCard -->
<CitationsCard 
  v-if="sources.length" 
  :sources="sources" 
  :request-id="requestId" 
  :mode="knowledgeMode || 'mock'"  
/>
```

```javascript
// CitationsCard.vue - F3: Mock vs Live 模式行为差异
const isInLiveMode = computed(() => props.mode === 'live') // mock 模式为 false

async function fetchAndShowDetails(source, index) {
  if (!source?.node_id || !canFetchDetails.value) return
  
  const key = sourceKey(source, index)
  
  // F3: Mock vs Live 模式行为差异
  if (isInLiveMode.value) {
    // ✅ Live 模式：发起 fetch 调用
    try {
      const response = await fetch(`/nodes/${source.node_id}`)
      if (response.ok) {
        detailsCache[key] = await response.json()
        loadingDetails.value[key] = false
      } else {
        detailErrors[key] = '获取节点详情失败'
      }
    } catch (error) {
      console.error(error)
      detailErrors[key] = error.message
    }
  } else {
    // ✅ Mock 模式：显示静态提示，不发起 fetch
    detailsCache[key] = `(模拟数据) 此来源无额外节点详情`
    loadingDetails.value[key] = false
  }
}

// F3: Mock 模式下字段占位符（通过 formatDetails()处理）
function formatDetails(details) {
  const d = details || {}
  return `text: ${d.text ?? '-'}\nsection_path: ${d.section_path ?? '-'}\npage_print: ${d.page_print ?? '-'}`
}
```

### F4: ChatInput experiments（已完成）

| 测试点 | 预期结果 | 状态 | 代码位置 |
|--------|----------|------|----------|
| **experiments prop 绑定** | :experiments="healthData?.experiments || []" | ✅ | App.vue line 139 |
| **mode-selector-group 样式** | CSS .mode-selector-group/.experiment-chip生效 | ✅ | ChatInput.vue styles |
| **selectExperiment()函数** | 处理实验模式切换逻辑 | ✅ | ChatInput.vue handleExperimentSelect() |

```html
<!-- App.vue - F4: 传递 experiments 白名单 -->
<ChatInput 
  :loading="isLoading" 
  :has-answer="hasContent" 
  @submit="handleQuery" 
  :experiments="healthData?.experiments || []"  
/>
```

```javascript
// ChatInput.vue - F4: experiments chip UI 实现
const handleExperimentSelect = (exp) => {
  console.log(`切换到实验模式：${exp.name}`)
}

function selectExperiment(exp) {
  mode.value = exp.mode || 'mock'
  if (experiments.includes(exp)) {
    experiments.value = experiments.filter(e => e !== exp)
  } else {
    experiments.value = [...experiments.value, exp]
  }
}

// template - F4: experiments prop 绑定
<ChatInput 
  :loading="isLoading" 
  :has-answer="hasContent" 
  @submit="handleQuery" 
  :experiments="healthData?.experiments || []"  
/>
```

## 📊 Mock vs Live 模式行为对比表

| 特性 | Mock 模式（开发测试） | Live 模式（生产环境） |
|------|----------------------|----------------------|
| **knowledgeMode.value** | `'mock'`（默认） | `'live'` |
| **health.kb** | `null` | `{doc_count, node_total, ...}` |
| **kbStats 绑定结果** | `null` → 显示"加载中…" | `{doc_count, node_total}` → 显示实际数据 |
| **health.embedder_class** | 不存在 → `healthData = null` | `'bge-m3'`或其他 → `healthData.embedder_class` |
| **向量引擎显示** | `未配置` | `BGE-M3`等嵌入模型名称 |
| **CitationsCard mode prop** | `'mock'` | `'live'` |
| **fetchAndShowDetails()行为** | 不发起 fetch，显示静态提示 | 发起 `/nodes/{node_id}` fetch |
| **字段填充值** | `text: '-'`, `page_print: '-'`等占位符 | 实际来源数据内容 |
| **sources 事件触发** | 仅在 mock 数据生成时触发 | 真实检索后触发 |
| **适用场景** | 开发测试、功能验证、调试 | 生产环境、真实查询 |

## 🧪 自动化测试建议（成员 E）

### 手动测试检查清单

- [ ] **阶段 1**: 后端启动，`curl http://localhost:8000/healthz`返回预期响应
- [ ] **阶段 2**: 前端启动，打开 http://localhost:5173
- [ ] **F1 验证**: 左侧状态卡显示"加载中…"（mock 模式）
- [ ] **F1 验证**: 输入测试问题，观察流式生成过程
- [ ] **F2 验证**: 检查 Markdown 渲染是否正常，无 XSS 注入迹象
- [ ] **F3 验证**: CitationsCard 引用卡片显示占位符内容
- [ ] **F3 验证**: 点击"查看节点详情"后，不发起网络请求（检查 Network 面板）
- [ ] **F4 验证**: ChatInput experiments chip UI 正常显示（如果有实验模式）

### 自动化测试脚本建议

```python
# tests/test_mock_mode.py - 建议的自动化测试

import pytest
from fastapi.testclient import TestClient
from server.main import app

client = TestClient(app)

def test_healthz_mock_mode():
    """验证 /healthz 在 mock 模式下返回正确响应"""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["mode"] == "mock"
    assert data["kb"] is None
    
def test_healthz_live_mode():
    """验证 /healthz 在 live 模式下返回 kb_stats"""
    # 需要构建索引后运行
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["mode"] == "live"
    assert data["kb"]["doc_count"] > 0
    
def test_query_mock_mode():
    """验证查询接口在 mock 模式下返回 mock 响应"""
    response = client.post("/query", json={"question": "ZRDDS 是什么？"})
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "sources" in data
    
# pytest -v tests/test_mock_mode.py
```

## ⚠️ 已知限制与注意事项

### Mock 模式下的功能限制

1. **CitationsCard 不渲染**（当 `kbStats = null`时）
   - 原因：`v-if="sources.length"`条件判断，mock 模式下 sources 为空数组
   - 影响：无法测试 F3 CitationsCard 的 mock 模式行为
   - 解决：需要在 mock 数据中注入 sources 测试用例

2. **左侧状态卡显示"加载中…"**
   - 原因：`kbStats = null`，触发 `v-else`分支
   - 影响：无法验证索引健康度进度条功能
   - 解决：live 模式构建索引后切换测试

3. **无真实检索数据展示**
   - 原因：后端不执行真实检索，只返回 mock 响应
   - 影响：无法测试真实场景下的引用来源功能
   - 接受：这是 Mock 模式的预期行为

### 切换到 Live 模式的操作步骤

```bash
# 1. 构建索引（首次运行时需要）
make build_index

# 2. 设置环境变量并启动后端
SAGEMAKER_ENDPOINT=https://your-sagemaker-endpoint.com \
RAG_MODE=live \
python -m server.main

# 3. 前端会自动检测到 mode 变化（通过 /healthz响应）
# 4. 刷新浏览器页面以获取最新的 healthData
```

### Mock/Live 切换时的注意事项

| 切换方向 | 需要操作 | 原因 |
|----------|---------|------|
| **Mock → Live** | 刷新前端页面 | 健康检查检测到 mode 变化，重新获取 healthData |
| **Live → Mock** | 无需操作（自动回退） | onMounted 重新 fetch，mock 模式时 kbStats = null |

## 📝 测试完成后的工作清单

如果所有 Mock 模式测试通过：

1. ✅ **清理 mock 数据**：删除任何仅用于测试的占位符
2. ✅ **准备 live 环境**：运行 `make build_index` 构建生产索引
3. ✅ **启用 live 模式**：设置`RAG_MODE="live"`并重启服务
4. ✅ **文档更新**：记录测试结果和问题修复情况

## 🔍 调试与故障排查

### 常见问题及解决方案

#### 问题 1: 左侧状态卡一直显示"加载中…"

```javascript
// App.vue - 检查 onMounted 是否正确执行
onMounted(async () => {
  try {
    const response = await fetch('/healthz')
    console.log('Healthz 响应:', response.status) // 调试输出
    const health = await response.json()
    console.log('Health 数据:', health)
    
    if (health.mode === 'mock') {
      console.warn('检测到 Mock 模式，kbStats 为 null')
      kbStats.value = null
    }
  } catch (error) {
    console.error('健康检查失败:', error)
    kbStats.value = null
  }
})
```

**解决方案：**
- 确认后端服务运行在 mock 模式
- 检查 Network 面板，确认 `/healthz`请求成功（状态码 200）

#### 问题 2: CitationsCard 点击"查看节点详情"后发起网络请求（不符合预期）

```javascript
// CitationsCard.vue - 检查 isInLiveMode 计算属性
console.log('Current mode:', props.mode) // 应该为'mock'
console.log('Is Live Mode?', isInLiveMode.value) // 应该为 false
```

**解决方案：**
- 确认 `:mode="knowledgeMode || 'mock'"`绑定正确传递了 mock 模式
- 检查 App.vue 中 knowledgeMode.value 的值

#### 问题 3: DOMPurify 导入失败

```javascript
// App.vue - 确保 dompurify 已安装
npm install dompurify
# 或
pnpm add dompurify
# 或
yarn add dompurify
```

## 📚 参考资料

- **F1-F4 需求文档**: `evaluation/delivery-guide.md`（成员 E 责任范围）
- **后端 API 文档**: `docs/api.md` (v0.14)
- **Chunking 规范**: `docs/chunking-defect-report.md`
- **Week4 Encoding Issue**: `docs/week4-delivery-review.md`

---

**文档版本历史：**
- v1.0 (2026-09-16): 初始版本，成员 E 编写
  - 覆盖 F1-F4 完整验证流程
  - 包含 Mock/Live 模式对比表
  - 添加自动化测试建议

**需要帮助？** 联系团队成员或提供浏览器控制台错误日志。

## 🔗 相关文档链接

| 文档 | 路径 | 说明 |
|------|------|------|
| API 文档 | `docs/api.md` | v0.14 接口规范 |
| Chunking 规范 | `docs/chunking-defect-report.md` | 分块实现缺陷报告 |
| Week4 编码问题 | `docs/week4-delivery-review.md` | 编码问题修复记录 |

---

**End of Document - Member E Edition v1.0 (2026-09-16)**
