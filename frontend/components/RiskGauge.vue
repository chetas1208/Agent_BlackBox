<template>
  <div class="flex flex-col items-center gap-1">
    <div class="relative w-16 h-16">
      <svg viewBox="0 0 36 36" class="w-16 h-16 -rotate-90">
        <circle
          cx="18" cy="18" r="15.9"
          fill="none"
          :stroke="trackColor"
          stroke-width="2.5"
        />
        <circle
          cx="18" cy="18" r="15.9"
          fill="none"
          :stroke="fillColor"
          stroke-width="2.5"
          stroke-linecap="round"
          :stroke-dasharray="`${value * 100}, 100`"
          class="transition-all duration-700 ease-out"
        />
      </svg>
      <div class="absolute inset-0 flex items-center justify-center">
        <span :class="['text-sm font-bold', textColor]">
          {{ Math.round(value * 100) }}
        </span>
      </div>
    </div>
    <span class="text-xs text-surface-500 font-medium">{{ label }}</span>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  value: number
  label: string
  invert?: boolean
}>()

const fillColor = computed(() => {
  const v = props.invert ? 1 - props.value : props.value
  if (v > 0.7) return '#10b981'
  if (v > 0.4) return '#f59e0b'
  return '#ef4444'
})

const textColor = computed(() => {
  const v = props.invert ? 1 - props.value : props.value
  if (v > 0.7) return 'text-emerald-400'
  if (v > 0.4) return 'text-amber-400'
  return 'text-red-400'
})

const trackColor = '#1e293b'
</script>
