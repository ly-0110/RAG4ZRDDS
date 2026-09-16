<template>
  <div v-if="sources.length" class="sources-block">
    <div class="sources-header">
      <div>
        <p class="eyebrow">EVIDENCE GRAPH</p>
        <h3 class="sources-title">来源与知识关联</h3>
        <p class="sources-subtitle">已从 {{ uniqueDocuments }} 份文档中筛选 {{ sources.length }} 个证据节点</p>
      </div>
      <span class="sources-count" :aria-label="`${sources.length} 个来源`">{{ sources.length }}</span>
    </div>

    <div class="evidence-summary">
      <div class="evidence-stat">
        <span class="summary-icon">◎</span>
        <div>
          <span>{{ scoreLabel }}<template v-if="!scoreComparable">（池内相对）</template></span>
          <strong>{{ averageScoreText }}</strong>
        </div>
      </div>
      <div class="evidence-stat">
        <span class="summary-icon">◇</span>
        <div>
          <span>图谱关联 · 后端未提供</span>
          <strong>{{ graphLinksTotal ? `${graphLinksTotal} 条` : '暂无数据' }}</strong>
        </div>
      </div>
      <div class="evidence-stat request-stat">
        <span class="summary-icon">#</span>
        <div>
          <span>请求标识（非批次计数）</span>
          <strong>{{ requestId ? requestId.slice(-8) : '暂无数据' }}</strong>
        </div>
      </div>
    </div>

    <!-- 2026-09-16（D 代修）：原为 <TransitionGroup name="source-list">，其 enter-from
         是 opacity:0，而 Vue 靠 requestAnimationFrame 移除该类；rAF 在未被合成的
         标签页不触发时来源卡会永久不可见。改普通容器，CSS 保留。 -->
    <div class="sources-list">
      <article
        v-for="(s, i) in sources"
        :key="sourceKey(s, i)"
        class="source-card"
        :class="{ 'is-expanded': isExpanded(s, i) }"
      >
        <div class="source-index">{{ String(i + 1).padStart(2, '0') }}</div>

        <div class="source-body">

          <div class="source-card-heading">
            <div class="source-title">{{ s.source_name || '未命名文档' }} · {{ s.section || '相关片段' }}</div>
            <span class="source-kind">{{ sourceKind(s) }}</span>
          </div>

          <div class="source-meta">
            <span class="page-info">第 <span class="page-print">{{ s.page_print || '—' }}</span> 页</span>
            <span class="meta-divider">·</span>
            <span>物理页 {{ s.page_physical || '—' }}</span>
            <span class="meta-divider">·</span>
            <span>{{ graphLinkLabel(s) }}</span>
            <span v-if="s.source_id" class="source-id">· {{ s.source_id }}</span>
          </div>

          <a
            v-if="s.source_url"
            class="source-link"
            :href="s.source_url"
            target="_blank"
            rel="noopener noreferrer"
          >
            打开 HTML 原文 <span aria-hidden="true">↗</span>
          </a>

          <div class="relevance-container">
            <div class="relevance-label">
              <span class="label-text">{{ scoreLabel }}</span>
              <strong class="score-value">{{ scoreValueText(s) }}</strong>
            </div>
            <div
              class="relevance-progress-wrapper"
              role="progressbar"
              :aria-valuenow="Math.round(scoreFraction(s) * 100)"
              aria-valuemin="0"
              aria-valuemax="100"
              :aria-label="`${scoreLabel} ${scoreValueText(s)}`"
            >
              <span class="progress-bar" :style="{ width: scoreBarWidth(s) }"></span>
            </div>
            <span class="relevance-tag">{{ scoreComparable ? relationLabel(s) : rankLabel(i) }}</span>
          </div>

          <p v-if="!scoreComparable" class="score-caveat">
            {{ scoreCaveat }}
          </p>

          <div class="action-area">
            <button
              v-if="requestId && canFetchDetails"
              class="view-details-btn"
              type="button"
              :disabled="isLoading(s, i)"
              :aria-expanded="isExpanded(s, i)"
              @click="fetchAndShowDetails(s, i)"
            >
              <span>{{ isExpanded(s, i) ? '收起详情' : '查看节点详情' }}</span>
              <span class="detail-chevron" :class="{ 'is-open': isExpanded(s, i) }" aria-hidden="true">⌄</span>
              <span v-if="isLoading(s, i)" class="inline-spinner" aria-hidden="true"></span>
            </button>
            <span v-else class="no-details-tip">节点详情未开放</span>
          </div>

          <!-- 同理去过渡：节点原文必须无条件可见（rAF 停摆时 enter-from 的
               max-height:0/opacity:0 会让展开的面板永远看不见） -->
          <div v-if="isExpanded(s, i)" class="details-panel">
              <div v-if="isLoading(s, i)" class="details-skeleton" aria-label="正在加载来源详情">
                <span class="skeleton-line skeleton-line-wide"></span>
                <span class="skeleton-line"></span>
                <span class="skeleton-line skeleton-line-short"></span>
              </div>
              <p v-else-if="detailErrorOf(s, i)" class="details-error">
                {{ detailErrorOf(s, i) }}
              </p>
              <p v-else-if="detailNoteOf(s, i)" class="details-note">
                {{ detailNoteOf(s, i) }}
              </p>
              <div v-else-if="detailOf(s, i)" class="details-node">
                <div class="details-meta">
                  <span class="details-chip">{{ detailOf(s, i).source_id || '未知来源' }}</span>
                  <span v-if="detailOf(s, i).version" class="details-chip">v{{ detailOf(s, i).version }}</span>
                  <span class="details-chip is-format">{{ formatLabel(detailOf(s, i)) }}</span>
                  <!-- 页码只对 PDF 有意义（HTML 无页面概念，产物里页字段为 None） -->
                  <span v-if="pageRangeText(detailOf(s, i))" class="details-pages">
                    {{ pageRangeText(detailOf(s, i)) }}
                  </span>
                </div>
                <p v-if="detailOf(s, i).title" class="details-title">{{ detailOf(s, i).title }}</p>
                <p v-if="sectionPathText(detailOf(s, i).section_path)" class="details-section">
                  {{ sectionPathText(detailOf(s, i).section_path) }}
                </p>
                <p class="details-text">{{ detailOf(s, i).text || '（该节点无正文）' }}</p>
                <a
                  v-if="detailOf(s, i).source_url"
                  class="source-link"
                  :href="detailOf(s, i).source_url"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {{ detailOf(s, i).source_type === 'html' ? '打开该节点 HTML 原文' : '打开来源文件' }}
                  <span aria-hidden="true">↗</span>
                </a>
              </div>
            </div>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  sources: {
    type: Array,
    required: true,
    default: () => [],
  },
  requestId: {
    type: String,
    default: '',
  },
  health: {
    type: Object,
    default: null,
  },
  // 当前检索模式（/healthz 的 experiment_modes）：决定分数怎么显示。
  // vector/hybrid_rerank 的分数量纲可跨查询比较；bm25 是原始词面分（7~56）、
  // hybrid 是 RRF（~0.03）——把它们当"相关度百分比"渲染会系统性误导（api.md v0.16）。
  scoreMode: {
    type: String,
    default: 'vector',
  },
})

