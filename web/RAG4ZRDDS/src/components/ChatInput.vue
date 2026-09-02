<template>
  <div class="chat-input-container">
    <!-- 输入框区域 -->
    <div class="input-wrapper">
      <textarea
        v-model="userInput"
        :placeholder="placeholder"
        rows="3"
        @keydown.enter="handleEnterKey"
        @input="updateLength"
        :disabled="loading"
      ></textarea>

      <!-- 提交按钮区域 -->
      <div class="submit-area">
        <span class="word-count">{{ userInput.length }}/{{ MAX_LENGTH }}</span>
        <button
          :disabled="!canSubmit"
          @click="handleSubmit"
          class="submit-btn"
        >
          {{ loading ? '回答中...' : '提问' }}
          <span v-if="loading" class="loading-icon">⏳</span>
        </button>
      </div>
    </div>

    <!-- 提示信息区域（尚无回答且空闲时显示） -->
    <div v-if="!hasAnswer && !loading" class="tip-box">
      <p class="tip-title">💡 提问示例：</p>
      <ul class="tips-list">
        <li>如何调用 DataWriter API?</li>
        <li>ZRDDS 故障码 E1003 是什么意思</li>
        <li>数据发送速率如何配置</li>
        <li>v2.4 版本新增了哪些功能</li>
      </ul>
    </div>
  </div>
</template>

<script setup>
// 纯输入组件（2026-08-29 接线修复）：只负责输入交互，提问动作通过
// submit 事件交给父组件（App.vue）统一走 /query SSE——组件内不再自发请求。
import { ref, computed } from 'vue'

const props = defineProps({
  loading: { type: Boolean, default: false },   // 后端是否正在回答
  hasAnswer: { type: Boolean, default: false }, // 是否已有回答/引用（隐藏示例提示）
})
const emit = defineEmits(['submit'])

const userInput = ref('')

// 字数限制（前端先行约束；后端 QueryRequest 上限 2000）
const MAX_LENGTH = 200

const canSubmit = computed(
  () => userInput.value.trim().length > 0 && !props.loading,
)

const placeholder = computed(() =>
  userInput.value.length >= MAX_LENGTH
    ? '请精简问题内容'
    : '请输入问题，例如：ZRDDS用户手册.pdf第42页关于API调用的说明...',
)

// 超过上限即截断
const updateLength = () => {
  if (userInput.value.length > MAX_LENGTH) {
    userInput.value = userInput.value.slice(0, MAX_LENGTH)
  }
}

// Enter 提交；Shift+Enter 换行（与占位提示"按 Enter 提交"一致）
const handleEnterKey = (e) => {
  if (e.shiftKey) return
  e.preventDefault()
  handleSubmit()
}

const handleSubmit = () => {
  const question = userInput.value.trim()
  if (!question || props.loading) return
  emit('submit', question)
}

defineExpose({ question: userInput })
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
  font-size: 14px;
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
  font-weight: bold;
  margin-bottom: 8px;
}

.tips-list {
  margin: 0;
  padding-left: 20px;
}

.tips-list li {
  margin: 4px 0;
  color: #555;
}
</style>
