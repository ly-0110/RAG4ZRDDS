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
          <span>平均相关度</span>
          <strong>{{ averageScore }}%</strong>
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

    <TransitionGroup name="source-list" tag="div" class="sources-list">
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

          <div class="relevance-row">
            <div class="relevance-label">
              <span>向量相关度</span>
              <strong>{{ displayScore(s) }}</strong>
            </div>
            <span class="relevance-tag">{{ relationLabel(s) }}</span>
          </div>
          <div class="relevance-track" :aria-label="`相关度 ${displayScore(s)}`">
            <span :style="{ width: scorePercent(s) }"></span>
          </div>

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

          <Transition name="details-expand">
            <div v-if="isExpanded(s, i)" class="details-panel">
              <div v-if="isLoading(s, i)" class="details-skeleton" aria-label="正在加载来源详情">
                <span class="skeleton-line skeleton-line-wide"></span>
                <span class="skeleton-line"></span>
                <span class="skeleton-line skeleton-line-short"></span>
              </div>
              <p v-else-if="detailErrors[sourceKey(s, i)]" class="details-error">
                暂时无法加载详情，请稍后重试。
              </p>
              <pre v-else class="details-content">{{ formatDetails(detailsCache[sourceKey(s, i)]) }}</pre>
            </div>
          </Transition>
        </div>
      </article>
    </TransitionGroup>
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
})

const detailsCache = ref({})
const detailErrors = ref({})
const loadingDetails = ref({})
const expandedDetails = ref(new Set())

const canFetchDetails = computed(() => props.requestId && props.requestId.length > 0)
const normalizedScore = (source) => {
  const rawScore = Number(source?.score)
  if (!Number.isFinite(rawScore)) return 0
  return Math.max(0, Math.min(1, rawScore > 1 ? rawScore / 100 : rawScore))
}
const scorePercent = (source) => `${Math.max(8, normalizedScore(source) * 100)}%`
const displayScore = (source) => `${(normalizedScore(source) * 100).toFixed(1)}%`
const averageScore = computed(() => {
  const total = props.sources.reduce((sum, source) => sum + normalizedScore(source), 0)
  return props.sources.length ? (total / props.sources.length * 100).toFixed(1) : '0.0'
})
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
  const score = normalizedScore(source)
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
  loadingDetails.value = {}
  expandedDetails.value = new Set()
})

const sourceKey = (source, index) => source?.node_id || `${source?.source_name || 'source'}-${source?.section || 'section'}-${index}`
const isExpanded = (source, index) => expandedDetails.value.has(sourceKey(source, index))
const isLoading = (source, index) => Boolean(loadingDetails.value[sourceKey(source, index)])

const setRecord = (record, key, value) => {
  record.value = { ...record.value, [key]: value }
}

const fetchAndShowDetails = async (source, index) => {
  if (!canFetchDetails.value) return

  const key = sourceKey(source, index)
  if (isLoading(source, index)) return

  if (Object.prototype.hasOwnProperty.call(detailsCache.value, key)) {
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
    const response = await fetch(`/sources/${props.requestId}`)
    if (!response.ok) {
      throw new Error(`获取详情失败：${response.status} ${response.statusText}`)
    }

    const data = await response.json()
    setRecord(detailsCache, key, data)
  } catch (error) {
    setRecord(detailErrors, key, error.message || '获取详情失败')
    console.error('获取详情出错:', error)
  } finally {
    setRecord(loadingDetails, key, false)
  }
}

const formatDetails = (details) => {
  if (typeof details === 'string') return details
  return JSON.stringify(details, null, 2)
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

.relevance-row {
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

.relevance-track {
  height: 4px;
  margin-top: 6px;
  overflow: hidden;
  border-radius: 99px;
  background: rgba(94, 156, 173, 0.12);
}

.relevance-track span {
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
