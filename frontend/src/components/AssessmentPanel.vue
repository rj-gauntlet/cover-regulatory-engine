<script setup lang="ts">
import { computed } from 'vue'
import type { Assessment, Constraint } from '@/types'
import { CATEGORY_LABELS, CATEGORY_ICONS } from '@/types'
import ConstraintCard from '@/components/ConstraintCard.vue'
import { api } from '@/services/api'

const props = defineProps<{
  assessment: Assessment
}>()

async function downloadGeojson() {
  try {
    const data = await api.geojson.export(props.assessment.id)
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/geo+json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `assessment-${props.assessment.id}.geojson`
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 200)
  } catch {
    console.warn('GeoJSON download failed')
  }
}

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
  if (c >= 0.9) return 'text-cover-green'
  if (c >= 0.7) return 'text-accent'
  return 'text-cover-red'
})
</script>

<template>
  <div class="divide-y divide-surface-200/50">
    <!-- Header -->
    <div class="px-6 py-4 bg-surface-50">
      <div class="flex items-start justify-between">
        <div>
          <h2 class="text-[14px] font-semibold text-cover-black tracking-tight">
            {{ assessment.parcel.address || assessment.parcel.apn }}
          </h2>
          <p class="text-[11px] text-surface-400 mt-1">
            Zone: <span class="font-semibold text-surface-500">{{ assessment.parcel.zone_code }}</span>
            <span v-if="assessment.parcel.lot_area_sqft" class="ml-3">
              Lot: <span class="font-semibold text-surface-500">{{ assessment.parcel.lot_area_sqft.toLocaleString() }} sqft</span>
            </span>
          </p>
        </div>
        <div class="text-right">
          <div :class="['text-[22px] font-bold tracking-tight', confidenceColor]">
            {{ Math.round(assessment.overall_confidence * 100) }}%
          </div>
          <div class="text-[9px] font-semibold uppercase tracking-widest text-surface-400">Confidence</div>
        </div>
      </div>

      <div class="flex items-center gap-2 mt-3">
        <span class="badge-deterministic">
          {{ deterministicCount }} deterministic
        </span>
        <span v-if="interpretedCount > 0" class="badge-interpreted">
          {{ interpretedCount }} interpreted
        </span>
        <span class="text-[11px] text-surface-400">
          {{ assessment.building_type }}
        </span>
        <button
          @click="downloadGeojson"
          class="ml-auto flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-medium text-surface-400 hover:text-cover-black border border-surface-200 hover:border-surface-400 rounded transition-colors"
          title="Download assessment as GeoJSON"
        >
          <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          GeoJSON
        </button>
      </div>
    </div>

    <!-- Constraint groups -->
    <div v-for="[category, constraints] in groupedConstraints" :key="category" class="px-6 py-4">
      <h3 class="text-[9px] font-bold uppercase tracking-widest-plus text-surface-400 mb-2.5 flex items-center gap-1.5">
        <span>{{ CATEGORY_ICONS[category] || '•' }}</span>
        {{ CATEGORY_LABELS[category] || category }}
        <span class="text-surface-300 font-normal">({{ constraints.length }})</span>
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