const scoreComparable = computed(() => ['vector', 'hybrid_rerank'].includes(props.scoreMode))
const scoreLabel = computed(() => ({
  vector: '向量相关度',
  hybrid_rerank: '精排相关度',
  bm25: 'BM25 词面分',
  hybrid: 'RRF 融合分',
}[props.scoreMode] || '检索得分'))
const scoreCaveat = computed(() => (props.scoreMode === 'bm25'
  ? 'BM25 为词面统计分（无上界），跨查询不可比；进度与"池内最强"为本批引用内的相对值。'
  : 'RRF 只有排序意义、分值与相关性不成比例；进度与"池内最强"为本批引用内的相对值。'))

const detailsCache = ref({})
const detailErrors = ref({})
const detailNotes = ref({})
const loadingDetails = ref({})
const expandedDetails = ref(new Set())

const canFetchDetails = computed(() => props.requestId && props.requestId.length > 0)

// ---- 分数展示（按模式分两路）---------------------------------------------
// 可比模式（vector cosine / hybrid_rerank sigmoid）：直接当百分比。
// 不可比模式（bm25 原始分 / hybrid RRF）：只在“本批引用内”做 min-max 归一，
// 作为相对强弱与排序提示，同时把原始分原样显示出来，不伪造百分比。
const rawScore = (source) => {
  const value = Number(source?.score)
  return Number.isFinite(value) ? value : 0
}
const comparableFraction = (source) => Math.max(0, Math.min(1, rawScore(source)))
const scoreBounds = computed(() => {
  const values = props.sources.map(rawScore)
  if (!values.length) return { min: 0, max: 0 }
  return { min: Math.min(...values), max: Math.max(...values) }
})
const relativeFraction = (source) => {
  const { min, max } = scoreBounds.value
  if (max <= min) return 1
  return Math.max(0, Math.min(1, (rawScore(source) - min) / (max - min)))
}
const scoreFraction = (source) => (scoreComparable.value ? comparableFraction(source) : relativeFraction(source))
const scoreBarWidth = (source) => `${Math.max(6, scoreFraction(source) * 100)}%`
const scoreValueText = (source) => (scoreComparable.value
  ? `${(comparableFraction(source) * 100).toFixed(1)}%`
  : rawScore(source).toFixed(3))
