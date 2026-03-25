<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { Assessment, NearbyParcel } from '@/types'
import AddressSearch from '@/components/AddressSearch.vue'
import MapView from '@/components/MapView.vue'
import AssessmentPanel from '@/components/AssessmentPanel.vue'
import ComparisonPanel from '@/components/ComparisonPanel.vue'
import ChatPanel from '@/components/ChatPanel.vue'
import ProjectInputs from '@/components/ProjectInputs.vue'
import type { ProjectInputsModel } from '@/components/ProjectInputs.vue'
import { api, ParcelNotFoundError } from '@/services/api'
import { useToast } from '@/composables/useToast'

const route = useRoute()
const router = useRouter()
const toast = useToast()

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

// Compare mode
const compareMode = ref(false)
const compareType = ref('')
const compareAssessment = ref<Assessment | null>(null)
const compareLoading = ref(false)

async function enterCompareMode() {
  if (!assessment.value) return
  // Pick the first building type that isn't the current one
  const other = buildingTypes.find(bt => bt.value !== buildingType.value)
  if (!other) return
  compareType.value = other.value
  compareMode.value = true
  await fetchCompareAssessment()
}

async function fetchCompareAssessment() {
  if (!address.value || !compareType.value) return
  compareLoading.value = true
  try {
    compareAssessment.value = await api.assess.create({
      address: address.value,
      building_type: compareType.value,
      project_inputs: projectInputs.value,
    })
  } catch {
    toast.show('Failed to load comparison assessment', 'warning')
    compareMode.value = false
  } finally {
    compareLoading.value = false
  }
}

function exitCompareMode() {
  compareMode.value = false
  compareAssessment.value = null
}

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
    // Update URL with assessment ID for sharing
    if (assessment.value?.id) {
      router.replace({ name: 'assessment', params: { id: assessment.value.id } })
      const count = assessment.value.constraints.length
      toast.show(`Assessment complete — ${count} constraint${count !== 1 ? 's' : ''} found`, 'success')
    }
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

// Load assessment from URL if shared link
onMounted(async () => {
  const id = route.params.id as string
  if (id) {
    loading.value = true
    try {
      assessment.value = await api.assess.get(id)
      if (assessment.value?.parcel?.address) {
        address.value = assessment.value.parcel.address
      }
    } catch {
      error.value = 'Assessment not found or expired.'
    } finally {
      loading.value = false
    }
  }
})

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
      lat: assessment.value.parcel.centroid_lat || 33.9097,
      lng: assessment.value.parcel.centroid_lng || -118.2971,
    }
  }
  if (searchedLocation.value) {
    return searchedLocation.value
  }
  return { lat: 33.9097, lng: -118.2971 }
})
</script>

