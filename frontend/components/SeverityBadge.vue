<template>
  <span :class="['badge border', colorClass]">
    {{ severity }}
  </span>
</template>

<script setup lang="ts">
import type { EventSeverity } from '~/types'

const props = defineProps<{ severity: EventSeverity }>()

const map: Record<EventSeverity, string> = {
  debug: 'bg-surface-700/50 text-surface-400 border-surface-600/50',
  info: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  warning: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  error: 'bg-red-500/20 text-red-400 border-red-500/30',
  critical: 'bg-red-600/30 text-red-300 border-red-500/40',
}

const colorClass = computed(() => map[props.severity] || map.info)
</script>
