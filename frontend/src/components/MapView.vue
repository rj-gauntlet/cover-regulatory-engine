<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue'
import mapboxgl from 'mapbox-gl'
import type { Assessment } from '@/types'

const props = defineProps<{
  center: { lat: number; lng: number }
  assessment: Assessment | null
}>()

const mapContainer = ref<HTMLElement | null>(null)
let map: mapboxgl.Map | null = null

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || ''

const SETBACK_COLORS: Record<string, string> = {
  front: '#ef4444',
  rear: '#f97316',
  side: '#eab308',
}

onMounted(() => {
  if (!mapContainer.value || !MAPBOX_TOKEN) return

  mapboxgl.accessToken = MAPBOX_TOKEN

  map = new mapboxgl.Map({
    container: mapContainer.value,
    style: 'mapbox://styles/mapbox/light-v11',
    center: [props.center.lng, props.center.lat],
    zoom: 17,
  })

  map.addControl(new mapboxgl.NavigationControl(), 'top-right')
})

watch(() => props.center, (newCenter) => {
  if (map) {
    map.flyTo({ center: [newCenter.lng, newCenter.lat], zoom: 18, duration: 1500 })
  }
})

watch(() => props.assessment, async (assessment) => {
  if (!map) return
  await nextTick()

  clearLayers()

  if (!assessment?.parcel) return

  if (map.isStyleLoaded()) {
    addParcelLayers(assessment)
  } else {
    map.once('style.load', () => addParcelLayers(assessment))
  }
}, { deep: true })

function clearLayers() {
  if (!map) return
  const layerIds = ['parcel-fill', 'parcel-outline', 'buildable-fill', 'buildable-outline',
                    'setback-front', 'setback-rear', 'setback-side', 'buildings-fill']
  const sourceIds = ['parcel', 'buildable', 'setbacks', 'buildings']

  for (const id of layerIds) {
    if (map.getLayer(id)) map.removeLayer(id)
  }
  for (const id of sourceIds) {
    if (map.getSource(id)) map.removeSource(id)
  }
}

function addParcelLayers(assessment: Assessment) {
  if (!map || !assessment.parcel) return
  const parcel = assessment.parcel

  // Parcel boundary
  if (parcel.geometry_geojson) {
    map.addSource('parcel', {
      type: 'geojson',
      data: { type: 'Feature', properties: {}, geometry: parcel.geometry_geojson },
    })

    map.addLayer({
      id: 'parcel-fill',
      type: 'fill',
      source: 'parcel',
      paint: {
        'fill-color': '#3b82f6',
        'fill-opacity': 0.08,
      },
    })

    map.addLayer({
      id: 'parcel-outline',
      type: 'line',
      source: 'parcel',
      paint: {
        'line-color': '#2563eb',
        'line-width': 2.5,
        'line-dasharray': [2, 1],
      },
    })
  }

  // Setback areas
  const setbackConstraints = assessment.constraints.filter(
    c => c.category === 'setback' && c.geometry_geojson
  )

  if (setbackConstraints.length > 0) {
    const features = setbackConstraints.map(c => ({
      type: 'Feature' as const,
      properties: {
        type: c.parameter,
        label: c.value,
      },
      geometry: c.geometry_geojson!,
    }))

    map.addSource('setbacks', {
      type: 'geojson',
      data: { type: 'FeatureCollection', features },
    })

    for (const setbackType of ['front', 'rear', 'side']) {
      const color = SETBACK_COLORS[setbackType] || '#94a3b8'
      map.addLayer({
        id: `setback-${setbackType}`,
        type: 'fill',
        source: 'setbacks',
        filter: ['==', ['get', 'type'], `${setbackType}_setback`],
        paint: {
          'fill-color': color,
          'fill-opacity': 0.2,
        },
      })
    }
  }

  // Fit map to parcel bounds
  if (parcel.geometry_geojson) {
    try {
      const coords = extractCoords(parcel.geometry_geojson)
      if (coords.length > 0) {
        const bounds = coords.reduce(
          (b, c) => b.extend(c as [number, number]),
          new mapboxgl.LngLatBounds(coords[0] as [number, number], coords[0] as [number, number])
        )
        map.fitBounds(bounds, { padding: 80, duration: 1500 })
      }
    } catch (e) {
      // fallback to center
    }
  }
}

function extractCoords(geometry: any): number[][] {
  if (geometry.type === 'Polygon') {
    return geometry.coordinates[0]
  } else if (geometry.type === 'MultiPolygon') {
    return geometry.coordinates[0][0]
  }
  return []
}
</script>

<template>
  <div ref="mapContainer" class="w-full h-full">
    <div v-if="!MAPBOX_TOKEN" class="w-full h-full flex items-center justify-center bg-surface-100">
      <div class="text-center text-surface-500 p-8">
        <p class="text-lg font-medium">Map unavailable</p>
        <p class="text-sm mt-1">Set VITE_MAPBOX_TOKEN in your environment</p>
      </div>
    </div>
  </div>
</template>
