<script setup lang="ts">
import { ref } from 'vue'
import type { Constraint } from '@/types'
import { api } from '@/services/api'

const props = defineProps<{
  constraint: Constraint
  assessmentId: string
}>()

const expanded = ref(false)
const feedbackSent = ref(false)

const badgeClass = {
  deterministic_lookup: 'badge-deterministic',
  computed: 'badge-computed',
  llm_interpreted: 'badge-interpreted',
}

const badgeLabel = {
  deterministic_lookup: 'Verified',
  computed: 'Computed',
  llm_interpreted: 'Interpreted',
}

async function sendFeedback(rating: 'positive' | 'negative') {
  try {
    await api.feedback.submit({
      constraint_id: props.constraint.id,
      assessment_id: props.assessmentId,
      rating,
    })
    feedbackSent.value = true
  } catch {
    // silently fail
  }
}
</script>

<template>
  <div
    class="border border-surface-200 rounded-lg hover:border-surface-300 transition-colors"
    :class="{ 'border-l-4': true, 'border-l-green-400': constraint.confidence >= 0.9, 'border-l-amber-400': constraint.confidence >= 0.7 && constraint.confidence < 0.9, 'border-l-red-400': constraint.confidence < 0.7 }"
  >
    <button
      @click="expanded = !expanded"
      class="w-full text-left p-3 flex items-start justify-between gap-2"
    >
      <div class="flex-1 min-w-0">
        <p class="text-sm font-medium text-surface-800 leading-tight">
          {{ constraint.rule_text }}
        </p>
        <div class="flex items-center gap-2 mt-1.5">
          <span :class="badgeClass[constraint.source_layer] || 'badge-interpreted'" class="text-[10px]">
            {{ badgeLabel[constraint.source_layer] || constraint.source_layer }}
          </span>
          <span class="text-[10px] text-surface-400">
            {{ Math.round(constraint.confidence * 100) }}% confidence
          </span>
        </div>
      </div>
      <svg
        class="w-4 h-4 text-surface-400 transition-transform shrink-0 mt-0.5"
        :class="{ 'rotate-180': expanded }"
        viewBox="0 0 20 20" fill="currentColor"
      >
        <path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clip-rule="evenodd" />
      </svg>
    </button>

    <div v-if="expanded" class="px-3 pb-3 space-y-3 border-t border-surface-100 pt-3">
      <!-- Reasoning -->
      <div>
        <h4 class="text-[10px] font-semibold text-surface-500 uppercase tracking-wider mb-1">Reasoning</h4>
        <p class="text-xs text-surface-600 leading-relaxed">{{ constraint.reasoning }}</p>
      </div>

      <!-- Citations -->
      <div v-if="constraint.citations.length > 0">
        <h4 class="text-[10px] font-semibold text-surface-500 uppercase tracking-wider mb-1">Citations</h4>
        <div v-for="(citation, idx) in constraint.citations" :key="idx" class="bg-surface-50 rounded p-2 text-xs">
          <p class="font-medium text-surface-700">LAMC {{ citation.section_number }} — {{ citation.section_title }}</p>
          <p class="text-surface-500 mt-1 italic">"{{ citation.relevant_text }}"</p>
        </div>
      </div>

      <!-- Feedback -->
      <div class="flex items-center gap-2 pt-1">
        <span class="text-[10px] text-surface-400">Helpful?</span>
        <template v-if="!feedbackSent">
          <button @click="sendFeedback('positive')" class="text-surface-400 hover:text-green-600 transition-colors">
            <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path d="M1 8.998a1 1 0 011-1h3v10H2a1 1 0 01-1-1v-8zm5-1.307A3.78 3.78 0 019.913 5.5l.462-2.308A1.5 1.5 0 0111.84 2h.34a1.5 1.5 0 011.463 1.162l.1.5A4 4 0 0114 5.5H17a2 2 0 012 2v.5a2 2 0 01-.2.88l-2.6 5.2A2 2 0 0114.41 15H8a2 2 0 01-2-2V7.691z" /></svg>
          </button>
          <button @click="sendFeedback('negative')" class="text-surface-400 hover:text-red-600 transition-colors">
            <svg class="w-4 h-4 rotate-180" viewBox="0 0 20 20" fill="currentColor"><path d="M1 8.998a1 1 0 011-1h3v10H2a1 1 0 01-1-1v-8zm5-1.307A3.78 3.78 0 019.913 5.5l.462-2.308A1.5 1.5 0 0111.84 2h.34a1.5 1.5 0 011.463 1.162l.1.5A4 4 0 0114 5.5H17a2 2 0 012 2v.5a2 2 0 01-.2.88l-2.6 5.2A2 2 0 0114.41 15H8a2 2 0 01-2-2V7.691z" /></svg>
          </button>
        </template>
        <span v-else class="text-[10px] text-green-600">Thanks for the feedback!</span>
      </div>
    </div>
  </div>
</template>