const averageScoreText = computed(() => {
  if (!props.sources.length) return '0.0%'
  if (!scoreComparable.value) {
    const total = props.sources.reduce((sum, source) => sum + rawScore(source), 0)
    return `${(total / props.sources.length).toFixed(3)}（原始分均值）`
  }
  const total = props.sources.reduce((sum, source) => sum + comparableFraction(source), 0)
  return `${(total / props.sources.length * 100).toFixed(1)}%`
})
const rankLabel = (index) => `第 ${index + 1} 位`
const uniqueDocuments = computed(() => new Set(props.sources.map((source) => source.source_name || '未命名文档')).size)
const graphLinksTotal = computed(() =>
  props.sources.reduce((sum, source) => sum + graphLinkCount(source), 0),
)

const graphLinkCount = (source) => {
  const links = source?.graph_links ?? source?.related_nodes ?? source?.relation_count
  if (Array.isArray(links)) return links.length
  const parsed = Number(links)
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0
}

const graphLinkLabel = (source) => {
  const links = source?.graph_links ?? source?.related_nodes ?? source?.relation_count
  if (Array.isArray(links)) return `${links.length} 个相邻节点`
  const parsed = Number(links)
  return Number.isFinite(parsed) && parsed >= 0
    ? `${parsed} 个相邻节点`
    : '图谱数据暂无（占位区域）'
}

const relationLabel = (source) => {
  const score = comparableFraction(source)
  if (score >= 0.78) return '强关联'
  if (score >= 0.55) return '中关联'
  return '弱关联'
}

const sourceKind = (source) => {
  if (source?.source_type) return String(source.source_type).toUpperCase()
  const name = String(source?.source_name || '')
  const extension = name.includes('.') ? name.split('.').pop() : ''
  return extension ? extension.toUpperCase() : 'DOC'
}

watch(() => props.requestId, () => {
  detailsCache.value = {}
  detailErrors.value = {}
  detailNotes.value = {}
  loadingDetails.value = {}
  expandedDetails.value = new Set()
})

const sourceKey = (source, index) => source?.node_id || `${source?.source_name || 'source'}-${source?.section || 'section'}-${index}`
const isExpanded = (source, index) => expandedDetails.value.has(sourceKey(source, index))
const isLoading = (source, index) => Boolean(loadingDetails.value[sourceKey(source, index)])
const detailOf = (source, index) => detailsCache.value[sourceKey(source, index)] || null
const detailErrorOf = (source, index) => detailErrors.value[sourceKey(source, index)] || ''
const detailNoteOf = (source, index) => detailNotes.value[sourceKey(source, index)] || ''
const sectionPathText = (path) => (Array.isArray(path) ? path.join(' › ') : path || '')

