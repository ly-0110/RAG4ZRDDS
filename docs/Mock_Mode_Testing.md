# Mock_Mode_Testing — CitationsCard 模拟模式行为验证指南

> 说明：本文档基于 `CitationsCard.vue` 实际代码逻辑编写，**不虚构 mock 静态提示语**。
> 
> 真实行为总结：
> - mock 模式下 CitationsCard **仍会渲染来源卡片**（只要 `sources.length > 0`）
> - 用户点击"查看节点详情"时，仅当`isInLiveMode.value === true`才会调用 `/nodes/{node_id}`
> - mock 模式下节点详情面板显示内容为空对象，格式化后为 `{}` 或 JSON 空对象状态

---

## 一、测试环境准备

### 1.1 启动 Mock 后端服务

```powershell
# PowerShell 7+ 使用 Start-Process 后台运行（避免&符号限制）
Start-Process powershell -ArgumentList "-NoExit","-Command","cd 'c:\Users\ycfnc\Documents\GitHub\RAG4ZRDDS'; uvicorn server.main:app --host 127.0.0.1 --port 8001"

# 或使用终端模式启动
$env:RAG_MODE='mock'
uvicorn server.main:app --host 127.0.0.1 --port 8001
```

### 1.2 验证服务就绪

```powershell
curl.exe -s http://127.0.0.1:8001/healthz | ConvertFrom-Json
# 预期响应：
# {
#   "status": "ok",
#   "mode": "mock",
#   "kb_stats": null,
#   "experiments": null
# }
```

### 1.3 前端准备（可选）

如前端未启动，则：

```powershell
cd web\RAG4ZRDDS
npm run dev
```

浏览器访问 `http://localhost:5173`。

---

## 二、CitationsCard 真实行为分析

### 2.1 核心代码逻辑（从 CitationsCard.vue）

```vue
<!-- 判断是否在 live 模式 -->
const isInLiveMode = computed(() => props.mode === 'live')

// F3: live 模式下调用 /nodes/{node_id} 获取节点详情
if (isInLiveMode.value && source.node_id) {
  const response = await fetch(`/nodes/${source.node_id}`)
  // ... 绑定响应到 detailsCache
} else {
  // mock 模式分支
  setRecord(detailsCache, key, {
    text: '',                          // text 为空字符串（非虚构提示语）
    section_path: '-',
    page_print: '-',
    source_url: source.source_url || null,
    raw_node: {},                     // 空对象，非静态文本占位
  })
}
```

### 2.2 关键结论

| 模式 | isInLiveMode.value | fetchAndShowDetails() 行为 | 详情面板内容 |
|------|-------------------|---------------------------|--------------|
| mock | `false` | **不发起真实请求**，直接进入 mock 分支 | 空对象格式化 → `{}` |
| live | `true` | 发起 `/nodes/{node_id}` 请求 | 绑定节点详情字段 |

> ⚠️ **重要纠正**：  
> 之前文档错误声称"mock 模式显示静态提示语（模拟数据）此来源无额外节点详情"，实际代码并未实现该文本。  
> 当`isInLiveMode.value === false`时，直接构造空对象 `{}`，格式化后为 JSON 空对象。

---

## 三、测试步骤与观察结果

### 3.1 基础渲染验证

#### 步骤：确保 `sources.length > 0`

- mock 模式下 CitationsCard **仍会渲染**（由模板中的 `v-if="sources.length"` 控制）
- 卡片标题显示来源数量、平均相关度等信息
- 来源列表正常展示字段（标题、类型、页码、相关度等）

#### 预期 UI：

```
EVIDENCE GRAPH
来源与知识关联
已从 X 份文档中筛选 Y 个证据节点

[来源卡片 1]
来源名称 · 章节名
第 N 页 · [页数]· ...
向量相关度 XX% [条形图]
...
节点详情未开放          ← 当 canFetchDetails=false 或 requestId 空
```

### 3.2 点击"查看节点详情"的行为验证

#### 前提条件：

- `requestId.length > 0`（mock 模式健康数据可为空，需注入测试用 requestId）
- `canFetchDetails.value = (requestId && requestId.length > 0)`

#### 预期交互序列：

1. **首次点击** "查看节点详情"
   - loading 骨架屏短暂显示
   - 进入 mock 分支（因`isInLiveMode.value === false`）
   - detailsCache[key] = `{ text: '', section_path: '-', page_print: '-', source_url: ..., raw_node: {} }`

2. **展开面板后**
   - `formatDetails(details)` → JSON.stringify({}, null, 2) → 空对象格式化输出
   - UI 显示：
     ```json
     {
       "text": "",
       "section_path": "-",
       "page_print": "-",
       "source_url": null,
       "raw_node": {}
     }
     ```

3. **再次点击"收起详情"** → 面板收起（Transition 动画）

4. **再次展开**
   - 因缓存命中，直接显示空对象（不会重复请求）

