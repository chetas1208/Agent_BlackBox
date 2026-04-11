<template>
  <div :class="['card-sm p-4', isQuarantined ? 'border-red-500/30 bg-red-950/20' : '']">
    <div class="flex items-start justify-between gap-2 mb-2">
      <div class="flex items-center gap-2">
        <span :class="['badge border text-xs', layerColor]">
          {{ memoryLayerLabel(item.layer) }}
        </span>
        <span :class="['badge border text-xs', statusBadge]">
          {{ item.status }}
        </span>
      </div>
      <span class="text-xs font-mono text-surface-600">{{ item.id.slice(0, 8) }}</span>
    </div>

    <h4 class="text-sm font-semibold text-surface-200 mb-1 font-mono">{{ item.key }}</h4>

    <div class="text-xs text-surface-400 mb-3 line-clamp-2">
      {{ typeof item.value === 'string' ? item.value : JSON.stringify(item.value) }}
    </div>

    <div class="grid grid-cols-3 gap-2 text-xs mb-3">
      <div>
        <span class="text-surface-600 block">Confidence</span>
        <span :class="item.confidence > 0.7 ? 'text-emerald-400' : item.confidence > 0.4 ? 'text-amber-400' : 'text-red-400'">
          {{ (item.confidence * 100).toFixed(0) }}%
        </span>
      </div>
      <div>
        <span class="text-surface-600 block">Contradiction</span>
        <span :class="item.contradiction_score > 0.5 ? 'text-red-400' : 'text-surface-400'">
          {{ (item.contradiction_score * 100).toFixed(0) }}%
        </span>
      </div>
      <div>
        <span class="text-surface-600 block">Importance</span>
        <span class="text-surface-300">{{ (item.importance_score * 100).toFixed(0) }}%</span>
      </div>
    </div>

    <div v-if="item.tags.length" class="flex flex-wrap gap-1 mb-2">
      <span v-for="tag in item.tags" :key="tag" class="badge badge-neutral text-[10px]">
        {{ tag }}
      </span>
    </div>

    <div class="text-[10px] text-surface-600 font-mono">
      {{ formatDateTime(item.updated_at) }}
      <span v-if="item.source"> · {{ item.source }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { MemoryItem } from '~/types'
import { memoryLayerLabel, memoryLayerColor, formatDateTime } from '~/utils/format'

const props = defineProps<{ item: MemoryItem }>()

const isQuarantined = computed(() => props.item.status === 'quarantined')

const layerColor = computed(() => memoryLayerColor(props.item.layer))

const statusMap: Record<string, string> = {
  active: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  stale: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  quarantined: 'bg-red-500/20 text-red-400 border-red-500/30',
  archived: 'bg-surface-700/50 text-surface-500 border-surface-600/50',
}
const statusBadge = computed(() => statusMap[props.item.status] || '')
</script>
