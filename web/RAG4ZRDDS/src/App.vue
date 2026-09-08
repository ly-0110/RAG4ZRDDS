<template>
  <div class="app-shell">
    <div class="app-panel">
      <header class="topbar">
        <div class="brand-group">
          <div class="brand-mark" aria-hidden="true">
            <span>R</span>
            <i></i>
          </div>
          <div>
            <p class="brand-name">RAG4ZRDDS</p>
            <p class="brand-subtitle">面向 ZRDDS 文档的检索增强问答工作台</p>
          </div>
        </div>
        <div class="topbar-meta">
          <span class="system-version">RAG pipeline · 2.4</span>
          <span class="status-pill">
            <span class="status-dot" aria-hidden="true"></span>
            {{ knowledgeStatusLabel }}
          </span>
        </div>
      </header>

      <div class="workspace-grid">
        <aside class="knowledge-rail" aria-label="知识库状态概览">
          <div class="rail-heading">
            <div>
              <p class="eyebrow">SYSTEM OVERVIEW</p>
              <h2>知识库状态</h2>
            </div>
            <span class="online-mark" :aria-label="knowledgeStatusLabel"></span>
          </div>

          <div class="stat-grid">
            <div class="stat-card">
              <span class="stat-label">文档集合</span>
              <strong>—</strong>
              <small>占位数据：未接入知识库统计接口</small>
            </div>
            <div class="stat-card">
              <span class="stat-label">知识节点</span>
              <strong>—</strong>
              <small>占位数据：未接入节点统计接口</small>
            </div>
            <div class="stat-card stat-card-wide">
              <div class="stat-heading">
                <span class="stat-label">索引健康度 · 占位</span>
                <strong>—</strong>
              </div>
              <div class="progress-track" aria-label="索引健康度暂无真实数据">
                <span style="width: 0%"></span>
              </div>
              <small>占位数据：未接入索引健康检查</small>
            </div>
          </div>

          <div class="rail-divider"></div>

          <section class="pipeline-panel" aria-labelledby="pipeline-title">
            <div class="panel-heading">
              <div>
                <p class="eyebrow">LIVE TRACE · SSE 状态推断</p>
                <h3 id="pipeline-title">检索流程 · 前端推断</h3>
              </div>
              <span class="trace-id">{{ requestId ? requestId.slice(-6) : 'IDLE' }}</span>
            </div>
            <ol class="pipeline-list">
              <li v-for="step in pipelineSteps" :key="step.key" :class="pipelineClass(step.key)">
                <span class="pipeline-node">
                  <span v-if="pipelineClass(step.key) === 'done'">✓</span>
                  <span v-else>{{ step.number }}</span>
                </span>
                <span class="pipeline-copy">
                  <strong>{{ step.label }}</strong>
                  <small>{{ pipelineStateLabel(step.key) }}</small>
                </span>
                <span v-if="step.key !== 'generate'" class="pipeline-connector" aria-hidden="true"></span>
              </li>
            </ol>
          </section>

          <div class="engine-card">
            <div class="engine-icon" aria-hidden="true">⌁</div>
            <div>
              <span class="stat-label">向量引擎</span>
              <strong>—</strong>
              <small>占位数据：未从服务端返回引擎信息</small>
            </div>
            <span class="engine-status">占位</span>
          </div>
        </aside>

        <main class="chat-workspace">
          <div class="conversation-column">
            <div class="workspace-intro">
              <div>
                <p class="eyebrow">CONTEXT-AWARE ANSWERS</p>
                <h1>从知识库中，找到可信的答案。</h1>
                <p class="intro-copy">输入一个问题，系统会检索相关片段、重排证据，并在回答中保留可追溯引用。</p>
              </div>
              <div class="intro-signal">
                <span class="signal-ring" aria-hidden="true"></span>
                <span>{{ isLoading ? '正在分析上下文' : '等待新的问题' }}</span>
              </div>
            </div>

            <ChatInput
              :loading="isLoading"
              :has-answer="hasContent"
              @submit="handleQuery"
            />

            <Transition name="section-fade" mode="out-in">
              <div v-if="isStreaming" class="response-section" aria-live="polite" :aria-busy="isLoading">
                <div class="response-heading">
                  <div>
                    <p class="eyebrow">RETRIEVAL OUTPUT</p>
                    <h2>回答与证据</h2>
                  </div>
                  <span class="response-state" :class="{ 'is-loading': isLoading }">
                    <span class="state-dot"></span>
                    {{ isLoading ? '流式生成中' : '已完成' }}
                  </span>
                </div>

                <CitationsCard
                  v-if="sources.length"
                  :sources="sources"
                  :request-id="requestId"
                />

                <Transition name="answer-fade" mode="out-in">
                  <div v-if="isLoading && !answer" key="answer-loading" class="answer-skeleton" aria-label="正在生成回答">
                    <div class="skeleton-heading skeleton-shimmer"></div>
                    <div class="skeleton-line skeleton-shimmer"></div>
                    <div class="skeleton-line skeleton-line-wide skeleton-shimmer"></div>
                    <div class="skeleton-line skeleton-line-short skeleton-shimmer"></div>
                    <div class="skeleton-status">
                      <span class="loading-dot"></span>
                      <span>正在检索并整理答案…</span>
                    </div>
                  </div>
                  <div v-else-if="answer" key="answer-content" class="answer-card">
                    <div class="section-header">
                      <span class="section-badge">GENERATED ANSWER</span>
                      <span class="answer-meta">来源已校验 · 置信回答</span>
                    </div>
                    <pre class="streaming-response">{{ answer }}</pre>
                  </div>
                </Transition>

                <Transition name="answer-fade">
                  <div v-if="errorMsg" class="error-box">
                    <span class="error-label">请求异常</span>
                    <p>{{ errorMsg }}</p>
                  </div>
                </Transition>
              </div>

              <div v-else key="empty-state" class="empty-state">
                <div class="empty-card">
                  <div class="empty-icon" aria-hidden="true">
                    <span>✦</span>
                    <i></i>
                  </div>
                  <p class="eyebrow">READY TO RETRIEVE</p>
                  <h2>开始一次有依据的提问</h2>
                  <p>我会先定位相关来源，再给出准确回答与引用证据。所有检索步骤都会在左侧实时展示。</p>
                  <div class="empty-capabilities">
                    <span>语义检索</span>
                    <span>引用优先</span>
                    <span>上下文重排</span>
                  </div>
                </div>
              </div>
            </Transition>

            <footer class="workspace-footer">
              <span><i class="footer-dot"></i> 数据仅来自已索引的 ZRDDS 文档</span>
              <span>Shift + Enter 换行</span>
            </footer>
          </div>
        </main>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import ChatInput from './components/ChatInput.vue'
