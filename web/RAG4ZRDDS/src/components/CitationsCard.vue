<template>
  <div class="sources-block" v-if="sources.length">
    <h3 class="sources-title">来源引用（{{ sources.length }}）</h3>
    <div
      v-for="(s, i) in sources"
      :key="s.node_id"
      class="source-card"
    >
      <!-- 来源标题 -->
      <div class="source-title">
        [{{ i + 1 }}] {{ s.source_name }} · {{ s.section }}
      </div>
        
      <!-- 来源元数据 -->
      <div class="source-meta">
        <span class="page-info">
          第 
          <span class="page-print">{{ s.page_print }}</span> 页（物理页 {{ s.page_physical }}）
        </span>
        <span class="score-info">
          · 相关度 {{ Number(s.score).toFixed(3) }}
        </span>
        <span class="source-id" v-if="s.source_id">
          · {{ s.source_id }}
        </span>
      </div>
        
      <!-- 查看详情按钮 -->
      <div class="action-area">
        <button 
          v-if="requestId && canFetchDetails"
          class="view-details-btn"
          @click="fetchAndShowDetails(s)"
        >
          📄 查看详情
        </button>
        <span v-else class="no-details-tip">无详情数据</span>
      </div>
        
      <!-- 详情展示区域（每个卡片独立） -->
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
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  /** 来源引用列表 */
  sources: {
    type: Array,
    required: true,
    default: () => []
  },
  
  /** 请求 ID（用于回查详情） */
  requestId: {
    type: String,
    default: ''
  }
})

/** 是否可以获取详情 */
const canFetchDetails = computed(() => {
  return props.requestId && props.requestId.length > 0
})

/** 详情显示状态（每个来源独立） */
const showDetails = ref({})

/** 活跃的来源数据（每个来源独立） */
const activeSources = ref({})

/**
 * 隐藏指定来源的详情面板
 * @param {string} nodeId - 来源节点 ID
 */
const hideDetails = (nodeId) => {
  showDetails.value[nodeId] = false
  activeSources.value[nodeId] = null
}

/**
 * 获取并显示来源详情
 * @param {Object} source - 来源对象
 */
const fetchAndShowDetails = async (source) => {
  if (!canFetchDetails.value) return
  
  // 直接使用传入的 source 对象作为详情数据（因为 API 返回的是整个列表）
  activeSources.value[source.node_id] = { ...source }
  showDetails.value[source.node_id] = true
  
  // 滚动到详情区域
  const detailsPanel = document.querySelector('.details-panel[style*="opacity: 1"]')
  if (detailsPanel) {
    detailsPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }
}
</script>

<style scoped>
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
  transition: box-shadow 0.2s ease, transform 0.2s ease;
}

.source-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transform: translateY(-1px);
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
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 6px;
}

.page-info {
  font-weight: 500;
}

.page-print {
  background-color: #e8f4f8;
  padding: 2px 6px;
  border-radius: 4px;
  color: #1a5276;
  font-family: 'Consolas', 'Monaco', monospace;
}

.score-info {
  opacity: 0.8;
}

.source-id {
  opacity: 0.6;
  font-size: 11px;
}

.action-area {
  display: flex;
  align-items: center;
  gap: 4px;
}

.view-details-btn {
  background-color: #e8f4f8;
  border: 1px solid #b8d4e0;
  color: #1a5276;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  transition: background-color 0.2s ease, color 0.2s ease;
}

.view-details-btn:hover {
  background-color: #dbe7f3;
  color: #154360;
}

.no-details-tip {
  font-size: 11px;
  color: #999;
  font-style: italic;
}

/* 详情面板样式 */
.details-panel {
  background-color: #f8fbff;
  border: 1px solid #b8d4e0;
  border-radius: 6px;
  padding: 12px;
  margin-top: 8px;
  animation: fadeIn 0.3s ease;
}

.details-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.close-details-btn {
  background-color: #fff;
  border: 1px solid #ccc;
  color: #666;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.close-details-btn:hover {
  background-color: #f5f5f5;
  color: #333;
  border-color: #999;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-5px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.details-title {
  font-size: 13px;
  font-weight: 600;
  color: #1a5276;
  margin: 0 0 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid #dbe7f3;
}

.details-content {
  font-size: 12px;
  color: #444;
  line-height: 1.6;
}

.details-content p {
  margin: 4px 0;
}

.details-content-text {
  margin-top: 8px;
  padding: 8px;
  background-color: #f5f9fc;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>