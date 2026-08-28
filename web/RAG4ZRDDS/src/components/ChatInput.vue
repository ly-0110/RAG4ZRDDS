<template>
  <div class="chat-input-container">
    <!-- 输入框区域 -->
    <div class="input-wrapper">
      <textarea
        v-model="userInput"
        :placeholder="placeholder"
        rows="3"
        @keydown.enter.prevent="handleEnterKey"
        @input="updateLength"
        :disabled="isLoading"
      ></textarea>
      
      <!-- 提交按钮区域 -->
      <div class="submit-area">
        <span class="word-count">{{ userInput.length }}/200</span>
        <button 
          :disabled="!isValidSubmit || isLoading" 
          @click="handleSubmit"
          class="submit-btn"
        >
          {{ submitButtonText }}
          <span v-if="isLoading" class="loading-icon">⏳</span>
        </button>
      </div>
    </div>
    
    <!-- 提示信息区域 -->
    <div v-if="!hasAnswer && !isLoading" class="tip-box">
      <p class="tip-title">💡 提问示例：</p>
      <ul class="tips-list">
        <li>如何调用 DataWriter API?</li>
        <li>ZRDDS 故障码 E1003 是什么意思</li>
        <li>数据发送速率如何配置</li>
        <li>v2.4 版本新增了哪些功能</li>
      </ul>
    </div>
    
    <!-- 空状态占位 -->
    <div v-if="!hasAnswer && !isLoading" class="empty-state">
      <p>输入问题后按 Enter 或点击「提问」按钮</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

// API 接口地址（根据项目第 5 节 /query SSE）<source id="6">
const API_URL = '/query'

// 响应式数据
const userInput = ref('')
const hasAnswer = ref(false)
const isLoading = ref(false)
let abortController = null
let debounceTimer = null

// 字数限制（第一周核心：200字符）<source id="1">
const MAX_LENGTH = 200

// 按钮文本
const submitButtonText = computed(() => isLoading.value ? '提问中...' : '提问')

// 是否可提交
const isValidSubmit = computed(() => userInput.value.trim().length > 0 && !isLoading.value)

// 占位符
const placeholder = computed(() => 
  userInput.value.length >= MAX_LENGTH 
    ? '请精简问题内容' 
    : '请输入问题，例如：ZRDDS用户手册.pdf第42页关于API调用的说明...'
)

// 更新字符数
const updateLength = () => {
  if (userInput.value.length >= MAX_LENGTH) {
    userInput.value = userInput.value.slice(0, MAX_LENGTH)
  }
}

// 处理 Enter 键提交（需 Ctrl/Cmd + Enter）<source id="6">
const handleEnterKey = (e) => {
  if (e.ctrlKey || e.metaKey) {
    handleSubmit()
  }
}

// 提交查询
const handleSubmit = async () => {
  if (!userInput.value.trim()) return
  
  const question = userInput.value.trim()
  hasAnswer.value = false
  
  // 创建新的 AbortController 支持取消前一次请求
  abortController?.abort()
  abortController = new AbortController()
  
  try {
    isLoading.value = true
    
    // 调用 SSE 接口（实际使用时修改为真实 API_URL）<source id="6">
    const response = await fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
      signal: abortController.signal
    })

    if (!response.ok) throw new Error(response.statusText)

    // 开始流式接收回答（这里只提交，实际 SSE 处理在 StreamingResponse 组件）
    console.log('问题已提交:', question)
  } catch (error) {
    console.error('提问失败:', error)
    alert('请求异常，请检查后端服务是否启动（make serve）')
  } finally {
    isLoading.value = false
  }
}

// 暴露给父组件的 props<source id="6">
defineExpose({
  question: userInput,
  submitQuestion: handleSubmit
})
</script>

<style scoped>
.chat-input-container {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 20px;
}

.input-wrapper {
  position: relative;
}

textarea {
  width: 100%;
  padding: 14px 16px 14px 14px;
  font-size: 16px;
  line-height: 1.5;
  border: 2px solid #e0e0e0;
  border-radius: 12px;
  resize: vertical;
  min-height: 80px;
  max-height: 200px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  transition: border-color 0.3s;
  outline: none;
  box-sizing: border-box;
}

textarea::placeholder {
  color: #999;
  font-style: italic;
}

textarea:focus {
  border-color: #007bff;
}

.submit-area {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-right: 8px;
}

.word-count {
  font-size: 14px;
  color: #666;
}

.submit-btn {
  padding: 10px 32px;
  font-size: 15px;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.submit-btn:hover:not(:disabled) {
  background-color: #0056b3;
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0, 123, 255, 0.3);
}

.submit-btn:active:not(:disabled) {
  background-color: #004494;
  transform: translateY(0);
}

.submit-btn:disabled {
  background-color: #ccc;
  cursor: not-allowed;
  opacity: 0.7;
}

.loading-icon {
  font-size: 16px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.tip-box {
  background-color: #f8f9fa;
  border-left: 4px solid #17a2b8;
  padding: 12px 16px;
  border-radius: 4px;
  font-size: 14px;
  color: #333;
}

.tip-title {
  font-weight: 600;
  margin-bottom: 8px;
}

.tips-list {
  margin: 0;
  padding-left: 20px;
}

.tips-list li {
  margin-bottom: 6px;
  color: #555;
}

.empty-state {
  text-align: center;
  padding: 30px;
  color: #999;
  font-size: 14px;
}
</style>