<template>
  <div
    :class="[
      'relative pl-8 pb-6 group',
      isExpanded ? '' : 'cursor-pointer',
    ]"
    @click="toggle"
  >
    <!-- Timeline line -->
    <div class="absolute left-3 top-6 bottom-0 w-px bg-surface-800 group-last:hidden" />

    <!-- Timeline dot -->
    <div :class="['absolute left-1 top-1.5 w-5 h-5 rounded-full flex items-center justify-center text-[10px] border-2 z-10', dotClass]">
      {{ eventTypeIcon(event.event_type) }}
    </div>

    <!-- Content -->
    <div :class="['card-sm p-3 transition-all duration-200', borderClass, 'hover:border-surface-600']">
      <div class="flex items-start justify-between gap-2">
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-0.5">
            <span class="text-sm font-medium text-surface-200 truncate">
              {{ event.summary || event.event_type.replace(/_/g, ' ') }}
            </span>
            <SeverityBadge :severity="event.severity" />
          </div>
          <div class="flex items-center gap-2 text-xs text-surface-500">
            <span class="font-mono">{{ formatTimestamp(event.created_at) }}</span>
            <span>·</span>
            <span>{{ event.actor.replace(/_/g, ' ') }}</span>
            <span>·</span>
            <span class="font-mono text-surface-600">{{ event.event_type }}</span>
          </div>
        </div>
      </div>

      <!-- Expanded payload -->
      <div v-if="isExpanded && hasPayload" class="mt-3 pt-3 border-t border-surface-800">
        <pre class="text-xs font-mono text-surface-400 bg-surface-950 rounded-lg p-3 overflow-x-auto max-h-48">{{ JSON.stringify(event.payload, null, 2) }}</pre>
        <div v-if="event.related_memory_ids.length" class="mt-2 flex items-center gap-1.5">
          <span class="text-xs text-surface-500">Memory:</span>
          <span
            v-for="mid in event.related_memory_ids"
            :key="mid"
            class="badge badge-neutral text-[10px] font-mono"
          >
            {{ mid.slice(0, 8) }}
          </span>
        </div>
        <div v-if="event.checkpoint_id" class="mt-1 flex items-center gap-1.5">
          <span class="text-xs text-surface-500">Checkpoint:</span>
          <span class="badge badge-info text-[10px] font-mono">{{ event.checkpoint_id.slice(0, 8) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { AgentEvent } from '~/types'
import { formatTimestamp, eventTypeIcon } from '~/utils/format'

const props = defineProps<{ event: AgentEvent }>()

const isExpanded = ref(false)
const hasPayload = computed(() => Object.keys(props.event.payload).length > 0)

function toggle() {
  if (hasPayload.value) isExpanded.value = !isExpanded.value
}

const dotClass = computed(() => {
  const map: Record<string, string> = {
    debug: 'bg-surface-900 border-surface-600',
    info: 'bg-surface-900 border-blue-500/60',
    warning: 'bg-surface-900 border-amber-500/60',
    error: 'bg-surface-900 border-red-500/60',
    critical: 'bg-red-950 border-red-500',
  }
  return map[props.event.severity] || map.info
})

const borderClass = computed(() => {
  if (props.event.severity === 'critical') return 'border-red-500/30'
  if (props.event.severity === 'error') return 'border-red-500/20'
  if (props.event.severity === 'warning') return 'border-amber-500/20'
  return ''
})
</script>