<template>
  <div class="h-full flex flex-col lg:flex-row relative">
    <!-- Left panel -->
    <div
      :class="[
        'flex flex-col border-r border-surface-200 bg-white shrink-0 transition-all duration-300 ease-in-out',
        panelCollapsed ? 'h-0 lg:h-auto lg:w-0 overflow-hidden border-r-0' : 'w-full lg:w-[460px] overflow-y-auto lg:overflow-hidden'
      ]"
    >
      <div class="flex flex-col min-h-full lg:h-full min-w-[320px] lg:min-w-[460px]">
        <!-- Search area -->
        <div class="px-6 py-5 border-b border-surface-200 space-y-3.5 shrink-0">
          <AddressSearch @search="handleSearch" :loading="loading" :model-value="address" />
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
            <template v-if="assessment && !compareMode">
              <span class="w-px h-5 bg-surface-200 mx-1"></span>
              <button
                @click="enterCompareMode"
                class="px-3.5 py-1.5 text-[11px] font-medium rounded-full border border-surface-200 text-surface-500 hover:border-surface-400 hover:text-cover-black transition-colors"
              >
                ↔ Compare
              </button>
            </template>
          </div>
          <ProjectInputs
            v-if="assessment"
            v-model="projectInputs"
            :building-type="buildingType"
          />
        </div>

        <!-- Content area -->
        <div class="flex-1 overflow-y-auto lg:overflow-hidden flex flex-col">
          <div v-if="!showChat" class="flex-1 lg:overflow-y-auto">
            <!-- Loading skeleton -->
            <div v-if="loading" class="divide-y divide-surface-200/50 animate-pulse">
              <div class="px-6 py-4 bg-surface-50">
                <div class="flex items-start justify-between">
                  <div class="space-y-2">
                    <div class="h-4 w-48 bg-surface-200 rounded"></div>
                    <div class="h-3 w-36 bg-surface-100 rounded"></div>
                  </div>
                  <div class="text-right space-y-1">
                    <div class="h-7 w-14 bg-surface-200 rounded ml-auto"></div>
                    <div class="h-2 w-16 bg-surface-100 rounded ml-auto"></div>
                  </div>
                </div>
                <div class="flex gap-2 mt-3">
                  <div class="h-5 w-28 bg-surface-100 rounded-full"></div>
                  <div class="h-5 w-20 bg-surface-100 rounded-full"></div>
                </div>
              </div>
              <div v-for="i in 4" :key="i" class="px-6 py-4 space-y-2.5">
                <div class="h-2.5 w-24 bg-surface-100 rounded"></div>
                <div class="h-16 bg-surface-100 rounded-lg"></div>
                <div class="h-16 bg-surface-50 rounded-lg"></div>
              </div>
            </div>

            <!-- Error -->
            <div v-else-if="error" class="p-6">
              <div class="bg-red-50 border border-red-200 rounded-lg p-4">
                <p class="text-[13px] text-cover-red">{{ error }}</p>
              </div>
            </div>

            <!-- Compare mode -->
            <template v-else-if="assessment && compareMode">
              <div class="px-6 py-3 bg-surface-50 border-b border-surface-200 flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <span class="text-[11px] font-semibold text-cover-black">Comparing:</span>
                  <select
                    v-model="compareType"
                    @change="fetchCompareAssessment()"
                    class="text-[11px] border border-surface-200 rounded px-2 py-1 bg-white text-cover-black focus:outline-none"
                  >
                    <option v-for="bt in buildingTypes.filter(b => b.value !== buildingType)" :key="bt.value" :value="bt.value">
                      {{ bt.label }}
                    </option>
                  </select>
                </div>
                <button
                  @click="exitCompareMode"
                  class="text-[11px] text-surface-400 hover:text-cover-black transition-colors"
                >
                  ← Back to single view
                </button>
              </div>
              <div v-if="compareLoading" class="p-8 text-center">
                <div class="inline-flex items-center gap-2.5 text-surface-400">
                  <svg class="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  <span class="text-[13px]">Loading comparison…</span>
                </div>
              </div>
              <ComparisonPanel
                v-else-if="compareAssessment"
                :left-assessment="assessment"
                :right-assessment="compareAssessment"
              />
            </template>

            <!-- Assessment -->
            <template v-else-if="assessment">
              <AssessmentPanel :assessment="assessment" :project-inputs="projectInputs" :building-type="buildingType" />
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
    <div :class="[
      'flex-1 transition-all duration-300',
      assessment && !panelCollapsed ? 'h-0 lg:h-auto overflow-hidden lg:overflow-visible' : 'min-h-[250px]'
    ]">
      <MapView :center="mapCenter" :assessment="assessment" :nearby-parcels="nearbyParcels" :searched-address="address" />
    </div>

    <!-- Mobile map toggle -->
    <button
      v-if="assessment && !showChat"
      @click="togglePanel"
      class="lg:hidden fixed bottom-4 right-4 z-30 bg-cover-black text-white text-[11px] font-semibold uppercase tracking-widest px-4 py-2.5 rounded-full shadow-lg"
    >
      {{ panelCollapsed ? 'Show Results' : 'Show Map' }}
    </button>
  </div>
</template>
