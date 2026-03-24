<script setup lang="ts">
import { ref, onMounted, watch, nextTick, onUnmounted } from 'vue'
import mapboxgl from 'mapbox-gl'
import type { Assessment, Constraint } from '@/types'

const props = defineProps<{
  center: { lat: number; lng: number }
  assessment: Assessment | null
}>()

const emit = defineEmits<{
  'constraint-click': [constraint: Constraint]
}>()

const mapContainer = ref<HTMLElement | null>(null)
const showLegend = ref(true)
const hoveredFeature = ref<{ parameter: string; value: string; category: string } | null>(null)
const tooltipPos = ref({ x: 0, y: 0 })
let map: mapboxgl.Map | null = null
let popup: mapboxgl.Popup | null = null

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || ''

const SETBACK_COLORS: Record<string, string> = {
  front: '#c45c5c',
  rear: '#c8956e',
  side: '#c8b46e',
}

const LEGEND_ITEMS = [
  { color: '#1a1a1a', label: 'Parcel Boundary', type: 'line' },
  { color: '#6b7b8d', label: 'Buildings', type: 'fill' },
  { color: '#c45c5c', label: 'Front Setback', type: 'fill' },
  { color: '#c8956e', label: 'Rear Setback', type: 'fill' },
  { color: '#c8b46e', label: 'Side Setback', type: 'fill' },
  { color: '#4a9e6e', label: 'Buildable Area', type: 'fill' },
]

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
  map.addControl(new mapboxgl.ScaleControl({ unit: 'imperial' }), 'bottom-right')

  map.on('mousemove', handleMouseMove)
  map.on('click', handleMapClick)
})

onUnmounted(() => {
  if (map) {
    map.off('mousemove', handleMouseMove)
    map.off('click', handleMapClick)
    map.remove()
    map = null
  }
})

function handleMouseMove(e: mapboxgl.MapMouseEvent) {
  if (!map) return
  const layers = ['setback-front', 'setback-rear', 'setback-side', 'buildable-fill', 'parcel-fill']
  const existing = layers.filter(l => map!.getLayer(l))
  if (existing.length === 0) { hoveredFeature.value = null; return }

  const features = map.queryRenderedFeatures(e.point, { layers: existing })
  if (features.length > 0) {
    const f = features[0]
    hoveredFeature.value = {
      parameter: f.properties?.type || f.properties?.label || f.layer.id,
      value: f.properties?.label || f.properties?.value || '',
      category: f.properties?.category || f.layer.id.replace('setback-', '') + ' setback',
    }
    tooltipPos.value = { x: e.point.x, y: e.point.y }
    map.getCanvas().style.cursor = 'pointer'
  } else {
    hoveredFeature.value = null
    map.getCanvas().style.cursor = ''
  }
}

function escapeHtml(str: string): string {
  const div = document.createElement('div')
  div.textContent = str
  return div.innerHTML
}

function handleMapClick(e: mapboxgl.MapMouseEvent) {
  if (!map || !props.assessment) return
  const layers = ['setback-front', 'setback-rear', 'setback-side', 'buildable-fill']
  const existing = layers.filter(l => map!.getLayer(l))
  if (existing.length === 0) return

  const features = map.queryRenderedFeatures(e.point, { layers: existing })
  if (features.length > 0) {
    const f = features[0]
    const parameter = f.properties?.type || ''
    const title = escapeHtml(f.properties?.type?.replace(/_/g, ' ') || 'Zone feature')
    const detail = escapeHtml(f.properties?.label || f.properties?.value || '')
    const html = `<div style="font-family:Inter,sans-serif;font-size:13px;"><div style="font-weight:600;color:#0a0a0a;">${title}</div><div style="color:#7a7a7a;margin-top:2px;">${detail}</div></div>`
    if (popup) popup.remove()
    popup = new mapboxgl.Popup({ closeButton: true, maxWidth: '200px' })
      .setLngLat(e.lngLat)
      .setHTML(html)
      .addTo(map)

    const constraint = props.assessment.constraints.find(c => c.parameter === parameter)
    if (constraint) emit('constraint-click', constraint)
  }
}

