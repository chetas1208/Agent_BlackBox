<template>
  <div class="w-full">
    <div class="flex items-center justify-between mb-1">
      <span v-if="label" class="text-xs text-surface-500">{{ label }}</span>
      <span class="text-xs font-mono text-surface-400">{{ value }}%</span>
    </div>
    <div class="h-1.5 bg-surface-800 rounded-full overflow-hidden">
      <div
        :class="['h-full rounded-full transition-all duration-500 ease-out', barColor]"
        :style="{ width: `${value}%` }"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  value: number
  label?: string
}>()

const barColor = computed(() => {
  if (props.value >= 80) return 'bg-emerald-500'
  if (props.value >= 40) return 'bg-accent-500'
  return 'bg-amber-500'
})
</script>
