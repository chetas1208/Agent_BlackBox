<template>
  <span :class="['badge border', colorClass]">
    <span v-if="dot" :class="['w-1.5 h-1.5 rounded-full mr-1.5', dotColor]" />
    {{ label || status }}
  </span>
</template>

<script setup lang="ts">
import type { SessionStatus } from '~/types'

const props = defineProps<{
  status: SessionStatus | string
  label?: string
  dot?: boolean
}>()

const colorMap: Record<string, string> = {
  pending: 'bg-surface-700/50 text-surface-400 border-surface-600/50',
  running: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  paused: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  completed: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  failed: 'bg-red-500/20 text-red-400 border-red-500/30',
  recovered: 'bg-violet-500/20 text-violet-400 border-violet-500/30',
  cancelled: 'bg-surface-700/50 text-surface-500 border-surface-600/50',
}

const dotColorMap: Record<string, string> = {
  pending: 'bg-surface-500',
  running: 'bg-blue-400 animate-pulse',
  paused: 'bg-amber-400',
  completed: 'bg-emerald-400',
  failed: 'bg-red-400',
  recovered: 'bg-violet-400',
  cancelled: 'bg-surface-500',
}

const colorClass = computed(() => colorMap[props.status] || colorMap.pending)
const dotColor = computed(() => dotColorMap[props.status] || dotColorMap.pending)
</script>
