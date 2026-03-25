<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

const STORAGE_KEY = 'cover-recent-searches'
const MAX_RECENT = 10

const emit = defineEmits<{
  search: [address: string]
}>()

const props = defineProps<{
  loading: boolean
  modelValue?: string
}>()

const address = ref(props.modelValue || '')
const showDropdown = ref(false)

watch(() => props.modelValue, (v) => {
  if (v !== undefined && v !== address.value) address.value = v
})
const recentSearches = ref<string[]>(loadRecent())

const filteredSearches = computed(() => {
  const q = address.value.trim().toLowerCase()
  if (!q) return recentSearches.value
  return recentSearches.value.filter(s => s.toLowerCase().includes(q))
})

function loadRecent(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveRecent(addr: string) {
  const filtered = recentSearches.value.filter(
    s => s.toLowerCase() !== addr.toLowerCase()
  )
  const updated = [addr, ...filtered].slice(0, MAX_RECENT)
  recentSearches.value = updated
  localStorage.setItem(STORAGE_KEY, JSON.stringify(updated))
}

function removeRecent(addr: string) {
  const updated = recentSearches.value.filter(
    s => s.toLowerCase() !== addr.toLowerCase()
  )
  recentSearches.value = updated
  localStorage.setItem(STORAGE_KEY, JSON.stringify(updated))
}

function handleSubmit() {
  const trimmed = address.value.trim()
  if (trimmed) {
    saveRecent(trimmed)
    showDropdown.value = false
    emit('search', trimmed)
  }
}

function selectRecent(addr: string) {
  address.value = addr
  saveRecent(addr)
  showDropdown.value = false
  emit('search', addr)
}

function handleFocus() {
  showDropdown.value = true
}

function handleBlur() {
  setTimeout(() => { showDropdown.value = false }, 150)
}

const inputEl = ref<HTMLInputElement | null>(null)

function handleKeydown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault()
    inputEl.value?.focus()
    inputEl.value?.select()
  }
}

onMounted(() => document.addEventListener('keydown', handleKeydown))
onUnmounted(() => document.removeEventListener('keydown', handleKeydown))
</script>

<template>
  <form @submit.prevent="handleSubmit" class="flex gap-2.5">
    <div class="flex-1 relative">
      <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-surface-300 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
      </svg>
      <input
        ref="inputEl"
        v-model="address"
        type="text"
        placeholder="Enter an LA address (e.g., 11344 Elderwood St)"
        class="w-full pl-9 pr-14 py-2.5 text-[13px] border border-surface-200 rounded-md bg-surface-50 text-cover-black placeholder:text-surface-300 focus:outline-none focus:border-surface-400 transition-colors"
        :disabled="loading"
        @focus="handleFocus"
        @blur="handleBlur"
      />
      <kbd class="absolute right-3 top-1/2 -translate-y-1/2 hidden sm:inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] text-surface-300 bg-surface-100 border border-surface-200 rounded font-mono pointer-events-none">⌘K</kbd>
      <ul
        v-if="showDropdown && !loading && filteredSearches.length"
        class="absolute z-50 mt-1 w-full bg-white border border-surface-200 rounded-md shadow-lg max-h-60 overflow-y-auto"
      >
        <li
          v-for="item in filteredSearches"
          :key="item"
          class="flex items-center justify-between px-3 py-2 text-[13px] text-cover-black hover:bg-surface-50 cursor-pointer group"
          @mousedown.prevent="selectRecent(item)"
        >
          <span class="truncate">{{ item }}</span>
          <button
            class="ml-2 text-surface-300 hover:text-cover-red opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
            @mousedown.prevent.stop="removeRecent(item)"
          >
            <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </li>
      </ul>
    </div>
    <button
      type="submit"
      :disabled="loading || !address.trim()"
      class="px-5 py-2.5 bg-cover-black text-white text-[11px] font-semibold uppercase tracking-widest rounded-md hover:bg-cover-charcoal transition-colors disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
    >
      <span v-if="loading" class="flex items-center gap-1.5">
        <svg class="animate-spin h-3 w-3" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        Assessing
      </span>
      <span v-else>Assess</span>
    </button>
  </form>
</template>