// 按来源格式渲染详情（item 4）：PDF 有印刷/物理页（可能跨页，显示区间），
// HTML 摘自 Doxygen 站点、无页面概念（产物页字段为 "None" → 归一为 null，
// 故不显示页码），改为展示文件与标题。
const formatLabel = (node) => {
  const type = String(node?.source_type || '').toLowerCase()
  if (type === 'html') return 'HTML 文档'
  if (type === 'pdf') return 'PDF 手册'
  return type ? type.toUpperCase() : '文档'
}
const pageRangeText = (node) => {
  const printStart = node?.page_print
  const physStart = node?.page_physical
  if (printStart == null && physStart == null) return ''
  const range = (start, end) => (end && end !== start ? `${start}–${end}` : `${start}`)
  const parts = []
  if (printStart != null) parts.push(`印刷页 ${range(printStart, node.page_print_end)}`)
  if (physStart != null) parts.push(`物理页 ${range(physStart, node.page_physical_end)}`)
  return parts.join(' · ')
}

const setRecord = (record, key, value) => {
  record.value = { ...record.value, [key]: value }
}

const fetchAndShowDetails = async (source, index) => {
  if (!canFetchDetails.value) return

  const key = sourceKey(source, index)
  if (isLoading(source, index)) return

  if (Object.prototype.hasOwnProperty.call(detailsCache.value, key)
    || detailNotes.value[key]) {
    const nextExpanded = new Set(expandedDetails.value)
    if (nextExpanded.has(key)) nextExpanded.delete(key)
    else nextExpanded.add(key)
    expandedDetails.value = nextExpanded
    return
  }

  setRecord(loadingDetails, key, true)
  setRecord(detailErrors, key, '')
  expandedDetails.value = new Set([...expandedDetails.value, key])

  try {
    // F3（api.md v0.14）：单节点原文走 GET /nodes/{node_id}。mock 模式后端无
    // Node 产物（/healthz 的 kb 为 null），给出可读说明而非请求注定 404。
    const isMock = props.health == null || props.health.kb == null
    if (isMock) {
      setRecord(detailNotes, key, '当前为 mock 模式，节点原文需 live 模式（RAG_MODE=live）下查询。')
    } else if (!source?.node_id) {
      setRecord(detailNotes, key, '该引用未携带 node_id，无法定位原文。')
    } else {
      const response = await fetch(`/nodes/${encodeURIComponent(source.node_id)}`)
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        throw new Error(body?.detail || `获取节点详情失败：${response.status}`)
      }
      setRecord(detailsCache, key, await response.json())
    }
  } catch (error) {
    setRecord(detailErrors, key, error.message || '获取节点详情失败')
    console.error('获取节点详情出错:', error)
  } finally {
    setRecord(loadingDetails, key, false)
  }
}
</script>

<style scoped>
.sources-block {
  display: flex;
  flex-direction: column;
  gap: 11px;
}

.sources-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 1px 2px 0;
}

.sources-title {
  margin: 5px 0 0;
  color: var(--ink-deep);
  font-size: 0.93rem;
}

.sources-subtitle {
  margin: 4px 0 0;
  color: var(--text-subtle);
  font-size: 0.66rem;
}

.sources-count {
  min-width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(94, 156, 173, 0.25);
  border-radius: 10px;
  background: rgba(94, 156, 173, 0.13);
  color: var(--primary-700);
  font: 0.75rem 'Consolas', monospace;
  font-weight: 700;
}

.evidence-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 7px;
}

.evidence-stat {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  padding: 9px 10px;
  border: 1px solid rgba(192, 216, 222, 0.82);
  border-radius: 11px;
  background: rgba(255, 255, 255, 0.62);
  box-shadow: var(--shadow-inset);
}

.summary-icon {
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  border-radius: 8px;
  background: rgba(94, 156, 173, 0.12);
  color: var(--primary-600);
  font-size: 0.9rem;
}

