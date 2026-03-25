<script setup lang="ts">
import { toRef } from 'vue'
import type { Assessment } from '@/types'
import { CATEGORY_LABELS, CATEGORY_ICONS } from '@/types'
import { useAssessmentDiff } from '@/composables/useAssessmentDiff'

const props = defineProps<{
  leftAssessment: Assessment
  rightAssessment: Assessment
}>()

const left = toRef(() => props.leftAssessment)
const right = toRef(() => props.rightAssessment)

const { groupedDiffs, diffStats } = useAssessmentDiff(left, right)

function formatValue(c: { value: string | null; numeric_value: number | null; unit: string | null } | null): string {
  if (!c) return '—'
  if (c.value) return c.value
  if (c.numeric_value != null) return `${c.numeric_value} ${c.unit || ''}`
  return '—'
}

function formatParam(param: string): string {
  return param
    .replace(/_/g, ' ')
    .replace(/\b\w/g, l => l.toUpperCase())
}
</script>

<template>
  <div class="divide-y divide-surface-200/50">
    <!-- Header -->
    <div class="px-6 py-4 bg-surface-50">
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-[14px] font-semibold text-cover-black tracking-tight">
          {{ leftAssessment.parcel.address || leftAssessment.parcel.apn }}
        </h2>
        <div class="text-[11px] text-surface-400">
          <span class="font-medium text-cover-black">{{ diffStats.different + diffStats.leftOnly + diffStats.rightOnly }}</span>
          differences
        </div>
      </div>

      <!-- Column headers -->
      <div class="grid grid-cols-[1fr_1fr_1fr] gap-2 text-[10px] font-bold uppercase tracking-widest text-surface-400">
        <div>Constraint</div>
        <div class="text-center px-2 py-1 bg-cover-black/5 rounded">
          {{ leftAssessment.building_type }}
        </div>
        <div class="text-center px-2 py-1 bg-cover-black/5 rounded">
          {{ rightAssessment.building_type }}
        </div>
      </div>
    </div>

    <!-- Diff groups -->
    <div v-for="[category, diffs] in groupedDiffs" :key="category" class="px-6 py-4">
      <h3 class="text-[9px] font-bold uppercase tracking-widest-plus text-surface-400 mb-2.5 flex items-center gap-1.5">
        <span>{{ CATEGORY_ICONS[category] || '•' }}</span>
        {{ CATEGORY_LABELS[category] || category }}
        <span class="text-surface-300 font-normal">({{ diffs.length }})</span>
      </h3>

      <div class="space-y-1.5">
        <div
          v-for="diff in diffs"
          :key="diff.parameter"
          :class="[
            'grid grid-cols-[1fr_1fr_1fr] gap-2 items-center px-3 py-2 rounded-lg text-[12px]',
            diff.isDifferent ? 'bg-amber-50/60 border border-amber-200/40' : 'bg-surface-50/50'
          ]"
        >
          <!-- Parameter name -->
          <div class="text-surface-500 font-medium truncate" :title="diff.parameter">
            {{ formatParam(diff.parameter) }}
          </div>

          <!-- Left value -->
          <div :class="[
            'text-center font-medium',
            !diff.left ? 'text-surface-300 italic' :
            diff.isDifferent ? 'text-cover-black' : 'text-surface-500'
          ]">
            {{ formatValue(diff.left) }}
          </div>

          <!-- Right value -->
          <div :class="[
            'text-center font-medium',
            !diff.right ? 'text-surface-300 italic' :
            diff.isDifferent ? 'text-cover-black' : 'text-surface-500'
          ]">
            {{ formatValue(diff.right) }}
          </div>
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-if="groupedDiffs.length === 0" class="px-6 py-8 text-center">
      <p class="text-[13px] text-surface-400">No constraints to compare.</p>
    </div>
  </div>
</template>
