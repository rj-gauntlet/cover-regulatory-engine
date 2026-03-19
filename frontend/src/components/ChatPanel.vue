<script setup lang="ts">
import { ref, nextTick, watch, onMounted, onUnmounted } from 'vue'
import type { ChatMessage } from '@/types'
import { api } from '@/services/api'

const props = defineProps<{
  assessmentId: string
  show: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

const messages = ref<ChatMessage[]>([])
const input = ref('')
const streaming = ref(false)
const loading = ref(false)
const error = ref<string | null>(null)
const messagesContainer = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLInputElement | null>(null)
let abortController: AbortController | null = null

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

async function loadHistory() {
  loading.value = true
  error.value = null
  try {
    messages.value = await api.chat.history(props.assessmentId)
    scrollToBottom()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load chat history'
  } finally {
    loading.value = false
  }
}

async function send() {
  const text = input.value.trim()
  if (!text || streaming.value) return

  const userMessage: ChatMessage = {
    id: crypto.randomUUID(),
    role: 'user',
    content: text,
    created_at: new Date().toISOString(),
  }
  messages.value.push(userMessage)
  input.value = ''
  scrollToBottom()

  const assistantMessage: ChatMessage = {
    id: crypto.randomUUID(),
    role: 'assistant',
    content: '',
    created_at: new Date().toISOString(),
  }
  messages.value.push(assistantMessage)
  streaming.value = true
  error.value = null
  abortController = new AbortController()

  try {
    await api.chat.stream(
      props.assessmentId,
      text,
      (token: string) => {
        assistantMessage.content += token
        scrollToBottom()
      },
      () => {
        streaming.value = false
      },
      abortController.signal,
    )
  } catch (e) {
    streaming.value = false
    if (e instanceof DOMException && e.name === 'AbortError') return
    error.value = e instanceof Error ? e.message : 'Failed to send message'
    if (!assistantMessage.content) {
      messages.value.pop()
    }
  } finally {
    abortController = null
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

watch(() => props.show, (visible) => {
  if (visible) {
    nextTick(() => inputRef.value?.focus())
  }
})

watch(() => props.assessmentId, () => {
  messages.value = []
  loadHistory()
})

onMounted(() => {
  if (props.assessmentId) {
    loadHistory()
  }
})

onUnmounted(() => {
  abortController?.abort()
})
</script>

<template>
  <div v-if="show" class="flex flex-col w-full h-full bg-white border-t border-surface-200">
    <!-- Header -->
    <div class="flex items-center justify-between px-5 py-3 border-b border-surface-200 bg-surface-50 shrink-0">
      <h3 class="text-[13px] font-semibold text-cover-black">Chat</h3>
      <button
        @click="emit('close')"
        class="w-7 h-7 flex items-center justify-center rounded text-surface-300 hover:text-surface-500 hover:bg-surface-100 transition-colors"
        aria-label="Close chat"
      >
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <!-- Messages -->
    <div ref="messagesContainer" class="flex-1 overflow-y-auto px-5 py-5 space-y-3">
      <div v-if="loading" class="flex items-center justify-center py-8">
        <div class="flex items-center gap-2 text-[13px] text-surface-300">
          <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Loading history…
        </div>
      </div>

      <div v-else-if="messages.length === 0" class="flex flex-col items-center justify-center py-12 text-center">
        <div class="w-10 h-10 rounded-full bg-surface-50 border border-surface-200 flex items-center justify-center mb-3">
          <svg class="w-5 h-5 text-surface-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
          </svg>
        </div>
        <p class="text-[13px] text-surface-400">Ask a question about this assessment</p>
      </div>

      <template v-else>
        <div
          v-for="msg in messages"
          :key="msg.id"
          :class="['flex', msg.role === 'user' ? 'justify-end' : 'justify-start']"
        >
          <div
            :class="[
              'max-w-[85%] rounded-xl px-3.5 py-2.5 text-[13px] leading-relaxed whitespace-pre-wrap break-words',
              msg.role === 'user'
                ? 'bg-cover-black text-white rounded-br-sm'
                : 'bg-surface-50 text-cover-black border border-surface-200 rounded-bl-sm',
            ]"
          >
            {{ msg.content }}
            <span
              v-if="streaming && msg === messages[messages.length - 1] && msg.role === 'assistant'"
              class="inline-flex ml-0.5 align-baseline"
            >
              <span class="typing-dot" />
              <span class="typing-dot animation-delay-150" />
              <span class="typing-dot animation-delay-300" />
            </span>
          </div>
        </div>
      </template>

      <div
        v-if="streaming && messages.length > 0 && messages[messages.length - 1].role === 'assistant' && !messages[messages.length - 1].content"
        class="flex justify-start"
      >
        <div class="bg-surface-50 border border-surface-200 rounded-xl rounded-bl-sm px-3.5 py-2.5">
          <span class="inline-flex gap-0.5">
            <span class="typing-dot" />
            <span class="typing-dot animation-delay-150" />
            <span class="typing-dot animation-delay-300" />
          </span>
        </div>
      </div>
    </div>

    <div v-if="error" class="px-5 py-2 bg-red-50 border-t border-red-100 shrink-0">
      <p class="text-[11px] text-cover-red">{{ error }}</p>
    </div>

    <!-- Input -->
    <div class="px-5 py-3 border-t border-surface-200 bg-white shrink-0">
      <div class="flex items-center gap-2">
        <input
          ref="inputRef"
          v-model="input"
          @keydown="handleKeydown"
          type="text"
          placeholder="Ask a follow-up question…"
          :disabled="streaming"
          class="flex-1 rounded-lg border border-surface-200 bg-surface-50 px-3.5 py-2 text-[13px] text-cover-black placeholder:text-surface-300 focus:outline-none focus:border-surface-400 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        />
        <button
          @click="send"
          :disabled="!input.trim() || streaming"
          class="shrink-0 w-9 h-9 flex items-center justify-center rounded-lg bg-cover-black text-white hover:bg-cover-charcoal transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.typing-dot {
  display: inline-block;
  width: 5px;
  height: 5px;
  margin: 0 1px;
  border-radius: 50%;
  background-color: currentColor;
  opacity: 0.3;
  animation: typing-bounce 1.2s infinite ease-in-out;
}
.animation-delay-150 { animation-delay: 0.15s; }
.animation-delay-300 { animation-delay: 0.3s; }
@keyframes typing-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.3; }
  30% { transform: translateY(-4px); opacity: 0.8; }
}
</style>
