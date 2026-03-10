<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{
  search: [address: string]
}>()

const props = defineProps<{
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
  <form @submit.prevent="handleSubmit" class="flex gap-2">
    <div class="flex-1 relative">
      <input
        v-model="address"
        type="text"
        placeholder="Enter an LA address (e.g., 1234 Main St, Los Angeles)"
        class="w-full px-4 py-2.5 text-sm border border-surface-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent placeholder:text-surface-400"
        :disabled="loading"
      />
    </div>
    <button
      type="submit"
      :disabled="loading || !address.trim()"
      class="px-4 py-2.5 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
    >
      Assess
    </button>
  </form>
</template>