watch(() => props.center, (newCenter) => {
  if (map) map.flyTo({ center: [newCenter.lng, newCenter.lat], zoom: 18, duration: 1500 })
})

watch(() => props.assessment, async (assessment) => {
  if (!map) return
  await nextTick()
  clearLayers()
  if (!assessment?.parcel) return
  if (map.isStyleLoaded()) addParcelLayers(assessment)
  else map.once('style.load', () => addParcelLayers(assessment))
}, { deep: true })

function clearLayers() {
  if (!map) return
  const layerIds = ['parcel-fill', 'parcel-outline', 'buildable-fill', 'buildable-outline', 'setback-front', 'setback-rear', 'setback-side', 'setback-labels', 'buildings-fill', 'buildings-outline']
  const sourceIds = ['parcel', 'buildable', 'setbacks', 'setback-labels', 'buildings']
  for (const id of layerIds) { if (map.getLayer(id)) map.removeLayer(id) }
  for (const id of sourceIds) { if (map.getSource(id)) map.removeSource(id) }
}

function addParcelLayers(assessment: Assessment) {
  if (!map || !assessment.parcel) return
  const parcel = assessment.parcel

  if (parcel.geometry_geojson) {
    map.addSource('parcel', {
      type: 'geojson',
      data: { type: 'Feature', properties: {}, geometry: parcel.geometry_geojson },
    })
    map.addLayer({
      id: 'parcel-fill',
      type: 'fill',
      source: 'parcel',
      paint: { 'fill-color': '#0a0a0a', 'fill-opacity': 0.03 },
    })
    map.addLayer({
      id: 'parcel-outline',
      type: 'line',
      source: 'parcel',
      paint: { 'line-color': '#1a1a1a', 'line-width': 2.5, 'line-dasharray': [2, 1] },
    })
  }

  const footprints = parcel.building_footprints_geojson
  if (footprints && Array.isArray(footprints) && footprints.length > 0) {
    map.addSource('buildings', {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: footprints },
    })
    map.addLayer({
      id: 'buildings-fill',
      type: 'fill',
      source: 'buildings',
      paint: { 'fill-color': '#6b7b8d', 'fill-opacity': 0.35 },
    })
    map.addLayer({
      id: 'buildings-outline',
      type: 'line',
      source: 'buildings',
      paint: { 'line-color': '#4a5568', 'line-width': 1 },
    })
  }

  const setbackConstraints = assessment.constraints.filter(c => c.category === 'setback' && c.geometry_geojson)
  if (setbackConstraints.length > 0) {
    const setbackFeatures = setbackConstraints.map(c => ({
      type: 'Feature' as const,
      properties: { type: c.parameter, label: c.value, category: c.category, value: `${c.value}` },
      geometry: c.geometry_geojson!,
    }))
    map.addSource('setbacks', {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: setbackFeatures },
    })
    for (const setbackType of ['front', 'rear', 'side']) {
      const color = SETBACK_COLORS[setbackType] || '#7a7a7a'
      map.addLayer({
        id: `setback-${setbackType}`,
        type: 'fill',
        source: 'setbacks',
        filter: ['==', ['get', 'type'], `${setbackType}_setback`],
        paint: { 'fill-color': color, 'fill-opacity': 0.18 },
      })
    }

    const labelFeatures = setbackConstraints.map(c => ({
      type: 'Feature' as const,
      properties: { label: c.value || '' },
      geometry: { type: 'Point' as const, coordinates: computeCentroid(c.geometry_geojson!) },
    }))
    map.addSource('setback-labels', {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: labelFeatures },
    })
    map.addLayer({
      id: 'setback-labels',
      type: 'symbol',
      source: 'setback-labels',
      layout: {
        'text-field': ['get', 'label'],
        'text-size': 11,
        'text-font': ['DIN Pro Medium', 'Arial Unicode MS Regular'],
        'text-allow-overlap': true,
      },
      paint: { 'text-color': '#2a2a2a', 'text-halo-color': '#ffffff', 'text-halo-width': 1.5 },
    })
  }

  const heightConstraint = assessment.constraints.find(c => c.category === 'height' && c.geometry_geojson)
  if (heightConstraint?.geometry_geojson) {
    map.addSource('buildable', {
      type: 'geojson',
      data: { type: 'Feature', properties: { label: 'Buildable Area' }, geometry: heightConstraint.geometry_geojson },
    })
    map.addLayer({
      id: 'buildable-fill',
      type: 'fill',
      source: 'buildable',
      paint: { 'fill-color': '#4a9e6e', 'fill-opacity': 0.08 },
    })
    map.addLayer({
      id: 'buildable-outline',
      type: 'line',
      source: 'buildable',
      paint: { 'line-color': '#4a9e6e', 'line-width': 1.5, 'line-dasharray': [3, 2] },
    })
  }

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
    } catch { /* fallback */ }
  }
}