import CitationsCard from './components/CitationsCard.vue'

const API_URL = '/query'

const answer = ref('')
const sources = ref([])
const errorMsg = ref('')
const isLoading = ref(false)
const isStreaming = ref(false)
const requestId = ref('')
const hasContent = computed(() => answer.value !== '' || sources.value.length > 0)
const knowledgeStatus = ref('checking')
const knowledgeMode = ref('')
const knowledgeStatusLabel = computed(() => {
  if (knowledgeStatus.value === 'online') {
    return knowledgeMode.value
      ? `服务在线 · ${knowledgeMode.value} 模式`
      : '服务在线'
  }
  if (knowledgeStatus.value === 'offline') return '服务离线'
  return '正在检查服务…'
})
const pipelineSteps = [
  { key: 'parse', number: '01', label: '问题解析' },
  { key: 'retrieve', number: '02', label: '检索召回' },
  { key: 'rerank', number: '03', label: '重排与引用' },
  { key: 'generate', number: '04', label: '生成答案' },
]
let abortController = null

onMounted(async () => {
  try {
    const response = await fetch('/healthz')
    if (!response.ok) throw new Error(`健康检查失败：${response.status}`)
    const health = await response.json()
    knowledgeStatus.value = health.status === 'ok' ? 'online' : 'offline'
    knowledgeMode.value = health.mode || ''
  } catch (error) {
    knowledgeStatus.value = 'offline'
    console.error('知识库服务健康检查失败:', error)
  }
})

