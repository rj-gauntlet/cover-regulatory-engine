<script setup lang="ts">
import { computed } from 'vue'
import type { Assessment, Constraint } from '@/types'
import { CATEGORY_LABELS, CATEGORY_ICONS } from '@/types'
import ConstraintCard from '@/components/ConstraintCard.vue'

const props = defineProps<{
  assessment: Assessment
}>()

const groupedConstraints = computed(() => {
  const groups: Record<string, Constraint[]> = {}
  for (const c of props.assessment.constraints) {
    const cat = c.category
    if (!groups[cat]) groups[cat] = []
    groups[cat].push(c)
  }
  const order = ['setback', 'height', 'far', 'density', 'lot', 'use', 'parking', 'adu', 'coverage', 'other']
  const sorted: [string, Constraint[]][] = []
  for (const cat of order) {
    if (groups[cat]) sorted.push([cat, groups[cat]])
  }
  for (const [cat, items] of Object.entries(groups)) {
    if (!order.includes(cat)) sorted.push([cat, items])
  }
  return sorted
})

const deterministicCount = computed(() =>
  props.assessment.constraints.filter(c => c.determination_type === 'deterministic').length
)

const interpretedCount = computed(() =>
  props.assessment.constraints.filter(c => c.determination_type !== 'deterministic').length
)

const confidenceColor = computed(() => {
  const c = props.assessment.overall_confidence
  if (c >= 0.9) return 'text-green-600'
  if (c >= 0.7) return 'text-amber-600'
  return 'text-red-600'
})
</script>

<template>
  <div class="divide-y divide-surface-100">
    <!-- Header -->
    <div class="p-4 bg-surface-50">
      <div class="flex items-start justify-between">
        <div>
          <h2 class="text-sm font-semibold text-surface-900">
            {{ assessment.parcel.address || assessment.parcel.apn }}
          </h2>
          <p class="text-xs text-surface-500 mt-0.5">
            Zone: <span class="font-medium text-surface-700">{{ assessment.parcel.zone_code }}</span>
            <span v-if="assessment.parcel.lot_area_sqft" class="ml-2">
              Lot: <span class="font-medium text-surface-700">{{ assessment.parcel.lot_area_sqft.toLocaleString() }} sqft</span>
            </span>
          </p>
        </div>
        <div class="text-right">
          <div :class="['text-lg font-bold', confidenceColor]">
            {{ Math.round(assessment.overall_confidence * 100) }}%
          </div>
          <div class="text-[10px] text-surface-500 uppercase tracking-wide">Confidence</div>
        </div>
      </div>

      <div class="flex gap-3 mt-3 text-xs">
        <span class="badge-deterministic">
          {{ deterministicCount }} deterministic
        </span>
        <span v-if="interpretedCount > 0" class="badge-interpreted">
          {{ interpretedCount }} interpreted
        </span>
        <span class="text-surface-400">
          {{ assessment.building_type }}
        </span>
      </div>
    </div>

    <!-- Constraint groups -->
    <div v-for="[category, constraints] in groupedConstraints" :key="category" class="p-4">
      <h3 class="text-xs font-semibold text-surface-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
        <span>{{ CATEGORY_ICONS[category] || '•' }}</span>
        {{ CATEGORY_LABELS[category] || category }}
        <span class="text-surface-400 font-normal">({{ constraints.length }})</span>
      </h3>
      <div class="space-y-2">
        <ConstraintCard
          v-for="constraint in constraints"
          :key="constraint.id"
          :constraint="constraint"
          :assessment-id="assessment.id"
        />
      </div>
    </div>
  </div>
</template>