.evidence-stat span:not(.summary-icon) {
  display: block;
  overflow: hidden;
  color: var(--text-subtle);
  font-size: 0.6rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.evidence-stat strong {
  display: block;
  margin-top: 2px;
  overflow: hidden;
  color: var(--primary-700);
  font: 0.76rem 'Consolas', monospace;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sources-list {
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.source-card {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  padding: 13px 14px;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.77);
  box-shadow: var(--shadow-card);
  transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease, background 0.25s ease;
}

.source-card:hover,
.source-card.is-expanded {
  border-color: rgba(94, 156, 173, 0.42);
  background: rgba(255, 255, 255, 0.95);
  box-shadow: var(--shadow-float);
  transform: translateY(-1px);
}

.source-card.is-expanded {
  transform: none;
}

.source-list-enter-active,
.source-list-leave-active {
  transition: opacity 0.28s ease, transform 0.28s ease;
}

.source-list-enter-from,
.source-list-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

.source-index {
  width: 31px;
  height: 31px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  border-radius: 10px;
  background: rgba(94, 156, 173, 0.11);
  color: var(--primary-700);
  font: 0.67rem 'Consolas', monospace;
  font-weight: 700;
}

.source-body {
  min-width: 0;
  flex: 1;
}

.source-card-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.source-title {
  min-width: 0;
  color: var(--primary-900);
  font-size: 0.84rem;
  font-weight: 800;
  line-height: 1.45;
}

.source-kind {
  padding: 4px 6px;
  flex: 0 0 auto;
  border: 1px solid rgba(94, 156, 173, 0.2);
  border-radius: 6px;
  background: rgba(94, 156, 173, 0.08);
  color: var(--primary-600);
  font: 0.57rem 'Consolas', monospace;
  font-weight: 700;
}

.source-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 5px;
  margin-top: 7px;
  color: var(--text-muted);
  font-size: 0.65rem;
  line-height: 1.5;
}

.source-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  color: var(--primary-700);
  font-size: 0.65rem;
  font-weight: 700;
  text-decoration: none;
}

.source-link:hover {
  color: var(--teal);
  text-decoration: underline;
}

.meta-divider {
  color: rgba(76, 91, 110, 0.35);
}

.page-info {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-weight: 600;
}

.page-print {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  padding: 2px 5px;
  border: 1px solid rgba(94, 156, 173, 0.18);
  border-radius: 6px;
  background: rgba(94, 156, 173, 0.09);
  color: var(--primary-700);
  font: 0.64rem 'Consolas', monospace;
}

.source-id {
  color: rgba(76, 91, 110, 0.72);
  font: 0.62rem 'Consolas', monospace;
}

.relevance-container {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 11px;
}

.relevance-label {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-subtle);
  font-size: 0.62rem;
}

.relevance-label strong {
  color: var(--primary-700);
  font: 0.66rem 'Consolas', monospace;
}

.relevance-tag {
  padding: 3px 6px;
  border-radius: 999px;
  background: rgba(78, 155, 136, 0.1);
  color: #397967;
  font-size: 0.59rem;
  font-weight: 700;
}

/* 不可比量纲（bm25/hybrid）的说明行：避免把原始分误读成"相关度很低" */
.score-caveat {
  margin: 6px 0 0;
  color: var(--text-subtle);
  font-size: 0.6rem;
  line-height: 1.5;
}

/* 相关度进度条：标签行（左）+ 进度条（中）+ 关联标签（右） */
.relevance-progress-wrapper {
  flex: 1;
  min-width: 72px;
  height: 5px;
  overflow: hidden;
  border-radius: 99px;
  background: rgba(94, 156, 173, 0.14);
}

.progress-bar {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--primary-300), var(--teal));
  transition: width 0.55s ease;
}

.action-area {
  display: flex;
  align-items: center;
  margin-top: 10px;
}

.view-details-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 6px 9px;
  border: 1px solid rgba(89, 142, 180, 0.34);
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(219, 237, 245, 0.75), rgba(207, 228, 242, 0.82));
  color: var(--primary-700);
  cursor: pointer;
  font-size: 0.64rem;
  font-weight: 700;
  transition: transform 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
}

.view-details-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 7px 15px rgba(76, 133, 180, 0.14);
}

.view-details-btn:active:not(:disabled) {
  transform: translateY(1px) scale(0.97);
}

.view-details-btn:focus-visible {
  outline: 3px solid rgba(106, 159, 199, 0.25);
  outline-offset: 2px;
}

.view-details-btn:disabled {
  cursor: wait;
  opacity: 0.76;
}

