<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import type { Assessment, NearbyParcel } from '@/types'
import AddressSearch from '@/components/AddressSearch.vue'
import MapView from '@/components/MapView.vue'
import AssessmentPanel from '@/components/AssessmentPanel.vue'
import ChatPanel from '@/components/ChatPanel.vue'
import ProjectInputs from '@/components/ProjectInputs.vue'
import type { ProjectInputsModel } from '@/components/ProjectInputs.vue'
import { api, ParcelNotFoundError } from '@/services/api'

const assessment = ref<Assessment | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const searchedLocation = ref<{ lat: number; lng: number } | null>(null)
const nearbyParcels = ref<NearbyParcel[]>([])
const buildingType = ref('SFH')
const showChat = ref(false)
const panelCollapsed = ref(false)
const address = ref('')
const projectInputs = ref<ProjectInputsModel>({
  stories: 1,
  bedrooms: 3,
  bathrooms: 2,
  sqft: null,
})

const buildingTypes = [
  { value: 'SFH', label: 'Single Family Home' },
  { value: 'ADU', label: 'ADU' },
  { value: 'Guest House', label: 'Guest House' },
]

async function handleSearch(searchAddress?: string) {
  const addr = searchAddress || address.value
  if (!addr) return
  address.value = addr

  loading.value = true
  error.value = null
  assessment.value = null
  searchedLocation.value = null
  nearbyParcels.value = []
  showChat.value = false
  panelCollapsed.value = false

  try {
    assessment.value = await api.assess.create({
      address: addr,
      building_type: buildingType.value,
      project_inputs: projectInputs.value,
    })
  } catch (e: any) {
    const notFound = e instanceof ParcelNotFoundError ? e : (e?.name === 'ParcelNotFoundError' ? e : null)
    if (notFound?.data?.geocoded_lat != null) {
      searchedLocation.value = { lat: notFound.data.geocoded_lat, lng: notFound.data.geocoded_lng }
      nearbyParcels.value = notFound.data.nearby_parcels || []
    }
    error.value = e.message || 'Assessment failed. Please try another address.'
  } finally {
    loading.value = false
  }
}

let projectInputsTimer: ReturnType<typeof setTimeout> | null = null
watch(projectInputs, () => {
  if (!assessment.value || !address.value) return
  if (projectInputsTimer) clearTimeout(projectInputsTimer)
  projectInputsTimer = setTimeout(() => handleSearch(), 500)
}, { deep: true })

onUnmounted(() => {
  if (projectInputsTimer) clearTimeout(projectInputsTimer)
})

async function handleBuildingTypeChange(type: string) {
  buildingType.value = type
  if (assessment.value?.parcel?.address) {
    await handleSearch(assessment.value.parcel.address)
  }
}

function togglePanel() {
  panelCollapsed.value = !panelCollapsed.value
  setTimeout(() => window.dispatchEvent(new Event('resize')), 350)
}

const mapCenter = computed(() => {
  if (assessment.value?.parcel) {
    return {
      lat: assessment.value.parcel.centroid_lat || 34.0522,
      lng: assessment.value.parcel.centroid_lng || -118.2437,
    }
  }
  if (searchedLocation.value) {
    return searchedLocation.value
  }
  return { lat: 34.0522, lng: -118.2437 }
})
</script>

<template>
  <div class="h-full flex flex-col lg:flex-row relative">
    <!-- Left panel -->
    <div
      :class="[
        'flex flex-col border-r border-surface-200 bg-white shrink-0 transition-all duration-300 ease-in-out',
        panelCollapsed ? 'w-0 overflow-hidden border-r-0' : 'w-full lg:w-[460px] overflow-hidden'
      ]"
    >
      <div class="flex flex-col h-full min-w-[460px]">
        <!-- Search area -->
        <div class="px-6 py-5 border-b border-surface-200 space-y-3.5 shrink-0">
          <AddressSearch @search="handleSearch" :loading="loading" />
          <div class="flex items-center gap-2 flex-wrap">
            <button
              v-for="bt in buildingTypes"
              :key="bt.value"
              @click="handleBuildingTypeChange(bt.value)"
              :class="[
                'px-3.5 py-1.5 text-[11px] font-medium rounded-full border transition-colors',
                buildingType === bt.value
                  ? 'bg-cover-black text-white border-cover-black'
                  : 'bg-transparent text-surface-500 border-surface-200 hover:border-surface-400 hover:text-cover-black'
              ]"
            >
              {{ bt.label }}
            </button>
          </div>
          <ProjectInputs
            v-if="assessment"
            v-model="projectInputs"
            :building-type="buildingType"
          />
        </div>

        <!-- Content area -->
        <div class="flex-1 overflow-hidden flex flex-col">
          <div v-if="!showChat" class="flex-1 overflow-y-auto">
            <!-- Loading -->
            <div v-if="loading" class="p-8 text-center">
              <div class="inline-flex items-center gap-2.5 text-surface-400">
                <svg class="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                <span class="text-[13px]">Analyzing parcel…</span>
              </div>
            </div>

            <!-- Error -->
            <div v-else-if="error" class="p-6">
              <div class="bg-red-50 border border-red-200 rounded-lg p-4">
                <p class="text-[13px] text-cover-red">{{ error }}</p>
              </div>
            </div>

            <!-- Assessment -->
            <template v-else-if="assessment">
              <AssessmentPanel :assessment="assessment" />
              <div class="px-6 py-4 border-t border-surface-200">
                <button
                  @click="showChat = true"
                  class="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-[12px] font-medium text-surface-500 bg-surface-50 hover:bg-surface-100 border border-surface-200 hover:border-surface-300 rounded-lg transition-colors"
                >
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
                  </svg>
                  Ask a follow-up question
                </button>
              </div>
            </template>

            <!-- Empty state -->
            <div v-else class="p-12 text-center">
              <div class="text-surface-300 space-y-3">
                <svg class="w-10 h-10 mx-auto text-surface-200" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25" />
                </svg>
                <p class="text-[13px] font-medium text-surface-400">Enter an LA residential address</p>
                <p class="text-[11px] text-surface-300">Get a structured buildability assessment with cited regulations</p>
              </div>
            </div>
          </div>

          <ChatPanel
            v-if="showChat && assessment"
            :assessment-id="assessment.id"
            :show="showChat"
            @close="showChat = false"
          />
        </div>
      </div>
    </div>

    <!-- Panel toggle -->
    <button
      @click="togglePanel"
      :title="panelCollapsed ? 'Show panel' : 'Hide panel'"
      :style="{ left: panelCollapsed ? '0px' : undefined }"
      :class="[
        'hidden lg:flex absolute top-1/2 -translate-y-1/2 z-30 w-5 h-10 items-center justify-center',
        'bg-white border border-surface-200 rounded-r-md shadow-sm',
        'hover:bg-surface-50 transition-all duration-300 cursor-pointer',
        panelCollapsed ? '' : 'lg:left-[460px]'
      ]"
    >
      <svg
        class="w-3 h-3 text-surface-400 transition-transform duration-300"
        :class="{ 'rotate-180': panelCollapsed }"
        viewBox="0 0 20 20" fill="currentColor"
      >
        <path fill-rule="evenodd" d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z" clip-rule="evenodd" />
      </svg>
    </button>

    <!-- Map -->
    <div class="flex-1 min-h-[300px]">
      <MapView :center="mapCenter" :assessment="assessment" :nearby-parcels="nearbyParcels" :searched-address="address" />
    </div>
  </div>
</template>
