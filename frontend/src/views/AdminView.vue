<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { PipelineStatus, ZoneRule } from '@/types'
import { api } from '@/services/api'

const status = ref<PipelineStatus | null>(null)
const rules = ref<ZoneRule[]>([])
const loading = ref(true)
const activeTab = ref('status')

onMounted(async () => {
  try {
    const [s, r] = await Promise.all([
      api.admin.pipelineStatus(),
      api.admin.rules(),
    ])
    status.value = s
    rules.value = r
  } catch (e) {
    console.error('Failed to load admin data:', e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="h-full overflow-y-auto bg-surface-50">
    <div class="max-w-5xl mx-auto p-6">
      <h1 class="text-xl font-semibold text-surface-900 mb-6">Admin Panel</h1>

      <!-- Tabs -->
      <div class="flex gap-1 mb-6 bg-surface-100 p-1 rounded-lg w-fit">
        <button
          v-for="tab in ['status', 'rules']"
          :key="tab"
          @click="activeTab = tab"
          :class="[
            'px-4 py-2 text-sm font-medium rounded-md transition-colors capitalize',
            activeTab === tab ? 'bg-white text-surface-900 shadow-sm' : 'text-surface-600 hover:text-surface-900'
          ]"
        >
          {{ tab === 'status' ? 'Pipeline Status' : 'Zone Rules' }}
        </button>
      </div>

      <div v-if="loading" class="text-center py-12 text-surface-500">Loading...</div>

      <!-- Pipeline Status -->
      <div v-else-if="activeTab === 'status' && status" class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div v-for="(value, label) in {
          'Raw Sources': status.total_raw_sources,
          'Regulations': status.total_regulations,
          'Chunks': status.total_chunks,
          'Zone Rules': status.total_zone_rules,
          'Verified Rules': status.verified_rules,
          'Cached Parcels': status.total_parcels_cached,
          'Assessments': status.total_assessments,
          'Feedback': status.total_feedback,
        }" :key="label" class="bg-white rounded-lg border border-surface-200 p-4">
          <p class="text-2xl font-bold text-surface-900">{{ value }}</p>
          <p class="text-xs text-surface-500 mt-1">{{ label }}</p>
        </div>
      </div>

      <!-- Zone Rules -->
      <div v-else-if="activeTab === 'rules'" class="bg-white rounded-lg border border-surface-200 overflow-hidden">
        <table class="w-full text-sm">
          <thead class="bg-surface-50 border-b border-surface-200">
            <tr>
              <th class="text-left px-4 py-2.5 text-xs font-semibold text-surface-500 uppercase">Zone</th>
              <th class="text-left px-4 py-2.5 text-xs font-semibold text-surface-500 uppercase">Parameter</th>
              <th class="text-left px-4 py-2.5 text-xs font-semibold text-surface-500 uppercase">Value</th>
              <th class="text-left px-4 py-2.5 text-xs font-semibold text-surface-500 uppercase">Section</th>
              <th class="text-left px-4 py-2.5 text-xs font-semibold text-surface-500 uppercase">Verified</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-surface-100">
            <tr v-for="rule in rules" :key="rule.id" class="hover:bg-surface-50">
              <td class="px-4 py-2.5 font-medium text-surface-800">{{ rule.zone_class }}</td>
              <td class="px-4 py-2.5 text-surface-600">{{ rule.parameter }}</td>
              <td class="px-4 py-2.5 text-surface-800">{{ rule.base_value }} {{ rule.unit }}</td>
              <td class="px-4 py-2.5 text-surface-500">{{ rule.section_number }}</td>
              <td class="px-4 py-2.5">
                <span :class="rule.is_verified ? 'text-green-600' : 'text-surface-400'">
                  {{ rule.is_verified ? '✓' : '—' }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