function pipelineClass(step) {
  if (!isStreaming.value) return 'idle'
  if (step === 'parse') return 'done'
  if (step === 'retrieve') return sources.value.length ? 'done' : 'active'
  if (step === 'rerank') {
    if (!sources.value.length) return 'idle'
    return isLoading.value ? 'active' : 'done'
  }
  if (answer.value && !isLoading.value) return 'done'
  return sources.value.length ? 'active' : 'idle'
}

function pipelineStateLabel(step) {
  const state = pipelineClass(step)
  if (state === 'done') return '已完成'
  if (state === 'active') return '处理中…'
  return '等待中'
}

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
    requestId.value = payload.request_id || ''
  } else if (eventName === 'token') {
    answer.value += payload.text
  } else if (eventName === 'done') {
    answer.value = payload.answer
    sources.value = payload.sources || sources.value
    requestId.value = payload.request_id || requestId.value
  } else if (eventName === 'error') {
    errorMsg.value = payload.error
  }
}

const handleQuery = async (question) => {
  if (!question.trim()) return

  abortController?.abort()
  abortController = new AbortController()
  answer.value = ''
  sources.value = []
  errorMsg.value = ''
  requestId.value = ''
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
      const body = await response.json().catch(() => null)
      throw new Error(body?.error || `请求失败：${response.status} ${response.statusText}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
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
.app-shell {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px 24px;
  background:
    radial-gradient(circle at 12% 8%, rgba(111, 183, 192, 0.2), transparent 29%),
    radial-gradient(circle at 92% 88%, rgba(83, 137, 172, 0.13), transparent 32%),
    linear-gradient(135deg, #edf7f8 0%, #e8f1f6 53%, #e9eef4 100%);
}

.app-panel {
  width: min(1280px, 100%);
  overflow: hidden;
  border: 1px solid rgba(178, 207, 215, 0.72);
  border-radius: var(--radius-xl);
  background: var(--panel);
  box-shadow: var(--shadow-soft);
  backdrop-filter: blur(18px);
  transition: box-shadow 0.35s ease, border-color 0.35s ease;
}

.app-panel:focus-within {
  border-color: rgba(73, 144, 157, 0.58);
  box-shadow: 0 28px 70px rgba(31, 74, 97, 0.2);
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 22px 30px;
  border-bottom: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.66);
}

.brand-group,
.topbar-meta,
.status-pill,
.intro-signal,
.response-state,
.workspace-footer {
  display: inline-flex;
  align-items: center;
}

.brand-group {
  gap: 13px;
}

.brand-mark {
  position: relative;
  width: 43px;
  height: 43px;
  display: grid;
  place-items: center;
  overflow: hidden;
  border-radius: 14px;
  background: linear-gradient(145deg, var(--primary-500), var(--primary-700));
  color: #fff;
  font-weight: 800;
  box-shadow: 0 9px 20px rgba(57, 125, 145, 0.28);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.brand-mark span {
  position: relative;
  z-index: 1;
  font-size: 1.15rem;
}

.brand-mark i,
.empty-icon i {
  position: absolute;
  width: 25px;
  height: 25px;
  border: 1px solid rgba(255, 255, 255, 0.34);
  border-radius: 50%;
  transform: translate(9px, -10px);
}

.brand-mark:hover {
  transform: translateY(-2px) rotate(-3deg);
  box-shadow: 0 12px 24px rgba(57, 125, 145, 0.36);
}

.brand-name,
.brand-subtitle,
.eyebrow,
.workspace-intro h1,
.response-heading h2,
.rail-heading h2,
.panel-heading h3 {
  margin: 0;
}

.brand-name {
  font-size: 1.08rem;
  font-weight: 800;
  letter-spacing: 0.055em;
  color: var(--ink-deep);
}

.brand-subtitle {
  margin-top: 3px;
  color: var(--text-muted);
  font-size: 0.76rem;
}

.topbar-meta {
  gap: 13px;
}

.system-version {
  color: var(--text-subtle);
  font: 0.68rem/1.4 'Consolas', 'SFMono-Regular', monospace;
  letter-spacing: 0.08em;
}

.status-pill {
  gap: 7px;
  padding: 7px 11px;
  border: 1px solid rgba(78, 155, 136, 0.24);
  border-radius: 999px;
  background: rgba(78, 155, 136, 0.09);
  color: #397967;
  font-size: 0.72rem;
  font-weight: 700;
}

.status-dot,
.online-mark,
.footer-dot,
.state-dot {
  width: 7px;
  height: 7px;
  display: inline-block;
  flex: 0 0 auto;
  border-radius: 50%;
  background: var(--success);
  box-shadow: 0 0 0 4px rgba(78, 155, 136, 0.12);
}

.status-dot {
  animation: pulse 1.8s ease-in-out infinite;
}

.workspace-grid {
  display: grid;
  grid-template-columns: 255px minmax(0, 1fr);
  min-height: 720px;
}

.knowledge-rail {
  padding: 28px 20px 22px;
  border-right: 1px solid var(--line);
  background: linear-gradient(180deg, rgba(240, 248, 249, 0.82), rgba(236, 244, 248, 0.66));
}

.rail-heading,
.panel-heading,
.stat-heading,
.response-heading,
.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.eyebrow {
  color: var(--primary-600);
  font-size: 0.62rem;
  font-weight: 800;
  letter-spacing: 0.14em;
}

.rail-heading h2 {
  margin-top: 5px;
  color: var(--ink-deep);
  font-size: 1.02rem;
  letter-spacing: 0.01em;
}

.online-mark {
  margin-top: 7px;
  width: 9px;
  height: 9px;
  box-shadow: 0 0 0 5px rgba(78, 155, 136, 0.1);
}

.stat-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 22px;
}

.stat-card,
.engine-card {
  position: relative;
  padding: 12px;
  border: 1px solid rgba(192, 216, 222, 0.8);
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.64);
  box-shadow: var(--shadow-inset);
}

.stat-card {
  min-height: 84px;
}

.stat-card-wide {
  grid-column: 1 / -1;
  min-height: 77px;
}

.stat-label,
.engine-card small,
.stat-card small {
  display: block;
  color: var(--text-subtle);
  font-size: 0.68rem;
  line-height: 1.4;
}

.stat-card strong {
  display: block;
  margin: 7px 0 2px;
  color: var(--ink-deep);
  font-size: 1.08rem;
  letter-spacing: -0.02em;
}

.stat-card small {
  color: var(--primary-600);
  font-size: 0.62rem;
}

.stat-heading {
  align-items: center;
}

.stat-heading strong {
  margin: 0;
  color: var(--primary-700);
  font-size: 0.8rem;
}

.progress-track {
  height: 5px;
  margin: 10px 0 7px;
  overflow: hidden;
  border-radius: 99px;
  background: rgba(92, 145, 158, 0.13);
}

.progress-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--teal), var(--primary-500));
}

.rail-divider {
  height: 1px;
  margin: 22px 0;
  background: var(--line);
}

.pipeline-panel {
  padding: 0 2px;
}

.panel-heading {
  align-items: center;
}

.panel-heading h3 {
  margin-top: 4px;
  color: var(--ink-deep);
  font-size: 0.9rem;
}

.trace-id {
  color: var(--text-subtle);
  font: 0.62rem 'Consolas', monospace;
  letter-spacing: 0.08em;
}

.pipeline-list {
  position: relative;
  display: grid;
  gap: 0;
  margin: 17px 0 0;
  padding: 0;
  list-style: none;
}

.pipeline-list li {
  position: relative;
  display: flex;
  align-items: flex-start;
  min-height: 56px;
  gap: 10px;
  color: var(--text-subtle);
  transition: color 0.3s ease;
}

.pipeline-node {
  position: relative;
  z-index: 1;
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  border: 1px solid var(--line-strong);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.74);
  color: var(--text-subtle);
  font: 0.62rem 'Consolas', monospace;
  transition: background 0.3s ease, color 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease;
}

.pipeline-copy {
  display: grid;
  gap: 2px;
  padding-top: 1px;
}

.pipeline-copy strong {
  color: inherit;
  font-size: 0.73rem;
  font-weight: 700;
}

.pipeline-copy small {
  color: var(--text-subtle);
  font-size: 0.62rem;
}

.pipeline-connector {
  position: absolute;
  top: 24px;
  left: 11px;
  width: 1px;
  height: 33px;
  background: var(--line-strong);
}

.pipeline-list li.done,
.pipeline-list li.active {
  color: var(--primary-700);
}

.pipeline-list li.done .pipeline-node {
  border-color: rgba(78, 155, 136, 0.35);
  background: rgba(78, 155, 136, 0.13);
  color: var(--success);
}

.pipeline-list li.active .pipeline-node {
  border-color: rgba(57, 125, 145, 0.42);
  background: rgba(94, 156, 173, 0.15);
  color: var(--primary-700);
  box-shadow: 0 0 0 4px rgba(94, 156, 173, 0.1);
  animation: active-ring 1.7s ease-in-out infinite;
}

.engine-card {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-top: 11px;
  padding: 11px;
}

.engine-icon {
  width: 29px;
  height: 29px;
  display: grid;
  place-items: center;
  border-radius: 9px;
  background: rgba(94, 156, 173, 0.13);
  color: var(--primary-700);
  font-size: 1.3rem;
}

.engine-card strong {
  display: block;
  margin: 3px 0 1px;
  color: var(--primary-700);
  font: 0.68rem 'Consolas', monospace;
}

.engine-card small {
  font-size: 0.6rem;
}

.engine-status {
  align-self: flex-start;
  margin-left: auto;
  color: var(--success);
  font-size: 0.6rem;
  font-weight: 700;
}

.chat-workspace {
  min-width: 0;
  padding: 36px 42px 22px;
}

.conversation-column {
  width: min(840px, 100%);
  margin: 0 auto;
}

.workspace-intro {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 25px;
}

.workspace-intro h1 {
  max-width: 620px;
  margin-top: 8px;
  color: var(--ink-deep);
  font-size: clamp(1.55rem, 2.4vw, 2.1rem);
  font-weight: 800;
  letter-spacing: -0.035em;
  line-height: 1.18;
}

.intro-copy {
  max-width: 570px;
  margin: 11px 0 0;
  color: var(--text-muted);
  font-size: 0.84rem;
  line-height: 1.7;
}

.intro-signal {
  flex: 0 0 auto;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.6);
  color: var(--text-muted);
  font-size: 0.66rem;
  white-space: nowrap;
}

.signal-ring {
  width: 7px;
  height: 7px;
  border: 2px solid var(--primary-500);
  border-radius: 50%;
  box-shadow: 0 0 0 3px rgba(94, 156, 173, 0.13);
}

.response-section {
  display: flex;
  flex-direction: column;
  gap: 15px;
  min-height: 180px;
  padding: 18px;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: rgba(242, 248, 250, 0.73);
  box-shadow: var(--shadow-inset);
}

.response-heading {
  align-items: center;
  padding: 1px 2px 2px;
}

.response-heading h2 {
  margin-top: 4px;
  color: var(--ink-deep);
  font-size: 1rem;
}

.response-state {
  gap: 7px;
  color: var(--success);
  font-size: 0.68rem;
  font-weight: 700;
}

.response-state.is-loading {
  color: var(--primary-700);
}

.response-state.is-loading .state-dot {
  background: var(--primary-500);
  box-shadow: 0 0 0 4px rgba(94, 156, 173, 0.12);
  animation: pulse 1.2s ease-in-out infinite;
}

.section-fade-enter-active,
.section-fade-leave-active,
.answer-fade-enter-active,
.answer-fade-leave-active {
  transition: opacity 0.32s ease, transform 0.32s ease;
}

.section-fade-enter-from,
.section-fade-leave-to,
.answer-fade-enter-from,
.answer-fade-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

.answer-skeleton {
  padding: 18px 20px;
  border: 1px solid rgba(108, 162, 202, 0.2);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.74);
  box-shadow: var(--shadow-card);
}

.skeleton-shimmer {
  background: linear-gradient(90deg, rgba(194, 220, 229, 0.48), rgba(239, 248, 250, 0.98), rgba(194, 220, 229, 0.48));
  background-size: 220% 100%;
  animation: shimmer 1.55s ease-in-out infinite;
}

.skeleton-heading,
.skeleton-line {
  display: block;
  width: 34%;
  height: 12px;
  margin-bottom: 14px;
  border-radius: 999px;
}

.skeleton-heading {
  width: 82px;
  height: 24px;
  margin-bottom: 22px;
}

.skeleton-line-wide { width: 92%; }
.skeleton-line-short { width: 62%; }

.skeleton-status {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  margin-top: 7px;
  color: var(--primary-700);
  font-size: 0.82rem;
}

.loading-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--primary-500), var(--primary-700));
  animation: pulse 1.2s ease-in-out infinite;
}

.answer-card {
  padding: 18px 20px;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.84);
  box-shadow: var(--shadow-card);
  transition: box-shadow 0.3s ease, border-color 0.3s ease, background 0.3s ease;
}

.answer-card:hover {
  border-color: rgba(94, 156, 173, 0.4);
  box-shadow: var(--shadow-float);
}

.section-header {
  align-items: center;
  margin-bottom: 13px;
}

.section-badge {
  display: inline-flex;
  padding: 6px 9px;
  border: 1px solid rgba(94, 156, 173, 0.2);
  border-radius: 999px;
  background: rgba(94, 156, 173, 0.11);
  color: var(--primary-700);
  font-size: 0.62rem;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.answer-meta {
  color: var(--text-subtle);
  font-size: 0.65rem;
}

.streaming-response {
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
  color: var(--text);
  font-size: 0.92rem;
  line-height: 1.78;
}

.error-box {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px 18px;
  border: 1px solid rgba(166, 126, 126, 0.28);
  border-radius: var(--radius-md);
  background: rgba(255, 245, 247, 0.8);
  color: #69525a;
  box-shadow: 0 6px 16px rgba(135, 98, 104, 0.08);
}

.error-label {
  display: inline-flex;
  width: fit-content;
  padding: 5px 8px;
  border-radius: 999px;
  background: rgba(166, 126, 126, 0.12);
  font-size: 0.68rem;
  font-weight: 700;
}

.error-box p {
  margin: 0;
  line-height: 1.6;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 315px;
}

.empty-card {
  width: min(570px, 100%);
  padding: 37px 30px 31px;
  text-align: center;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.74), rgba(236, 246, 248, 0.82));
  box-shadow: var(--shadow-card);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.empty-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-float);
}

.empty-icon {
  position: relative;
  width: 54px;
  height: 54px;
  display: grid;
  place-items: center;
  overflow: hidden;
  margin: 0 auto 17px;
  border: 1px solid rgba(94, 156, 173, 0.2);
  border-radius: 17px;
  background: rgba(94, 156, 173, 0.12);
  color: var(--primary-700);
  font-size: 1.4rem;
  transition: transform 0.35s ease, background 0.35s ease;
}

.empty-icon span {
  position: relative;
  z-index: 1;
}

.empty-icon i {
  width: 38px;
  height: 38px;
  border-color: rgba(94, 156, 173, 0.27);
  transform: translate(10px, -9px);
}

.empty-card:hover .empty-icon {
  transform: rotate(8deg) scale(1.05);
  background: rgba(94, 156, 173, 0.19);
}

.empty-card h2 {
  margin: 8px 0 9px;
  color: var(--ink-deep);
  font-size: 1.3rem;
}

.empty-card > p:not(.eyebrow) {
  max-width: 430px;
  margin: 0 auto;
  color: var(--text-muted);
  line-height: 1.7;
  font-size: 0.82rem;
}

.empty-capabilities {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 7px;
  margin-top: 20px;
}

.empty-capabilities span {
  padding: 6px 9px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.62);
  color: var(--primary-700);
  font-size: 0.63rem;
  font-weight: 700;
}

.workspace-footer {
  justify-content: space-between;
  gap: 12px;
  margin-top: 18px;
  color: var(--text-subtle);
  font-size: 0.62rem;
}

.footer-dot {
  width: 5px;
  height: 5px;
  margin-right: 5px;
  box-shadow: none;
  background: var(--primary-500);
}

@keyframes shimmer {
  from { background-position: 100% 0; }
  to { background-position: -100% 0; }
}

@keyframes pulse {
  0%, 100% { opacity: 0.48; transform: scale(0.94); }
  50% { opacity: 1; transform: scale(1.08); }
}

@keyframes active-ring {
  0%, 100% { box-shadow: 0 0 0 3px rgba(94, 156, 173, 0.08); }
  50% { box-shadow: 0 0 0 6px rgba(94, 156, 173, 0.16); }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}

@media (max-width: 900px) {
  .workspace-grid {
    grid-template-columns: 1fr;
  }

  .knowledge-rail {
    display: grid;
    grid-template-columns: 1fr 1.2fr;
    gap: 18px 24px;
    padding: 20px 24px;
    border-right: 0;
    border-bottom: 1px solid var(--line);
  }

  .stat-grid {
    grid-column: 1 / -1;
    grid-row: 2;
    margin-top: 0;
  }

  .rail-divider {
    display: none;
  }

  .pipeline-panel {
    grid-column: 2;
    grid-row: 1;
  }

  .pipeline-list {
    display: flex;
    justify-content: space-between;
    gap: 7px;
    margin-top: 12px;
  }

  .pipeline-list li {
    min-height: 0;
    flex: 1;
  }

  .pipeline-connector {
    top: 12px;
    left: 29px;
    width: calc(100% - 23px);
    height: 1px;
  }

  .pipeline-copy {
    display: none;
  }

  .engine-card {
    display: none;
  }
}

@media (max-width: 640px) {
  .app-shell {
    padding: 12px 8px;
  }

  .app-panel {
    border-radius: 22px;
  }

  .topbar {
    align-items: flex-start;
    padding: 17px 17px;
  }

  .brand-subtitle,
  .system-version {
    display: none;
  }

  .topbar-meta {
    padding-top: 4px;
  }

  .knowledge-rail {
    display: block;
    padding: 18px 17px 15px;
  }

  .stat-grid {
    margin-top: 16px;
  }

  .stat-card {
    min-height: 77px;
  }

  .pipeline-panel {
    margin-top: 17px;
  }

  .pipeline-list {
    gap: 4px;
  }

  .pipeline-node {
    width: 23px;
    height: 23px;
    margin: 0 auto;
  }

  .pipeline-connector {
    left: calc(50% + 11px);
    width: calc(100% - 25px);
  }

  .chat-workspace {
    padding: 26px 16px 19px;
  }

  .workspace-intro {
    display: block;
    margin-bottom: 20px;
  }

  .workspace-intro h1 {
    font-size: 1.6rem;
  }

  .intro-signal {
    margin-top: 14px;
  }

  .response-section {
    padding: 13px;
  }

  .answer-meta {
    display: none;
  }

  .workspace-footer {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
