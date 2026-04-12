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

        <!-- Expand button -->
        <button
          class="flex-shrink-0 w-7 h-7 rounded-md flex items-center justify-center text-xs font-bold transition-all"
          :class="isExpanded
            ? 'bg-accent-600 text-white shadow-lg shadow-accent-600/20'
            : 'bg-surface-800 text-surface-400 hover:text-white hover:bg-surface-700'"
          :title="isExpanded ? 'Collapse' : 'Show details'"
          @click.stop="isExpanded = !isExpanded"
        >
          {{ isExpanded ? '−' : '+' }}
        </button>
      </div>

      <!-- Quick preview (always visible when collapsed) -->
      <div v-if="!isExpanded && quickPreview" class="mt-1.5 text-xs font-mono text-surface-500 truncate bg-surface-900/50 rounded px-2 py-1">
        {{ quickPreview }}
      </div>

      <!-- ═══════════ EXPANDED DETAIL ═══════════ -->
      <div v-if="isExpanded" class="mt-3 pt-3 border-t border-surface-800 space-y-3">

        <!-- Command (tool_invoked with command) -->
        <div v-if="p.command" class="space-y-1">
          <div class="detail-label">Command</div>
          <pre class="detail-code text-emerald-400">$ {{ p.command }}</pre>
        </div>

        <!-- Directory (list_files) -->
        <div v-if="p.directory" class="flex items-center gap-2">
          <span class="detail-label">Directory</span>
          <code class="detail-inline">{{ p.directory }}</code>
        </div>

        <!-- Tool name -->
        <div v-if="p.tool" class="flex items-center gap-2">
          <span class="detail-label">Tool</span>
          <span class="badge badge-neutral border text-[10px]">{{ p.tool }}</span>
        </div>

        <!-- Exit code -->
        <div v-if="p.exit_code !== undefined" class="flex items-center gap-2">
          <span class="detail-label">Exit Code</span>
          <span :class="['badge border text-xs font-mono font-bold', p.exit_code === 0 ? 'badge-success' : 'badge-error']">
            {{ p.exit_code }}
          </span>
        </div>

        <!-- stdout (handles both "stdout" and "output" keys) -->
        <div v-if="stdoutText" class="space-y-1">
          <div class="detail-label">Output</div>
          <pre class="detail-code text-surface-300 max-h-60">{{ stdoutText }}</pre>
        </div>

        <!-- stderr -->
        <div v-if="p.stderr" class="space-y-1">
          <div class="detail-label text-amber-500">Stderr</div>
          <pre class="detail-code text-amber-400 max-h-40">{{ p.stderr }}</pre>
        </div>

        <!-- Files listing -->
        <div v-if="p.files" class="space-y-1">
          <div class="detail-label">Files Found</div>
          <pre class="detail-code text-surface-300 max-h-60">{{ p.files }}</pre>
        </div>

        <!-- File path + size (read/write result) -->
        <div v-if="p.path" class="flex items-center gap-3">
          <span class="detail-label">File</span>
          <code class="detail-inline">{{ p.path }}</code>
          <span v-if="p.size !== undefined" class="text-xs text-surface-600">{{ p.size }} bytes</span>
          <span v-if="p.bytes !== undefined" class="text-xs text-surface-600">{{ p.bytes }} bytes written</span>
        </div>

        <!-- Memory layer/key -->
        <div v-if="p.layer" class="flex items-center gap-2">
          <span class="detail-label">Memory</span>
          <span :class="['badge border text-[10px]', memoryLayerClass(p.layer)]">{{ p.layer }}</span>
          <code class="text-xs font-mono text-surface-400">{{ p.key }}</code>
        </div>

        <!-- Checkpoint ID -->
        <div v-if="p.checkpoint_id" class="flex items-center gap-2">
          <span class="detail-label">Checkpoint</span>
          <code class="detail-inline">{{ p.checkpoint_id.slice(0, 12) }}...</code>
        </div>

        <!-- Goal -->
        <div v-if="p.goal" class="space-y-1">
          <div class="detail-label">Goal</div>
          <p class="text-sm text-surface-300 bg-surface-900/50 rounded-lg p-2.5">{{ p.goal }}</p>
        </div>

        <!-- Outcome -->
        <div v-if="p.outcome" class="space-y-1">
          <div class="detail-label">Outcome</div>
          <p class="text-sm text-green-400 bg-green-900/10 border border-green-700/30 rounded-lg p-2.5">{{ p.outcome }}</p>
        </div>

        <!-- PR URL -->
        <div v-if="p.pr_url" class="space-y-1">
          <div class="detail-label">Pull Request</div>
          <a :href="p.pr_url" target="_blank" class="text-sm text-accent-400 hover:text-accent-300 underline break-all">
            {{ p.pr_url }}
          </a>
        </div>

        <!-- Report path -->
        <div v-if="p.report_size" class="flex items-center gap-2">
          <span class="detail-label">Report</span>
          <code class="detail-inline">{{ p.path || 'AGENT_REPORT.md' }}</code>
          <span class="text-xs text-surface-600">{{ p.report_size }} chars</span>
        </div>

        <!-- Compressed steps -->
        <div v-if="p.compressed_steps" class="flex items-center gap-2">
          <span class="detail-label">Context Compressed</span>
          <span class="text-xs text-surface-400">{{ p.compressed_steps }} older steps summarized</span>
        </div>

        <!-- Blocked command -->
        <div v-if="p.blocked" class="space-y-1">
          <div class="detail-label text-red-400">Blocked by Guardrail</div>
          <pre class="detail-code text-red-400">{{ p.command }}</pre>
        </div>

        <!-- Detector type (safety alert) -->
        <div v-if="p.detector" class="flex items-center gap-2">
          <span class="detail-label">Safety Detector</span>
          <span class="badge badge-error border text-[10px]">{{ p.detector }}</span>
        </div>

        <!-- Generic fallback: show any remaining keys as JSON -->
        <div v-if="remainingPayload && Object.keys(remainingPayload).length > 0" class="space-y-1">
          <div class="detail-label">Raw Data</div>
          <pre class="detail-code text-surface-400 max-h-40">{{ JSON.stringify(remainingPayload, null, 2) }}</pre>
        </div>

        <!-- Memory refs / Checkpoint refs -->
        <div v-if="event.related_memory_ids?.length || event.checkpoint_id" class="flex items-center gap-2 flex-wrap pt-2 border-t border-surface-800/60">
          <template v-if="event.related_memory_ids?.length">
            <span class="text-[10px] text-surface-500">Linked Memory:</span>
            <span v-for="mid in event.related_memory_ids" :key="mid" class="badge badge-neutral text-[10px] font-mono">
              {{ mid.slice(0, 8) }}
            </span>
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

