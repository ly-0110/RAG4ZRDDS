<template>
  <div class="chat-input-container">
    <div class="input-shell" :class="{ 'is-busy': loading }">
      <div class="input-toolbar">
        <div class="input-mode">
          <span class="mode-icon" aria-hidden="true">⌘</span>
          <div>
            <span class="toolbar-label">输入控制台</span>
            <span class="toolbar-caption">提问后自动检索文档上下文</span>
          </div>
        </div>
        <div class="toolbar-options">
          <span class="control-chip"><i class="chip-dot"></i>语义检索</span>
          <span class="control-chip">Top-K 6</span>
        </div>
      </div>

      <textarea
        v-model="userInput"
        :placeholder="placeholder"
        rows="3"
        maxlength="200"
        aria-label="输入你的问题"
        @keydown.enter="handleEnterKey"
        @input="updateLength"
        :disabled="loading"
      ></textarea>

      <div class="submit-area">
        <div class="input-hints">
          <span class="word-count">{{ userInput.length }}/{{ MAX_LENGTH }}</span>
          <span class="keyboard-hint">Enter 提交 · Shift + Enter 换行</span>
        </div>
        <button
          :disabled="!canSubmit"
          @click="handleSubmit"
          class="submit-btn"
          type="button"
        >
          <span>{{ loading ? '正在检索' : '开始检索' }}</span>
          <span v-if="loading" class="loading-icon" aria-hidden="true"></span>
          <span v-else class="submit-arrow" aria-hidden="true">↗</span>
        </button>
      </div>
    </div>

    <div v-if="!hasAnswer && !loading" class="tip-box">
      <div class="tip-heading">
        <div>
          <p class="tip-title">建议从这些问题开始</p>
          <span class="tip-caption">点击示例即可填入控制台</span>
        </div>
        <span class="tip-mark" aria-hidden="true">✦</span>
      </div>
      <div class="tips-list">
        <button
          v-for="suggestion in suggestions"
          :key="suggestion"
          class="suggestion-chip"
          type="button"
          @click="useSuggestion(suggestion)"
        >
          <span>↗</span>{{ suggestion }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  loading: { type: Boolean, default: false },
  hasAnswer: { type: Boolean, default: false },
})
const emit = defineEmits(['submit'])

const userInput = ref('')
const MAX_LENGTH = 200
const suggestions = [
  '如何调用 DataWriter API？',
  'ZRDDS 故障码 E1003 是什么意思？',
  '数据发送速率如何配置？',
  'v2.4 版本新增了哪些功能？',
]

const canSubmit = computed(
  () => userInput.value.trim().length > 0 && !props.loading,
)

const placeholder = computed(() =>
  userInput.value.length >= MAX_LENGTH
    ? '请精简问题内容'
    : '输入关于 ZRDDS API、配置或故障排查的问题…',
)

const updateLength = () => {
  if (userInput.value.length > MAX_LENGTH) {
    userInput.value = userInput.value.slice(0, MAX_LENGTH)
  }
}

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

const useSuggestion = (suggestion) => {
  if (props.loading) return
  userInput.value = suggestion
}

defineExpose({ question: userInput })
</script>

<style scoped>
.chat-input-container {
  display: flex;
  flex-direction: column;
  gap: 11px;
  margin-bottom: 20px;
}

.input-shell {
  padding: 15px 15px 11px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.84);
  box-shadow: var(--shadow-float), var(--shadow-inset);
  transition: border-color 0.25s ease, box-shadow 0.25s ease, transform 0.25s ease;
}

.input-shell:focus-within {
  border-color: rgba(62, 145, 157, 0.62);
  box-shadow: 0 17px 38px rgba(40, 87, 106, 0.13), 0 0 0 4px rgba(94, 156, 173, 0.1);
  transform: translateY(-1px);
}

.input-shell.is-busy {
  border-color: rgba(94, 156, 173, 0.38);
}

.input-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 2px 12px;
}

.input-mode,
.toolbar-options,
.control-chip,
.tip-heading {
  display: flex;
  align-items: center;
}

.input-mode {
  gap: 9px;
}

.mode-icon {
  width: 27px;
  height: 27px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(94, 156, 173, 0.2);
  border-radius: 9px;
  background: rgba(94, 156, 173, 0.11);
  color: var(--primary-700);
  font-size: 0.9rem;
  font-weight: 800;
}

.toolbar-label,
.toolbar-caption {
  display: block;
}

.toolbar-label {
  color: var(--ink-deep);
  font-size: 0.7rem;
  font-weight: 800;
}

.toolbar-caption {
  margin-top: 2px;
  color: var(--text-subtle);
  font-size: 0.62rem;
}

