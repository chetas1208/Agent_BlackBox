<template>
  <div class="relative pl-8 pb-4 group">
    <!-- Timeline line -->
    <div class="absolute left-3 top-6 bottom-0 w-px bg-surface-800 group-last:hidden" />

    <!-- Timeline dot -->
    <div :class="['absolute left-1 top-1.5 w-5 h-5 rounded-full flex items-center justify-center text-[10px] border-2 z-10', dotClass]">
      {{ eventTypeIcon(event.event_type) }}
    </div>

    <!-- Card -->
    <div :class="['card-sm p-3 transition-all duration-200', borderClass]">
      <!-- Header row -->
      <div class="flex items-start justify-between gap-2">
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-0.5 flex-wrap">
            <span class="text-sm font-medium text-surface-200">
              {{ event.summary || event.event_type.replace(/_/g, ' ') }}
            </span>
            <SeverityBadge :severity="event.severity" />
            <span class="badge badge-neutral border text-[10px] font-mono text-surface-600">
              {{ event.event_type }}
            </span>
          </div>
          <div class="flex items-center gap-2 text-xs text-surface-500">
            <span class="font-mono">{{ formatTimestamp(event.created_at) }}</span>
            <span>·</span>
            <span>{{ event.actor.replace(/_/g, ' ') }}</span>
          </div>
        </div>

        <!-- Expand button — always visible -->
        <button
          :class="[
            'flex-shrink-0 w-6 h-6 rounded flex items-center justify-center text-xs transition-colors',
            isExpanded
              ? 'bg-accent-600/20 text-accent-400'
              : 'bg-surface-800 text-surface-500 hover:text-surface-300 hover:bg-surface-700',
          ]"
          :title="isExpanded ? 'Collapse' : 'Show details'"
          @click.stop="isExpanded = !isExpanded"
        >
          {{ isExpanded ? '▲' : '▼' }}
        </button>
      </div>

      <!-- Quick preview line for key events (always visible) -->
      <div v-if="!isExpanded && quickPreview" class="mt-1.5 text-xs font-mono text-surface-500 truncate bg-surface-900/50 rounded px-2 py-1">
        {{ quickPreview }}
      </div>

      <!-- Expanded detail -->
      <div v-if="isExpanded" class="mt-3 pt-3 border-t border-surface-800 space-y-3">

        <!-- Command highlight -->
        <div v-if="event.payload?.command" class="space-y-1">
          <div class="text-[10px] font-semibold text-surface-500 uppercase tracking-wider">Command</div>
          <pre class="text-xs font-mono text-emerald-400 bg-surface-950 rounded-lg p-2.5 overflow-x-auto whitespace-pre-wrap break-all">{{ event.payload.command }}</pre>
        </div>

        <!-- Stdout -->
        <div v-if="event.payload?.stdout" class="space-y-1">
          <div class="text-[10px] font-semibold text-surface-500 uppercase tracking-wider">stdout</div>
          <pre class="text-xs font-mono text-surface-300 bg-surface-950 rounded-lg p-2.5 overflow-x-auto max-h-48 whitespace-pre-wrap">{{ event.payload.stdout }}</pre>
        </div>

        <!-- Stderr -->
        <div v-if="event.payload?.stderr" class="space-y-1">
          <div class="text-[10px] font-semibold text-amber-600 uppercase tracking-wider text-[10px]">stderr</div>
          <pre class="text-xs font-mono text-amber-400 bg-surface-950 rounded-lg p-2.5 overflow-x-auto max-h-32 whitespace-pre-wrap">{{ event.payload.stderr }}</pre>
        </div>

        <!-- Exit code badge -->
        <div v-if="event.payload?.exit_code !== undefined" class="flex items-center gap-2">
          <span class="text-[10px] text-surface-500 uppercase tracking-wider">Exit code</span>
          <span :class="['badge border text-xs font-mono', event.payload.exit_code === 0 ? 'badge-success' : 'badge-error']">
            {{ event.payload.exit_code }}
          </span>
        </div>

        <!-- File path -->
        <div v-if="event.payload?.path" class="flex items-center gap-2">
          <span class="text-[10px] text-surface-500 uppercase tracking-wider">File</span>
          <code class="text-xs font-mono text-accent-400 bg-surface-800 px-2 py-0.5 rounded">{{ event.payload.path }}</code>
          <span v-if="event.payload?.size !== undefined" class="text-xs text-surface-600">{{ event.payload.size }} bytes</span>
        </div>

        <!-- Memory layer/key -->
        <div v-if="event.payload?.layer" class="flex items-center gap-2">
          <span class="text-[10px] text-surface-500 uppercase tracking-wider">Memory</span>
          <span class="badge badge-neutral border text-[10px]">{{ event.payload.layer }}</span>
          <code class="text-xs font-mono text-surface-400">{{ event.payload.key }}</code>
        </div>

        <!-- PR URL -->
        <div v-if="event.payload?.pr_url" class="space-y-1">
          <div class="text-[10px] font-semibold text-surface-500 uppercase tracking-wider">Pull Request</div>
          <a :href="event.payload.pr_url" target="_blank" class="text-sm text-accent-400 hover:text-accent-300 underline break-all">
            {{ event.payload.pr_url }}
          </a>
        </div>

        <!-- Generic payload fallback -->
        <div v-else-if="hasOtherPayload" class="space-y-1">
          <div class="text-[10px] font-semibold text-surface-500 uppercase tracking-wider">Details</div>
          <pre class="text-xs font-mono text-surface-400 bg-surface-950 rounded-lg p-2.5 overflow-x-auto max-h-48">{{ JSON.stringify(filteredPayload, null, 2) }}</pre>
        </div>

        <!-- Memory + checkpoint refs -->
        <div v-if="event.related_memory_ids?.length || event.checkpoint_id" class="flex items-center gap-2 flex-wrap pt-1 border-t border-surface-800/60">
          <template v-if="event.related_memory_ids?.length">
            <span class="text-[10px] text-surface-500">Mem:</span>
            <span v-for="mid in event.related_memory_ids" :key="mid" class="badge badge-neutral text-[10px] font-mono">
              {{ mid.slice(0, 8) }}
            </span>
          </template>
          <template v-if="event.checkpoint_id">
            <span class="text-[10px] text-surface-500">Checkpoint:</span>
            <span class="badge badge-info text-[10px] font-mono">{{ event.checkpoint_id.slice(0, 8) }}</span>
          </template>
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

const hasPayload = computed(() => Object.keys(props.event.payload || {}).length > 0)

// Keys that have dedicated UI above — exclude from fallback JSON
const HANDLED_KEYS = new Set(['command', 'stdout', 'stderr', 'exit_code', 'path', 'size', 'layer', 'key', 'pr_url'])

const filteredPayload = computed(() => {
  const p = props.event.payload || {}
  const out: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(p)) {
    if (!HANDLED_KEYS.has(k)) out[k] = v
  }
  return out
})

const hasOtherPayload = computed(() => Object.keys(filteredPayload.value).length > 0)

// One-line preview shown when collapsed (for command/file events)
const quickPreview = computed(() => {
  const p = props.event.payload || {}
  if (p.command) return `$ ${String(p.command).slice(0, 100)}`
  if (p.path) return `📄 ${p.path}`
  if (p.pr_url) return `🔗 ${p.pr_url}`
  if (p.layer && p.key) return `💾 ${p.layer} → ${p.key}`
  return ''
})

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