.detail-chevron {
  font-size: 0.9rem;
  line-height: 0.75;
  transition: transform 0.25s ease;
}

.detail-chevron.is-open {
  transform: rotate(180deg);
}

.inline-spinner {
  width: 11px;
  height: 11px;
  border: 2px solid rgba(57, 95, 137, 0.22);
  border-top-color: var(--primary-700);
  border-radius: 50%;
  animation: spin 0.75s linear infinite;
}

.no-details-tip {
  color: rgba(97, 112, 127, 0.75);
  font-size: 0.63rem;
  font-style: italic;
}

.details-panel {
  overflow: hidden;
  margin-top: 10px;
  padding: 11px 12px;
  border: 1px solid rgba(108, 162, 202, 0.2);
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(239, 248, 255, 0.82), rgba(231, 243, 251, 0.68));
}

.details-expand-enter-active,
.details-expand-leave-active {
  max-height: 360px;
  transition: max-height 0.32s ease, opacity 0.25s ease, transform 0.32s ease, margin-top 0.32s ease, padding 0.32s ease;
}

.details-expand-enter-from,
.details-expand-leave-to {
  max-height: 0;
  margin-top: 0;
  padding-top: 0;
  padding-bottom: 0;
  opacity: 0;
  transform: translateY(-5px);
}

.details-content {
  max-height: 300px;
  overflow: auto;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--text-muted);
  font: 0.72rem/1.6 'Consolas', monospace;
}

/* 节点详情（GET /nodes/{node_id}）：元信息行 + 章节路径 + 正文 */
.details-node {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.details-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.details-chip {
  padding: 2px 7px;
  border: 1px solid rgba(94, 156, 173, 0.2);
  border-radius: 999px;
  background: rgba(94, 156, 173, 0.1);
  color: var(--primary-700);
  font: 0.62rem 'Consolas', monospace;
}

.details-pages {
  color: var(--text-subtle);
  font: 0.62rem 'Consolas', monospace;
}

.details-section {
  margin: 0;
  color: var(--primary-700);
  font-size: 0.68rem;
  font-weight: 700;
}

.details-text {
  max-height: 300px;
  overflow: auto;
  margin: 0;
  padding: 9px 10px;
  border: 1px solid rgba(138, 175, 202, 0.26);
  border-radius: 9px;
  background: rgba(247, 251, 252, 0.72);
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--text-muted);
  font: 0.72rem/1.65 'Consolas', monospace;
}

.details-note {
  margin: 0;
  color: var(--text-subtle);
  font-size: 0.72rem;
}

.details-chip.is-format {
  border-color: rgba(120, 150, 190, 0.3);
  background: rgba(120, 150, 190, 0.12);
  color: #4a5f7a;
}

.details-title {
  margin: 0;
  color: var(--ink-deep);
  font-size: 0.72rem;
  font-weight: 700;
}

.details-error {
  margin: 0;
  color: #806875;
  font-size: 0.75rem;
}

.details-skeleton {
  display: grid;
  gap: 9px;
}

.skeleton-line {
  display: block;
  width: 76%;
  height: 9px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(194, 220, 235, 0.55), rgba(238, 247, 252, 0.95), rgba(194, 220, 235, 0.55));
  background-size: 220% 100%;
  animation: shimmer 1.5s ease-in-out infinite;
}

.skeleton-line-wide { width: 92%; }
.skeleton-line-short { width: 48%; }

@keyframes shimmer {
  from { background-position: 100% 0; }
  to { background-position: -100% 0; }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (prefers-reduced-motion: reduce) {
  .source-card,
  .view-details-btn,
  .detail-chevron,
  .details-expand-enter-active,
  .details-expand-leave-active,
  .source-list-enter-active,
  .source-list-leave-active {
    transition-duration: 0.01ms;
  }

  .inline-spinner,
  .skeleton-line {
    animation: none;
  }
}

@media (max-width: 600px) {
  .evidence-summary {
    grid-template-columns: 1fr 1fr;
  }

  .request-stat {
    grid-column: 1 / -1;
  }

  .source-card-heading {
    display: block;
  }

  .source-kind {
    display: inline-flex;
    margin-top: 6px;
  }
}
</style>
