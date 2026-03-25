<script setup lang="ts">
import { ref } from 'vue'
import type { Constraint, ComplianceResult } from '@/types'
import { api } from '@/services/api'

const props = defineProps<{
  constraint: Constraint
  assessmentId: string
  compliance?: ComplianceResult | null
}>()

const expanded = ref(false)
const feedbackSent = ref(false)
const submitting = ref(false)
const feedbackError = ref(false)

const badgeLabel: Record<string, string> = {
  deterministic_lookup: 'Verified',
  computed: 'Computed',
  llm_interpreted: 'Interpreted',
}

const badgeColor: Record<string, string> = {
  deterministic_lookup: 'text-cover-green',
  computed: 'text-accent',
  llm_interpreted: 'text-accent',
}

const barColor: Record<string, string> = {
  deterministic_lookup: 'bg-cover-green',
  computed: 'bg-accent',
  llm_interpreted: 'bg-accent',
}

const complianceBarColor: Record<string, string> = {
  pass: 'bg-cover-green',
  fail: 'bg-cover-red',
  warning: 'bg-amber-400',
}

const complianceBadge: Record<string, { label: string; color: string }> = {
  pass: { label: 'PASS', color: 'text-cover-green' },
  fail: { label: 'FAIL', color: 'text-cover-red' },
  warning: { label: '⚠', color: 'text-amber-500' },
}

async function sendFeedback(rating: 'positive' | 'negative') {
  if (submitting.value) return
  submitting.value = true
  feedbackError.value = false
  try {
    await api.feedback.submit({
      constraint_id: props.constraint.id,
      assessment_id: props.assessmentId,
      rating,
    })
    feedbackSent.value = true
  } catch (e) {
    console.warn('Feedback submission failed:', e)
    feedbackError.value = true
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="border border-surface-200 rounded-lg hover:border-surface-300 transition-colors overflow-hidden">
    <button
      @click="expanded = !expanded"
      class="w-full text-left px-4 py-3 flex items-start justify-between gap-2 relative"
    >
      <div
        :class="['absolute left-0 top-2.5 bottom-2.5 w-[3px] rounded-full',
          compliance?.status && compliance.status !== 'unknown'
            ? complianceBarColor[compliance.status]
            : barColor[constraint.source_layer] || 'bg-cover-green'
        ]"
      />
      <div class="flex-1 min-w-0 pl-2">
        <p class="text-[13px] font-medium text-cover-black leading-snug tracking-tight">
          {{ constraint.rule_text }}
        </p>
        <div class="flex items-center gap-2 mt-1">
          <span :class="['text-[9px] font-semibold uppercase tracking-wide', badgeColor[constraint.source_layer] || 'text-cover-green']">
            {{ badgeLabel[constraint.source_layer] || constraint.source_layer }}
          </span>
          <span class="text-[9px] text-surface-300">
            {{ Math.round(constraint.confidence * 100) }}% confidence
          </span>
          <span
            v-if="compliance?.status && compliance.status !== 'unknown'"
            :class="['text-[9px] font-bold uppercase tracking-wide', complianceBadge[compliance.status]?.color]"
          >
            {{ complianceBadge[compliance.status]?.label }}
          </span>
        </div>
      </div>
      <svg
        class="w-4 h-4 text-surface-300 transition-transform shrink-0 mt-0.5"
        :class="{ 'rotate-180': expanded }"
        viewBox="0 0 20 20" fill="currentColor"
      >
        <path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clip-rule="evenodd" />
      </svg>
    </button>

    <div v-if="expanded" class="px-4 pb-4 space-y-3 border-t border-surface-200 pt-3 pl-6">
      <div v-if="compliance?.message" :class="[
        'rounded-md px-3 py-2 text-[11px] font-medium',
        compliance.status === 'pass' ? 'bg-green-50 text-cover-green' :
        compliance.status === 'fail' ? 'bg-red-50 text-cover-red' :
        compliance.status === 'warning' ? 'bg-amber-50 text-amber-700' : ''
      ]">
        {{ compliance.message }}
      </div>
      <div>
        <h4 class="text-[9px] font-bold uppercase tracking-widest text-surface-400 mb-1">Reasoning</h4>
        <p class="text-[12px] text-surface-500 leading-relaxed">{{ constraint.reasoning }}</p>
      </div>

      <div v-if="constraint.citations?.length > 0">
        <h4 class="text-[9px] font-bold uppercase tracking-widest text-surface-400 mb-1">Citations</h4>
        <div v-for="(citation, idx) in constraint.citations" :key="idx" class="bg-surface-50 rounded-md p-3 text-[11px]">
          <p class="font-semibold text-surface-500">LAMC {{ citation.section_number }} — {{ citation.section_title }}</p>
          <p class="text-surface-400 mt-1 italic leading-relaxed">"{{ citation.relevant_text }}"</p>
        </div>
      </div>

      <div class="flex items-center gap-2 pt-1">
        <span class="text-[10px] text-surface-300">Helpful?</span>
        <template v-if="!feedbackSent && !feedbackError">
          <button @click="sendFeedback('positive')" :disabled="submitting" class="w-7 h-7 flex items-center justify-center border border-surface-200 rounded text-surface-300 hover:border-surface-400 hover:text-surface-500 transition-colors text-sm disabled:opacity-30 disabled:cursor-not-allowed">👍</button>
          <button @click="sendFeedback('negative')" :disabled="submitting" class="w-7 h-7 flex items-center justify-center border border-surface-200 rounded text-surface-300 hover:border-surface-400 hover:text-surface-500 transition-colors text-sm disabled:opacity-30 disabled:cursor-not-allowed">👎</button>
        </template>
        <span v-else-if="feedbackError" class="text-[10px] text-cover-red">Failed to submit</span>
        <span v-else class="text-[10px] text-cover-green">Thanks for the feedback!</span>
      </div>
    </div>
  </div>
</template>
