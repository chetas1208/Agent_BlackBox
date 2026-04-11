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
  ready: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  unconfigured: 'bg-surface-700/50 text-surface-400 border-surface-600/50',
  bootstrapping: 'bg-sky-500/20 text-sky-400 border-sky-500/30',
  planning: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
  executing: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  summarizing: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  recovering: 'bg-violet-500/20 text-violet-400 border-violet-500/30',
  done: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  idle: 'bg-surface-700/50 text-surface-400 border-surface-600/50',
}

const dotColorMap: Record<string, string> = {
  pending: 'bg-surface-500',
  running: 'bg-blue-400 animate-pulse',
  paused: 'bg-amber-400',
  completed: 'bg-emerald-400',
  failed: 'bg-red-400',
  recovered: 'bg-violet-400',
  cancelled: 'bg-surface-500',
  ready: 'bg-emerald-400',
  unconfigured: 'bg-surface-500',
  bootstrapping: 'bg-sky-400 animate-pulse',
  planning: 'bg-indigo-400 animate-pulse',
  executing: 'bg-blue-400 animate-pulse',
  summarizing: 'bg-cyan-400 animate-pulse',
  recovering: 'bg-violet-400 animate-pulse',
  done: 'bg-emerald-400',
  idle: 'bg-surface-500',
}

const colorClass = computed(() => colorMap[props.status] || colorMap.pending)
const dotColor = computed(() => dotColorMap[props.status] || dotColorMap.pending)
</script>
