<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{
  search: [address: string]
}>()

defineProps<{
  loading: boolean
}>()

const address = ref('')

function handleSubmit() {
  const trimmed = address.value.trim()
  if (trimmed) {
    emit('search', trimmed)
  }
}
</script>

<template>
  <form @submit.prevent="handleSubmit" class="flex gap-2.5">
    <div class="flex-1 relative">
      <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-surface-300 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
      </svg>
      <input
        v-model="address"
        type="text"
        placeholder="Enter an LA address (e.g., 11348 Elderwood St)"
        class="w-full pl-9 pr-4 py-2.5 text-[13px] border border-surface-200 rounded-md bg-surface-50 text-cover-black placeholder:text-surface-300 focus:outline-none focus:border-surface-400 transition-colors"
        :disabled="loading"
      />
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
