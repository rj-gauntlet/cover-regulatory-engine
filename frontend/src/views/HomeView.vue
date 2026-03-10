<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Assessment } from '@/types'
import AddressSearch from '@/components/AddressSearch.vue'
import MapView from '@/components/MapView.vue'
import AssessmentPanel from '@/components/AssessmentPanel.vue'
import { api } from '@/services/api'

const assessment = ref<Assessment | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const buildingType = ref('SFH')

const buildingTypes = [
  { value: 'SFH', label: 'Single Family Home' },
  { value: 'ADU', label: 'ADU' },
  { value: 'Guest House', label: 'Guest House' },
]

async function handleSearch(address: string) {
  loading.value = true
  error.value = null
  assessment.value = null

  try {
    assessment.value = await api.assess.create({
      address,
      building_type: buildingType.value,
    })
  } catch (e: any) {
    error.value = e.message || 'Assessment failed. Please try another address.'
  } finally {
    loading.value = false
  }
}

async function handleBuildingTypeChange(type: string) {
  buildingType.value = type
  if (assessment.value?.parcel?.address) {
    await handleSearch(assessment.value.parcel.address)
  }
}

const mapCenter = computed(() => {
  if (assessment.value?.parcel) {
    return {
      lat: assessment.value.parcel.centroid_lat || 34.0522,
      lng: assessment.value.parcel.centroid_lng || -118.2437,
    }
  }
  return { lat: 34.0522, lng: -118.2437 }
})
</script>

<template>
  <div class="h-full flex flex-col lg:flex-row">
    <!-- Left panel: Search + Assessment -->
    <div class="w-full lg:w-[440px] xl:w-[480px] flex flex-col border-r border-surface-200 bg-white overflow-hidden shrink-0">
      <!-- Search -->
      <div class="p-4 border-b border-surface-200 space-y-3">
        <AddressSearch @search="handleSearch" :loading="loading" />
        <div class="flex gap-2">
          <button
            v-for="bt in buildingTypes"
            :key="bt.value"
            @click="handleBuildingTypeChange(bt.value)"
            :class="[
              'px-3 py-1.5 text-xs font-medium rounded-full transition-colors',
              buildingType === bt.value
                ? 'bg-primary-600 text-white'
                : 'bg-surface-100 text-surface-600 hover:bg-surface-200'
            ]"
          >
            {{ bt.label }}
          </button>
        </div>
      </div>

      <!-- Loading / Error / Results -->
      <div class="flex-1 overflow-y-auto">
        <div v-if="loading" class="p-8 text-center">
          <div class="inline-flex items-center gap-2 text-surface-500">
            <svg class="animate-spin h-5 w-5" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span class="text-sm">Analyzing parcel...</span>
          </div>
        </div>

        <div v-else-if="error" class="p-4">
          <div class="bg-red-50 border border-red-200 rounded-lg p-4">
            <p class="text-sm text-red-700">{{ error }}</p>
          </div>
        </div>

        <AssessmentPanel v-else-if="assessment" :assessment="assessment" />

        <div v-else class="p-8 text-center">
          <div class="text-surface-400 space-y-2">
            <p class="text-4xl">🏠</p>
            <p class="text-sm font-medium">Enter an LA residential address</p>
            <p class="text-xs text-surface-400">Get a structured buildability assessment with cited regulations</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Right panel: Map -->
    <div class="flex-1 min-h-[300px]">
      <MapView
        :center="mapCenter"
        :assessment="assessment"
      />
    </div>
  </div>
</template>
