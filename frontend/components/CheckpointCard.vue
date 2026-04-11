<template>
  <div class="card-sm p-3 flex items-center gap-3">
    <div class="flex-shrink-0 w-9 h-9 rounded-xl bg-accent-600/20 border border-accent-500/30 flex items-center justify-center">
      <span class="text-sm">💾</span>
    </div>
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2">
        <span class="text-sm font-medium text-surface-200 truncate">
          {{ checkpoint.label || 'Checkpoint' }}
        </span>
        <span :class="['badge border text-[10px]', safetyClass]">
          {{ checkpoint.safety_status }}
        </span>
      </div>
      <div class="text-xs text-surface-500 mt-0.5">
        Event #{{ checkpoint.event_index }}
        · Risk {{ (checkpoint.risk_score_at * 100).toFixed(0) }}%
        · {{ formatTimestamp(checkpoint.created_at) }}
      </div>
    </div>
    <button
      v-if="showRestore"
      class="flex-shrink-0 px-2.5 py-1 text-xs font-medium text-accent-400 bg-accent-600/10 border border-accent-500/20 rounded-lg hover:bg-accent-600/20 transition-colors"
      @click="$emit('restore', checkpoint.id)"
    >
      Restore
    </button>
  </div>
</template>

<script setup lang="ts">
import type { Checkpoint } from '~/types'
import { formatTimestamp } from '~/utils/format'

const props = defineProps<{
  checkpoint: Checkpoint
  showRestore?: boolean
}>()

defineEmits<{
  restore: [id: string]
}>()

const safetyClass = computed(() => {
  if (props.checkpoint.safety_status === 'clean') return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
  return 'bg-amber-500/20 text-amber-400 border-amber-500/30'
})
</script>
