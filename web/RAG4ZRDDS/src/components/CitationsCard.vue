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

const detailsCache = ref({})

/** 是否可以获取详情 */
const canFetchDetails = computed(() => {
  return props.requestId && props.requestId.length > 0
})

/**
 * 获取并显示来源详情
 * @param {Object} source - 来源对象
 */
const fetchAndShowDetails = async (source) => {
  if (!canFetchDetails.value) return
  
  try {
    const response = await fetch(`/sources/${props.requestId}`)
    
    if (!response.ok) {
      console.warn(`获取详情失败：${response.status} ${response.statusText}`)
      return
    }
    
    const data = await response.json()
    detailsCache.value[source.node_id || source.section] = data
    
    // 可以在这里添加显示详情的逻辑，例如弹窗或展开区域
    console.log('来源详情:', data)
    
  } catch (error) {
    console.error('获取详情出错:', error)
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
</style>