---

## 四、Mock vs Live 行为对比表

| 行为维度 | mock 模式 | live 模式 |
|----------|-----------|-----------|
| CitationsCard 渲染 | `sources.length > 0` → **会渲染** | 同上 |
| isInLiveMode.value | `false` | `true` |
| 点击"查看节点详情" | 不发起 fetch，直接构造空对象 | 发起 `/nodes/{node_id}` 请求 |
| 详情面板内容 | JSON 空对象 `{}` 或字段占位符 | 真实节点数据（text/section_path 等） |
| 错误处理 | 无网络错误 | 可能返回 500/404 等状态 |

---

## 五、注入测试数据的后端示例

如需手动注入带 requestId 的健康数据（触发 canFetchDetails=true），可调用：

```bash
curl -X POST "http://127.0.0.1:8001/sources" ^
  -H "Content-Type: application/json" ^
  -d '[
    {
      "source_name": "用户手册",
      "section": "安装说明",
      "page_print": "3",
      "score": 0.92,
      "node_id": "manual-install-v1",
      "source_url": "http://example.com/manual.html#install"
    }
  ]'
```

或修改 `healthz` 响应注入（需后端支持）：

---

## 六、常见问题与排查

### Q1: mock 模式下详情面板完全空白（非 JSON 对象）？

**可能原因：**
- `sources.length === 0` → CitationsCard 未渲染
- `requestId === ''` → canFetchDetails=false，按钮显示"节点详情未开放"

**解决方案：**
```bash
curl http://127.0.0.1:8001/healthz
# 检查 experiments 字段（mock 模式应为 null）
# 如需触发 canFetchDetails，需注入非空的 requestId
```

### Q2: "查看节点详情"按钮点击无反应？

**可能原因：**
- 按钮被`disabled=""`属性禁用（因 isLoading=true 或 canFetchDetails=false）
- 网络请求失败进入 catch 分支

**排查步骤：**
1. 打开浏览器 DevTools → Network 标签
2. 确认是否有 `/nodes/{node_id}` 请求（mock 模式不应有）
3. 检查 Console 是否报错

### Q3: 如何验证 mock 模式未发起真实请求？

```bash
# 在启动后端同一机器上监听/nodes 端口流量
netstat -an | findstr :8001
# 或浏览器 DevTools → Network → Filter → 无/nodes/请求

# mock 模式下 healthz 响应：
curl http://127.0.0.1:8001/healthz
# 返回 experiments=null，确认未加载实验配置
```

---

## 七、测试用例清单（Test Cases）

| ID | 场景 | 预期结果 |
|----|------|----------|
| TC-01 | mock 模式渲染 CitationsCard（sources.length>0） | 卡片正常显示，无错误 |
| TC-02 | canFetchDetails=false（requestId='') | 按钮显示"节点详情未开放" |
| TC-03 | canFetchDetails=true + 点击展开（mock） | 详情面板显示 JSON 空对象 |
| TC-04 | mock 模式多次展开/收起 | 缓存命中，无重复请求 |
| TC-05 | sources 为空数组 | CitationsCard 不渲染 |

---

## 八、Live 模式对比测试（可选）

如需验证 live 模式行为：

1. 停止 mock 服务
2. `make build_index` 构建索引
3. 启动 live 后端：
   ```powershell
   $env:RAG_MODE='live'
   uvicorn server.main:app --host 127.0.0.1 --port 8002
   ```
4. 前端访问 `/healthz` → mode=live, kb_stats 有值
5. CitationsCard 点击展开 → 显示真实节点详情

---

## 附录：CitationsCard 关键代码片段

```vue
<!-- 模板部分 -->
<button
  v-if="requestId && canFetchDetails"
  class="view-details-btn"
  :disabled="isLoading(s, i)"
  @click="fetchAndShowDetails(s, i)"
>
  <span>{{ isExpanded ? '收起详情' : '查看节点详情' }}</span>
</button>
<span v-else class="no-details-tip">节点详情未开放</span>

<Transition name="details-expand">
  <div v-if="isExpanded" class="details-panel">
    <p v-else-if="detailErrors[key]" class="details-error">
      暂时无法加载详情，请稍后重试。
    </p>
    <pre v-else class="details-content">{{ formatDetails(detailsCache[key]) }}</pre>
  </div>
</Transition>

<!-- script setup 部分 -->
const isInLiveMode = computed(() => props.mode === 'live')
const canFetchDetails = computed(() => props.requestId && props.requestId.length > 0)

// mock 分支构造空对象（非静态文本）
setRecord(detailsCache, key, {
  text: '',
  section_path: '-',
  page_print: '-',
  raw_node: {},
})
```

---

**文档版本：** v1.0  
**最后更新：** 2026-09-03  
**相关组件：** `CitationsCard.vue`、`server/core/settings.py`  
**测试环境：** FastAPI mock 模式（8001）、Vue 3 前端（5173）