function computeCentroid(geometry: any): [number, number] {
  const coords = extractCoords(geometry)
  if (coords.length === 0) return [0, 0]
  const sum = coords.reduce((acc, c) => [acc[0] + c[0], acc[1] + c[1]], [0, 0])
  return [sum[0] / coords.length, sum[1] / coords.length]
}

function extractCoords(geometry: any): number[][] {
  if (geometry.type === 'Polygon') return geometry.coordinates[0]
  if (geometry.type === 'MultiPolygon') return geometry.coordinates[0][0]
  return []
}
</script>

<template>
  <div class="relative w-full h-full">
    <div ref="mapContainer" class="w-full h-full">
      <div v-if="!MAPBOX_TOKEN" class="w-full h-full flex items-center justify-center bg-surface-100">
        <div class="text-center text-surface-400 p-8">
          <p class="text-lg font-medium">Map unavailable</p>
          <p class="text-[13px] mt-1">Set VITE_MAPBOX_TOKEN in your environment</p>
        </div>
      </div>
    </div>

    <!-- Hover tooltip -->
    <div
      v-if="hoveredFeature"
      class="absolute pointer-events-none z-20 bg-white/95 backdrop-blur-sm rounded-lg shadow-lg px-3 py-2 text-[11px] border border-surface-200"
      :style="{ left: tooltipPos.x + 12 + 'px', top: tooltipPos.y - 20 + 'px' }"
    >
      <div class="font-semibold text-cover-black">{{ hoveredFeature.parameter.replace(/_/g, ' ') }}</div>
      <div v-if="hoveredFeature.value" class="text-surface-400">{{ hoveredFeature.value }}</div>
    </div>

    <!-- Legend -->
    <div
      v-if="assessment && showLegend"
      class="absolute bottom-5 left-5 z-10 bg-white/95 backdrop-blur-sm rounded-lg shadow-lg border border-surface-200 p-4 min-w-[160px]"
    >
      <div class="flex items-center justify-between mb-2.5">
        <span class="text-[9px] font-bold uppercase tracking-widest text-surface-400">Legend</span>
        <button @click="showLegend = false" class="text-surface-300 hover:text-surface-500 transition-colors">
          <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      <div class="space-y-1.5">
        <div v-for="item in LEGEND_ITEMS" :key="item.label" class="flex items-center gap-2">
          <span
            v-if="item.type === 'fill'"
            class="w-3 h-3 rounded-sm"
            :style="{ backgroundColor: item.color + '30', border: '1px solid ' + item.color }"
          />
          <span v-else class="w-3 h-0 border-t-2 border-dashed" :style="{ borderColor: item.color }" />
          <span class="text-[11px] text-surface-500">{{ item.label }}</span>
        </div>
      </div>
    </div>

    <button
      v-if="assessment && !showLegend"
      @click="showLegend = true"
      class="absolute bottom-5 left-5 z-10 bg-white/95 backdrop-blur-sm rounded-lg shadow-lg border border-surface-200 px-3 py-2 text-[11px] font-medium text-surface-400 hover:text-cover-black transition-colors"
    >
      Show Legend
    </button>
  </div>
</template>