.toolbar-options {
  gap: 6px;
}

.control-chip {
  gap: 5px;
  padding: 5px 7px;
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--text-muted);
  font-size: 0.6rem;
  font-weight: 700;
}

.chip-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--teal);
}

textarea {
  width: 100%;
  min-height: 88px;
  max-height: 220px;
  display: block;
  box-sizing: border-box;
  padding: 14px 14px 12px;
  resize: vertical;
  outline: none;
  border: 1px solid rgba(138, 175, 202, 0.32);
  border-radius: var(--radius-md);
  background: rgba(247, 251, 252, 0.92);
  color: var(--text);
  font-size: 0.94rem;
  line-height: 1.6;
  transition: border-color 0.22s ease, box-shadow 0.22s ease, background 0.22s ease;
}

textarea::placeholder {
  color: #8195a0;
}

textarea:focus {
  border-color: rgba(76, 133, 148, 0.65);
  background: #fff;
  box-shadow: 0 0 0 3px rgba(118, 164, 178, 0.12);
}

textarea:disabled {
  opacity: 0.72;
  cursor: not-allowed;
}

.submit-area {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 2px 0;
}

.input-hints {
  display: flex;
  align-items: center;
  gap: 9px;
}

.word-count {
  color: var(--primary-700);
  font: 0.68rem 'Consolas', monospace;
}

.keyboard-hint {
  color: var(--text-subtle);
  font-size: 0.61rem;
}

.submit-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 14px 10px 16px;
  border: 0;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--primary-600), var(--primary-700));
  color: #fff;
  cursor: pointer;
  font-size: 0.75rem;
  font-weight: 800;
  box-shadow: 0 9px 18px rgba(57, 125, 145, 0.25);
  transition: transform 0.2s ease, box-shadow 0.2s ease, filter 0.2s ease;
}

.submit-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 12px 24px rgba(57, 125, 145, 0.32);
  filter: brightness(1.04);
}

.submit-btn:active:not(:disabled) {
  transform: translateY(1px) scale(0.97);
}

.submit-btn:focus-visible {
  outline: 3px solid rgba(94, 156, 173, 0.26);
  outline-offset: 3px;
}

.submit-btn:disabled {
  background: linear-gradient(135deg, #b9cbd1, #aebfc6);
  box-shadow: none;
  cursor: not-allowed;
  opacity: 0.83;
}

.submit-arrow {
  width: 19px;
  height: 19px;
  display: grid;
  place-items: center;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.16);
  font-size: 0.92rem;
  line-height: 1;
}

.loading-icon {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.38);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.75s linear infinite;
}

.tip-box {
  padding: 13px 15px 14px;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: linear-gradient(115deg, rgba(247, 251, 252, 0.86), rgba(239, 247, 249, 0.74));
  box-shadow: var(--shadow-card);
}

.tip-heading {
  justify-content: space-between;
  gap: 12px;
}

.tip-title {
  margin: 0;
  color: var(--primary-700);
  font-size: 0.73rem;
  font-weight: 800;
}

.tip-caption {
  display: block;
  margin-top: 3px;
  color: var(--text-subtle);
  font-size: 0.62rem;
}

.tip-mark {
  width: 25px;
  height: 25px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: rgba(94, 156, 173, 0.12);
  color: var(--primary-600);
  font-size: 0.78rem;
}

.tips-list {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  margin-top: 11px;
}

.suggestion-chip {
  min-width: 0;
  overflow: hidden;
  padding: 8px 9px;
  border: 1px solid rgba(192, 216, 222, 0.9);
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.58);
  color: var(--text-muted);
  cursor: pointer;
  font-size: 0.67rem;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: border-color 0.2s ease, color 0.2s ease, background 0.2s ease, transform 0.2s ease;
}

.suggestion-chip span {
  margin-right: 5px;
  color: var(--primary-600);
}

.suggestion-chip:hover {
  border-color: rgba(94, 156, 173, 0.46);
  background: rgba(255, 255, 255, 0.92);
  color: var(--primary-700);
  transform: translateY(-1px);
}

.suggestion-chip:focus-visible {
  outline: 3px solid rgba(94, 156, 173, 0.22);
  outline-offset: 2px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (prefers-reduced-motion: reduce) {
  .input-shell,
  .submit-btn,
  .suggestion-chip {
    transition-duration: 0.01ms;
  }

  .loading-icon {
    animation: none;
  }
}

@media (max-width: 560px) {
  .input-toolbar {
    align-items: flex-start;
  }

  .toolbar-options {
    display: none;
  }

  .keyboard-hint {
    display: none;
  }

  .tips-list {
    grid-template-columns: 1fr;
  }
}
</style>
