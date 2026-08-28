<template>
  <div class="chat-container">
    <!-- 输入框组件 -->
    <ChatInput />
    
    <!-- 流式回答展示区域（第二周创建 StreamingResponse.vue 后接入） -->
    <div v-if="isStreaming" class="response-section">
      <div class="loading-spinner" v-if="isLoading">
        <p>正在检索...</p>
      </div>
      
      <pre 
        v-else-if="hasAnswer" 
        class="streaming-response"
        :key="lastResponseKey"
      >
        {{ answer }}
      </pre>
    </div>

    <!-- 空状态提示 -->
    <div v-else-if="!hasAnswer" class="empty-state">
      <p>💡 提示：输入问题后按 Enter 或点击提问</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
// 导入 ChatInput 组件（第一周核心交付）<sup>[[1]](product_rag_implementation_guide.md)</sup>
import ChatInput from './components/ChatInput.vue'

// 创建 StreamingResponse 后在这里导入
// import StreamingResponse from './components/StreamingResponse.vue'

// 响应式数据（第一周需求）<sup>[[2]](https://github.com/ly-0110/RAG4ZRDDS/)</sup>
const userInput = ref('')
const answer = ref('')
const isLoading = ref(false)
const hasAnswer = ref(false)
const lastResponseKey = ref(0)
let abortController = null

// API 接口地址（根据项目第 5 节 /query SSE）<sup>[[3]](Pasted_Text_1787902362988.txt)</sup>
const API_URL = 'http://localhost:8000/query'

// 流式回答函数（核心改造点）<sup>[[4]](Pasted_Text_1787902676690.txt)</sup>
const streamResponse = async (question) => {
  try {
    abortController?.abort()
    abortController = new AbortController()
    
    const response = await fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
      signal: abortController.signal
    })

    if (!response.ok) throw new Error(response.statusText)

    const reader = response.body.getReader()
    let decodedText = ''
    
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      
      const chunk = new TextDecoder('utf-8').decode(value)
      // 简单处理 SSE 流，实际需解析 data: prefix<sup>[[5]](Pasted_Text_1787902676690.txt)</sup>
      decodedText += chunk.replace(/^data: /, '').trim()
      
      answer.value = decodedText
      hasAnswer.value = true
    }
  } catch (error) {
    if (error.name !== 'AbortError') {
      console.error('获取回答失败:', error)
    }
  }
}

// 提交查询（由 ChatInput 组件内部处理）<sup>[[6]](Pasted_Text_1787902676690.txt)</sup>
const handleQuery = async (question) => {
  if (!question.trim()) return
  
  // 清空状态并触发流式响应
  answer.value = ''
  hasAnswer.value = false
  isLoading.value = true
  lastResponseKey.value++
  
  await streamResponse(question)
}

// StreamingResponse 组件集成示例（第二周添加）
/*
import { watch } from 'vue'

watch(() => userInput.value, (newVal) => {
  if (!isLoading.value && newVal.trim()) {
    handleQuery(newVal)
  }
})
*/
</script>

<style scoped>
.chat-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.input-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 20px;
}

input[type="text"] {
  width: 100%;
  padding: 12px;
  font-size: 16px;
  border: 1px solid #ccc;
  border-radius: 8px;
  resize: vertical;
}

.submit-btn-container {
  display: flex;
  justify-content: center;
}

.response-section {
  min-height: 100px;
  padding: 15px;
  border: 1px solid #eee;
  border-radius: 8px;
  background-color: #f9f9f9;
}

.streaming-response {
  white-space: pre-wrap;
  word-wrap: break-word;
  line-height: 1.6;
  color: #333;
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