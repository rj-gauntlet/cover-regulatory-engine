<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import type { PipelineStatus, ZoneRule, AdminFeedback } from '@/types'
import { api } from '@/services/api'

const status = ref<PipelineStatus | null>(null)
const rules = ref<ZoneRule[]>([])
const feedback = ref<AdminFeedback[]>([])
const loading = ref(true)
const feedbackLoading = ref(false)
const activeTab = ref('status')
const zoneClassFilter = ref<string>('')
const showIngestionConfirm = ref(false)
const ingestionTriggering = ref(false)
const ingestionResult = ref<{ status: string; stats: Record<string, number> } | null>(null)
const ruleUpdating = ref<Set<string>>(new Set())
const error = ref<string | null>(null)

const ZONE_CLASS_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'R1', label: 'R1' },
  { value: 'R2', label: 'R2' },
  { value: 'RD', label: 'RD' },
  { value: 'RE', label: 'RE' },
]

const filteredRules = computed(() => {
  if (!zoneClassFilter.value) return rules.value
  if (zoneClassFilter.value === 'RD' || zoneClassFilter.value === 'RE') {
    return rules.value.filter((r) => r.zone_class.startsWith(zoneClassFilter.value))
  }
  return rules.value.filter((r) => r.zone_class === zoneClassFilter.value)
})

function truncateId(id: string, len = 8) {
  if (!id) return '—'
  return id.length > len ? `${id.slice(0, len)}…` : id
}

function formatDate(iso: string) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

async function loadRules() {
  const zoneClass = zoneClassFilter.value && zoneClassFilter.value !== 'RD' && zoneClassFilter.value !== 'RE' ? zoneClassFilter.value : undefined
  rules.value = await api.admin.rules(zoneClass)
}

async function loadFeedback() {
  feedbackLoading.value = true
  error.value = null
  try { feedback.value = await api.admin.feedback() }
  catch (e) { error.value = 'Failed to load feedback'; feedback.value = [] }
  finally { feedbackLoading.value = false }
}

async function toggleRuleVerified(rule: ZoneRule) {
  if (ruleUpdating.value.has(rule.id)) return
  ruleUpdating.value.add(rule.id)
  try {
    const updated = await api.admin.updateRule(rule.id, { is_verified: !rule.is_verified })
    rule.is_verified = updated.is_verified
  } catch (e) { error.value = 'Failed to update rule verification' }
  finally { ruleUpdating.value.delete(rule.id) }
}

async function triggerIngestion() {
  ingestionTriggering.value = true
  ingestionResult.value = null
  error.value = null
  try {
    ingestionResult.value = await api.admin.triggerIngestion()
    showIngestionConfirm.value = false
    status.value = await api.admin.pipelineStatus()
  } catch (e) { error.value = 'Failed to trigger ingestion' }
  finally { ingestionTriggering.value = false }
}

const tabs = [
  { id: 'status', label: 'Pipeline Status' },
  { id: 'rules', label: 'Zone Rules' },
  { id: 'feedback', label: 'Feedback Review' },
]

onMounted(async () => {
  try {
    const [s, r] = await Promise.all([api.admin.pipelineStatus(), api.admin.rules()])
    status.value = s
    rules.value = r
  } catch (e) { error.value = 'Failed to load admin data' }
  finally { loading.value = false }
})
</script>

