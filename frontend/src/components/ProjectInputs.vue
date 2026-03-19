<script lang="ts">
export interface ProjectInputsModel {
  stories: number
  bedrooms: number
  bathrooms: number
  sqft: number | null
}
</script>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    modelValue: ProjectInputsModel
    buildingType: string
  }>(),
  {
    modelValue: () => ({
      stories: 1,
      bedrooms: 3,
      bathrooms: 2,
      sqft: null,
    }),
  }
)

const emit = defineEmits<{
  'update:modelValue': [value: ProjectInputsModel]
}>()

function update<K extends keyof ProjectInputsModel>(key: K, value: ProjectInputsModel[K]) {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

function stepStories(delta: number) {
  update('stories', clamp((props.modelValue.stories ?? 1) + delta, 1, 3))
}
function stepBedrooms(delta: number) {
  update('bedrooms', clamp((props.modelValue.bedrooms ?? 3) + delta, 0, 6))
}
function stepBathrooms(delta: number) {
  update('bathrooms', clamp((props.modelValue.bathrooms ?? 2) + delta, 0, 4))
}
function onSqftChange(e: Event) {
  const raw = (e.target as HTMLInputElement).value
  const parsed = raw === '' ? null : parseInt(raw, 10)
  update('sqft', parsed === null || isNaN(parsed) || parsed < 0 ? null : parsed)
}
</script>

<template>
  <div class="grid grid-cols-2 gap-x-4 gap-y-3">
    <div class="space-y-1">
      <label class="block text-[10px] font-semibold uppercase tracking-widest text-surface-400">Stories</label>
      <div class="flex items-center gap-1">
        <button type="button" @click="stepStories(-1)" :disabled="(modelValue.stories ?? 1) <= 1"
          class="flex h-7 w-7 shrink-0 items-center justify-center rounded border border-surface-200 bg-surface-50 text-surface-500 hover:bg-surface-100 disabled:opacity-30 disabled:cursor-not-allowed text-sm">−</button>
        <input type="number" :value="modelValue.stories ?? 1"
          @input="update('stories', clamp(parseInt(($event.target as HTMLInputElement).value, 10) || 1, 1, 3))"
          min="1" max="3" class="w-10 text-center text-[13px] border border-surface-200 rounded px-1 py-1 bg-white text-cover-black focus:outline-none focus:border-surface-400" />
        <button type="button" @click="stepStories(1)" :disabled="(modelValue.stories ?? 1) >= 3"
          class="flex h-7 w-7 shrink-0 items-center justify-center rounded border border-surface-200 bg-surface-50 text-surface-500 hover:bg-surface-100 disabled:opacity-30 disabled:cursor-not-allowed text-sm">+</button>
      </div>
    </div>

    <div class="space-y-1">
      <label class="block text-[10px] font-semibold uppercase tracking-widest text-surface-400">Bedrooms</label>
      <div class="flex items-center gap-1">
        <button type="button" @click="stepBedrooms(-1)" :disabled="(modelValue.bedrooms ?? 3) <= 0"
          class="flex h-7 w-7 shrink-0 items-center justify-center rounded border border-surface-200 bg-surface-50 text-surface-500 hover:bg-surface-100 disabled:opacity-30 disabled:cursor-not-allowed text-sm">−</button>
        <input type="number" :value="modelValue.bedrooms ?? 3"
          @input="update('bedrooms', clamp(parseInt(($event.target as HTMLInputElement).value, 10) || 0, 0, 6))"
          min="0" max="6" class="w-10 text-center text-[13px] border border-surface-200 rounded px-1 py-1 bg-white text-cover-black focus:outline-none focus:border-surface-400" />
        <button type="button" @click="stepBedrooms(1)" :disabled="(modelValue.bedrooms ?? 3) >= 6"
          class="flex h-7 w-7 shrink-0 items-center justify-center rounded border border-surface-200 bg-surface-50 text-surface-500 hover:bg-surface-100 disabled:opacity-30 disabled:cursor-not-allowed text-sm">+</button>
      </div>
    </div>

    <div class="space-y-1">
      <label class="block text-[10px] font-semibold uppercase tracking-widest text-surface-400">Bathrooms</label>
      <div class="flex items-center gap-1">
        <button type="button" @click="stepBathrooms(-1)" :disabled="(modelValue.bathrooms ?? 2) <= 0"
          class="flex h-7 w-7 shrink-0 items-center justify-center rounded border border-surface-200 bg-surface-50 text-surface-500 hover:bg-surface-100 disabled:opacity-30 disabled:cursor-not-allowed text-sm">−</button>
        <input type="number" :value="modelValue.bathrooms ?? 2"
          @input="update('bathrooms', clamp(parseInt(($event.target as HTMLInputElement).value, 10) || 0, 0, 4))"
          min="0" max="4" class="w-10 text-center text-[13px] border border-surface-200 rounded px-1 py-1 bg-white text-cover-black focus:outline-none focus:border-surface-400" />
        <button type="button" @click="stepBathrooms(1)" :disabled="(modelValue.bathrooms ?? 2) >= 4"
          class="flex h-7 w-7 shrink-0 items-center justify-center rounded border border-surface-200 bg-surface-50 text-surface-500 hover:bg-surface-100 disabled:opacity-30 disabled:cursor-not-allowed text-sm">+</button>
      </div>
    </div>

    <div class="space-y-1">
      <label class="block text-[10px] font-semibold uppercase tracking-widest text-surface-400">Proposed Sqft</label>
      <input type="number" :value="modelValue.sqft ?? ''" @input="onSqftChange" placeholder="e.g. 1500" min="0"
        class="w-full text-[13px] border border-surface-200 rounded px-3 py-1.5 bg-white text-cover-black placeholder:text-surface-300 focus:outline-none focus:border-surface-400" />
    </div>
  </div>
</template>
