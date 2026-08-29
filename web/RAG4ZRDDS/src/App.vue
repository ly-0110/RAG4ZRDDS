<template>
  <div class="chat-container">
    <!-- 输入框组件：提交动作经 submit 事件进入本组件统一处理 -->
    <ChatInput
      :loading="isLoading"
      :has-answer="hasContent"
      @submit="handleQuery"
    />

    <!-- 回答区域：引用卡片（evidence-first）→ 流式答案 → 错误 -->
    <div v-if="isStreaming" class="response-section">
      <div class="loading-spinner" v-if="isLoading && !sources.length && !answer">
        <p>正在检索...</p>
      </div>

      <!-- 来源引用卡片（docs/api.md：sources 事件，双页码 +7 约定） -->
      <div v-if="sources.length" class="sources-block">
        <h3 class="sources-title">来源引用（{{ sources.length }}）</h3>
        <div
          v-for="(s, i) in sources"
          :key="s.node_id"
          class="source-card"
        >
          <div class="source-title">
            [{{ i + 1 }}] {{ s.source_name }} · {{ s.section }}
          </div>
          <div class="source-meta">
            第 {{ s.page_print }} 页（物理页 {{ s.page_physical }}） ·
            相关度 {{ Number(s.score).toFixed(3) }} · {{ s.source_id }}
          </div>
        </div>
      </div>

      <!-- 流式答案正文 -->
      <pre v-if="answer" class="streaming-response">{{ answer }}</pre>

      <!-- 流中错误（error 事件的唯一展示通道） -->
      <div v-if="errorMsg" class="error-box">{{ errorMsg }}</div>
    </div>

    <!-- 空状态提示 -->
    <div v-else class="empty-state">
      <p>💡 提示：输入问题后按 Enter 或点击提问</p>
    </div>
  </div>
</template>

<script setup>
// 问答页面主控（2026-08-29 接线修复）：
//  * 请求走相对路径 /query，由 vite dev server 代理到后端（见 vite.config.js）
//  * 按 docs/api.md 的事件协议解析 SSE 四种事件：sources / token / done / error
//  * sources → 渲染引用卡片；token → 增量拼答案；done → 收尾；error → 可读错误框
import { ref, computed } from 'vue'
import ChatInput from './components/ChatInput.vue'

const API_URL = '/query' // dev 代理 → http://localhost:8000（vite.config.js）

const answer = ref('')
const sources = ref([])
const errorMsg = ref('')
const isLoading = ref(false)
const isStreaming = ref(false)
const hasContent = computed(() => answer.value !== '' || sources.value.length > 0)
let abortController = null

// 一帧 = "event: 名称\ndata: JSON"，以空行结束。逐帧分派到对应事件处理。
function handleFrame(frame) {
  let eventName = 'message'
  const dataLines = []
  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) eventName = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  if (!dataLines.length) return
  let payload
  try {
    payload = JSON.parse(dataLines.join('\n'))
  } catch {
    return
  }
  if (eventName === 'sources') {
    sources.value = payload.sources || []
  } else if (eventName === 'token') {
    answer.value += payload.text
  } else if (eventName === 'done') {
    answer.value = payload.answer
    sources.value = payload.sources || sources.value
  } else if (eventName === 'error') {
    errorMsg.value = payload.error
  }
}

const handleQuery = async (question) => {
  if (!question.trim()) return

  // 复位上一轮状态，取消未完成的旧请求
  abortController?.abort()
  abortController = new AbortController()
  answer.value = ''
  sources.value = []
  errorMsg.value = ''
  isStreaming.value = true
  isLoading.value = true

  try {
    const response = await fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
      signal: abortController.signal,
    })

    if (!response.ok) {
      // 流开始前的错误：HTTP 4xx/5xx + JSON 体 {error}（docs/api.md 双通道约定）
      const body = await response.json().catch(() => null)
      throw new Error(body?.error || `HTTP ${response.status} ${response.statusText}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      // SSE 帧之间以空行（\n\n）分隔；半帧留在 buffer 等待下次 read
      let sep
      while ((sep = buffer.indexOf('\n\n')) >= 0) {
        const frame = buffer.slice(0, sep)
        buffer = buffer.slice(sep + 2)
        handleFrame(frame)
      }
    }
  } catch (error) {
    if (error.name !== 'AbortError') {
      errorMsg.value = `请求失败：${error.message}（请确认后端已启动：make serve）`
      console.error('查询失败:', error)
    }
  } finally {
    isLoading.value = false
  }
}
</script>

<style scoped>
.chat-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.response-section {
  min-height: 100px;
  padding: 15px;
  border: 1px solid #eee;
  border-radius: 8px;
  background-color: #f9f9f9;
}

.sources-block {
  margin-bottom: 12px;
}

.sources-title {
  font-size: 14px;
  color: #555;
  margin: 0 0 8px;
}

.source-card {
  border: 1px solid #dbe7f3;
  background: #fff;
  border-radius: 8px;
  padding: 8px 12px;
  margin-bottom: 8px;
}

.source-title {
  font-size: 14px;
  font-weight: 600;
  color: #1a5276;
  margin-bottom: 4px;
}

.source-meta {
  font-size: 12px;
  color: #777;
}

.streaming-response {
  white-space: pre-wrap;
  word-wrap: break-word;
  line-height: 1.6;
  color: #333;
  margin: 0;
}

.error-box {
  border: 1px solid #f5c6cb;
  background: #f8d7da;
  color: #721c24;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 14px;
  margin-top: 10px;
}

.loading-spinner {
  text-align: center;
  padding: 20px;
  color: #666;
}

.empty-state {
  text-align: center;
  color: #999;
  padding: 40px;
}
</style>