<template>
  <div class="h-full overflow-y-auto bg-surface-50">
    <div class="max-w-5xl mx-auto p-8">
      <h1 class="text-lg font-semibold text-cover-black tracking-tight mb-8">Admin Panel</h1>

      <!-- Tabs -->
      <div class="flex gap-1 mb-8 bg-surface-100 p-1 rounded-lg w-fit">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          @click="activeTab = tab.id; if (tab.id === 'feedback') loadFeedback();"
          :class="[
            'px-4 py-2 text-[12px] font-medium rounded-md transition-colors',
            activeTab === tab.id ? 'bg-white text-cover-black shadow-sm' : 'text-surface-400 hover:text-cover-black',
          ]"
        >
          {{ tab.label }}
        </button>
      </div>

      <div v-if="error" class="mb-4 bg-red-50 border border-red-200 rounded-lg p-4">
        <p class="text-[13px] text-cover-red">{{ error }}</p>
      </div>

      <div v-if="loading" class="text-center py-12 text-surface-400 text-[13px]">Loading…</div>

      <!-- Pipeline Status -->
      <div v-else-if="activeTab === 'status' && status" class="space-y-6">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div
            v-for="(value, label) in {
              'Raw Sources': status.total_raw_sources,
              'Regulations': status.total_regulations,
              'Chunks': status.total_chunks,
              'Zone Rules': status.total_zone_rules,
              'Verified Rules': status.verified_rules,
              'Cached Parcels': status.total_parcels_cached,
              'Assessments': status.total_assessments,
              'Feedback': status.total_feedback,
            }"
            :key="label"
            class="bg-white rounded-lg border border-surface-200 p-4"
          >
            <p class="text-2xl font-bold text-cover-black tracking-tight">{{ value }}</p>
            <p class="text-[10px] uppercase tracking-widest text-surface-400 mt-1 font-semibold">{{ label }}</p>
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-4">
          <p v-if="status.last_ingestion" class="text-[12px] text-surface-400">Last ingestion: {{ formatDate(status.last_ingestion) }}</p>
          <button
            type="button"
            @click="showIngestionConfirm = true"
            class="px-5 py-2 bg-cover-black text-white text-[11px] font-semibold uppercase tracking-widest rounded-md hover:bg-cover-charcoal transition-colors disabled:opacity-40"
            :disabled="ingestionTriggering"
          >
            {{ ingestionTriggering ? 'Running…' : 'Trigger Re-ingestion' }}
          </button>
        </div>

        <!-- Confirmation modal -->
        <div v-if="showIngestionConfirm" class="fixed inset-0 z-50 flex items-center justify-center bg-cover-black/50" @click.self="showIngestionConfirm = false">
          <div class="bg-white rounded-xl shadow-xl p-6 max-w-md w-full mx-4">
            <h3 class="text-[15px] font-semibold text-cover-black mb-2">Trigger Re-ingestion?</h3>
            <p class="text-[13px] text-surface-400 mb-6">This will re-run the full ingestion pipeline. It may take several minutes.</p>
            <div class="flex gap-3 justify-end">
              <button type="button" @click="showIngestionConfirm = false" class="px-4 py-2 text-[12px] font-medium text-surface-400 hover:text-cover-black">Cancel</button>
              <button type="button" @click="triggerIngestion" class="px-5 py-2 bg-cover-black text-white text-[11px] font-semibold uppercase tracking-widest rounded-md hover:bg-cover-charcoal disabled:opacity-40" :disabled="ingestionTriggering">
                {{ ingestionTriggering ? 'Running…' : 'Confirm' }}
              </button>
            </div>
          </div>
        </div>

        <div v-if="ingestionResult" class="bg-white rounded-lg border border-surface-200 p-4 space-y-2">
          <p class="text-[13px] font-medium text-cover-black">Ingestion {{ ingestionResult.status === 'complete' ? 'completed' : ingestionResult.status }}.</p>
          <div class="grid grid-cols-2 sm:grid-cols-3 gap-2 text-[12px]">
            <div v-for="(val, key) in ingestionResult.stats" :key="key" class="flex justify-between gap-2">
              <span class="text-surface-400">{{ key.replace(/_/g, ' ') }}:</span>
              <span class="font-medium text-cover-black">{{ val }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Zone Rules -->
      <div v-else-if="activeTab === 'rules'" class="space-y-4">
        <div class="flex items-center gap-4">
          <label class="text-[11px] font-semibold uppercase tracking-widest text-surface-400">Zone class</label>
          <select
            v-model="zoneClassFilter"
            @change="loadRules"
            class="rounded-md border border-surface-200 bg-white px-3 py-2 text-[13px] text-cover-black focus:outline-none focus:border-surface-400"
          >
            <option v-for="opt in ZONE_CLASS_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </select>
        </div>

        <div class="bg-white rounded-lg border border-surface-200 overflow-hidden">
          <table class="w-full text-[13px]">
            <thead class="bg-surface-50 border-b border-surface-200">
              <tr>
                <th class="text-left px-4 py-2.5 text-[9px] font-bold uppercase tracking-widest text-surface-400">Zone</th>
                <th class="text-left px-4 py-2.5 text-[9px] font-bold uppercase tracking-widest text-surface-400">Parameter</th>
                <th class="text-left px-4 py-2.5 text-[9px] font-bold uppercase tracking-widest text-surface-400">Value</th>
                <th class="text-left px-4 py-2.5 text-[9px] font-bold uppercase tracking-widest text-surface-400">Section</th>
                <th class="text-left px-4 py-2.5 text-[9px] font-bold uppercase tracking-widest text-surface-400">Verified</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-surface-100">
              <tr
                v-for="rule in filteredRules"
                :key="rule.id"
                :class="['hover:bg-surface-50 transition-colors', rule.is_verified ? 'bg-cover-green-dim' : '']"
              >
                <td class="px-4 py-2.5 font-medium text-cover-black">{{ rule.zone_class }}</td>
                <td class="px-4 py-2.5 text-surface-500">{{ rule.parameter }}</td>
                <td class="px-4 py-2.5 text-cover-black">{{ rule.base_value }} {{ rule.unit }}</td>
                <td class="px-4 py-2.5 text-surface-400">{{ rule.section_number }}</td>
                <td class="px-4 py-2.5">
                  <button
                    type="button"
                    @click="toggleRuleVerified(rule)"
                    :disabled="ruleUpdating.has(rule.id)"
                    :class="[
                      'inline-flex items-center justify-center w-7 h-7 rounded border transition-colors text-[12px]',
                      rule.is_verified
                        ? 'bg-cover-green-dim border-cover-green/30 text-cover-green hover:bg-cover-green/20'
                        : 'bg-surface-50 border-surface-200 text-surface-300 hover:border-surface-400 hover:text-surface-500',
                    ]"
                  >
                    <span v-if="ruleUpdating.has(rule.id)">…</span>
                    <span v-else>{{ rule.is_verified ? '✓' : '○' }}</span>
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Feedback Review -->
      <div v-else-if="activeTab === 'feedback'" class="bg-white rounded-lg border border-surface-200 overflow-hidden">
        <div v-if="feedbackLoading" class="text-center py-12 text-surface-400 text-[13px]">Loading feedback…</div>
        <div v-else-if="feedback.length === 0" class="text-center py-12 text-surface-400 text-[13px]">No feedback yet.</div>
        <table v-else class="w-full text-[13px]">
          <thead class="bg-surface-50 border-b border-surface-200">
            <tr>
              <th class="text-left px-4 py-2.5 text-[9px] font-bold uppercase tracking-widest text-surface-400">Date</th>
              <th class="text-left px-4 py-2.5 text-[9px] font-bold uppercase tracking-widest text-surface-400">Assessment ID</th>
              <th class="text-left px-4 py-2.5 text-[9px] font-bold uppercase tracking-widest text-surface-400">Constraint</th>
              <th class="text-left px-4 py-2.5 text-[9px] font-bold uppercase tracking-widest text-surface-400">Rating</th>
              <th class="text-left px-4 py-2.5 text-[9px] font-bold uppercase tracking-widest text-surface-400">Comment</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-surface-100">
            <tr v-for="fb in feedback" :key="fb.id" class="hover:bg-surface-50">
              <td class="px-4 py-2.5 text-surface-500">{{ formatDate(fb.created_at) }}</td>
              <td class="px-4 py-2.5 font-mono text-[11px] text-surface-500">{{ truncateId(fb.assessment_id) }}</td>
              <td class="px-4 py-2.5 font-mono text-[11px] text-surface-400">{{ fb.constraint_id ? truncateId(fb.constraint_id) : '—' }}</td>
              <td class="px-4 py-2.5">
                <span :class="fb.rating === 'positive' ? 'text-cover-green' : 'text-cover-red'">{{ fb.rating === 'positive' ? '👍' : '👎' }}</span>
              </td>
              <td class="px-4 py-2.5 text-surface-500 max-w-xs truncate" :title="fb.comment || ''">{{ fb.comment || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