const p = computed(() => props.event.payload || {})

// Merge "stdout" and "output" into one field
const stdoutText = computed(() => {
  return p.value.stdout || p.value.output || ''
})

// Keys that have dedicated UI sections above
const HANDLED_KEYS = new Set([
  'command', 'tool', 'directory', 'exit_code', 'stdout', 'stderr', 'output',
  'files', 'path', 'size', 'bytes', 'layer', 'key', 'checkpoint_id', 'goal',
  'outcome', 'pr_url', 'report_size', 'compressed_steps', 'blocked', 'detector',
])

const remainingPayload = computed(() => {
  const out: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(p.value)) {
    if (!HANDLED_KEYS.has(k)) out[k] = v
  }
  return out
})

// One-line preview when collapsed
const quickPreview = computed(() => {
  const v = p.value
  if (v.command) return `$ ${String(v.command).slice(0, 120)}`
  if (v.directory) return `📂 ${v.directory}`
  if (v.path) return `📄 ${v.path}${v.size !== undefined ? ` (${v.size} bytes)` : ''}`
  if (v.stdout || v.output) return `→ ${String(v.stdout || v.output).slice(0, 100)}`
  if (v.files) return `📁 ${String(v.files).split('\n').length} files found`
  if (v.layer && v.key) return `💾 ${v.layer} → ${v.key}`
  if (v.goal) return `🎯 ${String(v.goal).slice(0, 100)}`
  if (v.outcome) return `✅ ${String(v.outcome).slice(0, 100)}`
  if (v.checkpoint_id) return `💾 Checkpoint: ${v.checkpoint_id.slice(0, 12)}`
  if (v.pr_url) return `🔗 ${v.pr_url}`
  return ''
})

function memoryLayerClass(layer: string): string {
  if (layer.includes('working')) return 'bg-blue-500/20 text-blue-400 border-blue-500/30'
  if (layer.includes('episodic')) return 'bg-purple-500/20 text-purple-400 border-purple-500/30'
  if (layer.includes('semantic')) return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
  if (layer.includes('risk')) return 'bg-red-500/20 text-red-400 border-red-500/30'
  return 'bg-surface-800 text-surface-400 border-surface-700'
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

<style scoped>
.detail-label {
  @apply text-[10px] font-semibold text-surface-500 uppercase tracking-wider;
}
.detail-code {
  @apply text-xs font-mono bg-surface-950 rounded-lg p-2.5 overflow-x-auto whitespace-pre-wrap break-words;
}
.detail-inline {
  @apply text-xs font-mono text-accent-400 bg-surface-800 px-2 py-0.5 rounded;
}
</style>
