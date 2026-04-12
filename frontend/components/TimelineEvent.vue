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
      <!-- Header row — clicking the whole header toggles expand -->
      <div class="flex items-start justify-between gap-2 cursor-pointer select-none" @click="isExpanded = !isExpanded">
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
        <div
          :class="[
            'flex-shrink-0 w-7 h-7 rounded-md flex items-center justify-center text-xs font-bold transition-all',
            isExpanded
              ? 'bg-accent-600 text-white'
              : 'bg-surface-800 text-surface-400 hover:text-white hover:bg-surface-700',
          ]"
        >
          {{ isExpanded ? '−' : '+' }}
        </div>
      </div>

      <!-- Quick preview (always visible when collapsed) -->
      <div v-if="!isExpanded && quickPreview" class="mt-1.5 text-xs font-mono text-surface-500 truncate bg-surface-900/50 rounded px-2 py-1">
        {{ quickPreview }}
      </div>

      <!-- ═══════════ EXPANDED DETAIL ═══════════ -->
      <div v-if="isExpanded" class="mt-3 pt-3 border-t border-surface-800 space-y-3">

        <!-- What Happened summary -->
        <div class="bg-surface-900/80 border border-surface-700/50 rounded-lg p-3">
          <div class="text-[10px] font-semibold text-accent-400 uppercase tracking-wider mb-1">What Happened</div>
          <p class="text-sm text-surface-300">{{ explainEvent }}</p>
        </div>

        <!-- Command (tool_invoked with command) -->
        <div v-if="p.command" class="space-y-1">
          <div class="text-[10px] font-semibold text-surface-500 uppercase tracking-wider">Command</div>
          <pre class="text-xs font-mono text-emerald-400 bg-surface-950 rounded-lg p-2.5 overflow-x-auto whitespace-pre-wrap break-all">$ {{ p.command }}</pre>
        </div>

        <!-- Directory (list_files) -->
        <div v-if="p.directory" class="flex items-center gap-2">
          <span class="text-[10px] font-semibold text-surface-500 uppercase tracking-wider">Directory</span>
          <code class="text-xs font-mono text-accent-400 bg-surface-800 px-2 py-0.5 rounded">{{ p.directory }}</code>
        </div>

        <!-- Tool name -->
        <div v-if="p.tool" class="flex items-center gap-2">
          <span class="text-[10px] font-semibold text-surface-500 uppercase tracking-wider">Tool</span>
          <span class="badge badge-neutral border text-[10px]">{{ p.tool }}</span>
        </div>

        <!-- Exit code -->
        <div v-if="p.exit_code !== undefined" class="flex items-center gap-2">
          <span class="text-[10px] font-semibold text-surface-500 uppercase tracking-wider">Exit Code</span>
          <span :class="['badge border text-xs font-mono font-bold', p.exit_code === 0 ? 'badge-success' : 'badge-error']">
            {{ p.exit_code }}
          </span>
          <span v-if="p.exit_code === 0" class="text-xs text-green-400">Success</span>
          <span v-else class="text-xs text-red-400">Failed</span>
        </div>

        <!-- stdout / output -->
        <div v-if="stdoutText" class="space-y-1">
          <div class="text-[10px] font-semibold text-surface-500 uppercase tracking-wider">Output</div>
          <pre class="text-xs font-mono text-surface-300 bg-surface-950 rounded-lg p-2.5 overflow-x-auto whitespace-pre-wrap break-words max-h-60">{{ stdoutText }}</pre>
        </div>

        <!-- stderr -->
        <div v-if="p.stderr" class="space-y-1">
          <div class="text-[10px] font-semibold text-amber-500 uppercase tracking-wider">Stderr</div>
          <pre class="text-xs font-mono text-amber-400 bg-surface-950 rounded-lg p-2.5 overflow-x-auto whitespace-pre-wrap break-words max-h-40">{{ p.stderr }}</pre>
        </div>

        <!-- Files listing -->
        <div v-if="p.files" class="space-y-1">
          <div class="text-[10px] font-semibold text-surface-500 uppercase tracking-wider">Files Found</div>
          <pre class="text-xs font-mono text-surface-300 bg-surface-950 rounded-lg p-2.5 overflow-x-auto whitespace-pre-wrap max-h-60">{{ p.files }}</pre>
        </div>

        <!-- File path + size -->
        <div v-if="p.path" class="flex items-center gap-3 flex-wrap">
          <span class="text-[10px] font-semibold text-surface-500 uppercase tracking-wider">File</span>
          <code class="text-xs font-mono text-accent-400 bg-surface-800 px-2 py-0.5 rounded">{{ p.path }}</code>
          <span v-if="p.size !== undefined" class="text-xs text-surface-600">{{ p.size }} bytes</span>
          <span v-if="p.bytes !== undefined" class="text-xs text-surface-600">{{ p.bytes }} bytes written</span>
        </div>

        <!-- Memory layer/key -->
        <div v-if="p.layer" class="flex items-center gap-2">
          <span class="text-[10px] font-semibold text-surface-500 uppercase tracking-wider">Memory</span>
          <span :class="['badge border text-[10px]', memoryLayerClass(p.layer)]">{{ p.layer }}</span>
          <code class="text-xs font-mono text-surface-400">{{ p.key }}</code>
        </div>

        <!-- Checkpoint ID -->
        <div v-if="p.checkpoint_id" class="flex items-center gap-2">
          <span class="text-[10px] font-semibold text-surface-500 uppercase tracking-wider">Checkpoint</span>
          <code class="text-xs font-mono text-accent-400 bg-surface-800 px-2 py-0.5 rounded">{{ p.checkpoint_id.slice(0, 16) }}...</code>
        </div>

        <!-- Goal -->
        <div v-if="p.goal" class="space-y-1">
          <div class="text-[10px] font-semibold text-surface-500 uppercase tracking-wider">Goal</div>
          <p class="text-sm text-surface-300 bg-surface-900/50 rounded-lg p-2.5">{{ p.goal }}</p>
        </div>

        <!-- Outcome -->
        <div v-if="p.outcome" class="space-y-1">
          <div class="text-[10px] font-semibold text-surface-500 uppercase tracking-wider">Outcome</div>
          <p class="text-sm text-green-400 bg-green-900/10 border border-green-700/30 rounded-lg p-2.5">{{ p.outcome }}</p>
        </div>

        <!-- PR URL -->
        <div v-if="p.pr_url" class="space-y-1">
          <div class="text-[10px] font-semibold text-surface-500 uppercase tracking-wider">Pull Request</div>
          <a :href="p.pr_url" target="_blank" class="text-sm text-accent-400 hover:text-accent-300 underline break-all">{{ p.pr_url }}</a>
        </div>

        <!-- Report path -->
        <div v-if="p.report_size" class="flex items-center gap-2">
          <span class="text-[10px] font-semibold text-surface-500 uppercase tracking-wider">Report</span>
          <code class="text-xs font-mono text-accent-400 bg-surface-800 px-2 py-0.5 rounded">{{ p.path || 'AGENT_REPORT.md' }}</code>
          <span class="text-xs text-surface-600">{{ p.report_size }} chars</span>
        </div>

        <!-- Blocked command -->
        <div v-if="p.blocked" class="space-y-1">
          <div class="text-[10px] font-semibold text-red-400 uppercase tracking-wider">Blocked by Guardrail</div>
          <pre class="text-xs font-mono text-red-400 bg-red-950/30 border border-red-700/30 rounded-lg p-2.5">{{ p.command }}</pre>
        </div>

        <!-- Detector type -->
        <div v-if="p.detector" class="flex items-center gap-2">
          <span class="text-[10px] font-semibold text-surface-500 uppercase tracking-wider">Safety Detector</span>
          <span class="badge badge-error border text-[10px]">{{ p.detector }}</span>
        </div>

        <!-- Context compression -->
        <div v-if="p.compressed_steps" class="flex items-center gap-2">
          <span class="text-[10px] font-semibold text-surface-500 uppercase tracking-wider">Context Compressed</span>
          <span class="text-xs text-surface-400">{{ p.compressed_steps }} older steps summarized</span>
        </div>

        <!-- Generic fallback -->
        <div v-if="Object.keys(remainingPayload).length > 0" class="space-y-1">
          <div class="text-[10px] font-semibold text-surface-500 uppercase tracking-wider">Additional Data</div>
          <pre class="text-xs font-mono text-surface-400 bg-surface-950 rounded-lg p-2.5 overflow-x-auto whitespace-pre-wrap max-h-40">{{ JSON.stringify(remainingPayload, null, 2) }}</pre>
        </div>

        <!-- Memory refs -->
        <div v-if="event.related_memory_ids?.length" class="flex items-center gap-2 flex-wrap pt-2 border-t border-surface-800/60">
          <span class="text-[10px] text-surface-500">Linked Memory:</span>
          <span v-for="mid in event.related_memory_ids" :key="mid" class="badge badge-neutral text-[10px] font-mono">{{ mid.slice(0, 8) }}</span>
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

const stdoutText = computed(() => p.value.stdout || p.value.output || '')

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

const quickPreview = computed(() => {
  const v = p.value
  if (v.command) return `$ ${String(v.command).slice(0, 120)}`
  if (v.directory) return `dir: ${v.directory}`
  if (v.path) return `${v.path}${v.size !== undefined ? ` (${v.size} bytes)` : ''}`
  if (v.stdout || v.output) return String(v.stdout || v.output).split('\n')[0]?.slice(0, 100)
  if (v.files) return `${String(v.files).split('\n').length} files`
  if (v.layer && v.key) return `${v.layer} -> ${v.key}`
  if (v.goal) return String(v.goal).slice(0, 100)
  if (v.outcome) return String(v.outcome).slice(0, 100)
  if (v.checkpoint_id) return `checkpoint: ${v.checkpoint_id.slice(0, 12)}`
  if (v.pr_url) return v.pr_url
  return ''
})

// Human-readable explanation of what this event means
const explainEvent = computed(() => {
  const t = props.event.event_type
  const v = p.value
  const s = props.event.summary || ''

  if (t === 'session_created') return 'A new agent session was initialized. The runtime is preparing the sandbox environment.'
  if (t === 'agent_step' && s.includes('sandbox')) return 'The runtime is creating an isolated cloud sandbox (Blaxel) where the agent will execute code safely.'
  if (t === 'agent_step' && s.includes('Report')) return 'The agent wrote a comprehensive analysis report (AGENT_REPORT.md) summarizing everything it found and did.'
  if (t === 'agent_step' && s.includes('Context')) return `The agent compressed ${v.compressed_steps || 'older'} conversation steps into a summary to stay within GPT's token limit.`
  if (t === 'agent_step') return s || 'The agent performed an internal step.'

  if (t === 'tool_invoked' && v.command?.includes('git clone')) return `The agent is cloning the repository into /workspace inside the sandbox. This downloads all the code so the agent can work on it.`
  if (t === 'tool_invoked' && v.command?.includes('pip install')) return `The agent detected Python dependencies and is installing them. Command: ${v.command}`
  if (t === 'tool_invoked' && v.command?.includes('npm install')) return `The agent detected Node.js dependencies and is installing them.`
  if (t === 'tool_invoked' && v.command?.includes('pytest')) return `The agent is running the Python test suite to find failures.`
  if (t === 'tool_invoked' && v.command) return `The agent decided to run a shell command in the sandbox: ${v.command}`
  if (t === 'tool_invoked' && v.path && v.tool === 'sandbox_read') return `The agent is reading the file "${v.path}" to understand its contents and structure.`
  if (t === 'tool_invoked' && v.path && v.tool === 'sandbox_write') return `The agent is writing changes to "${v.path}".`
  if (t === 'tool_invoked' && v.path) return `The agent is accessing file: ${v.path}`
  if (t === 'tool_invoked' && v.directory !== undefined) return `The agent is listing files in "${v.directory || '.'}" to understand the project structure.`
  if (t === 'tool_invoked') return `The agent invoked a tool: ${s}`

  if (t === 'tool_result' && v.exit_code === 0) return `The command completed successfully (exit code 0). ${v.stdout || v.output ? 'See output below.' : ''}`
  if (t === 'tool_result' && v.exit_code !== undefined && v.exit_code !== 0) return `The command FAILED with exit code ${v.exit_code}. The agent will analyze the error and try a different approach.`
  if (t === 'tool_result' && v.files) return 'File listing retrieved. The agent now knows the project structure.'
  if (t === 'tool_result' && v.path) return `File "${v.path}" was read successfully (${v.size || 0} bytes).`
  if (t === 'tool_result') return s || 'Tool execution result received.'

  if (t === 'memory_write' && v.layer?.includes('working')) return `Working memory updated — the agent recorded a short-term fact: "${v.key}". This helps it track what commands were run and their results.`
  if (t === 'memory_write' && v.layer?.includes('episodic')) return `Episodic memory updated — the agent recorded a file interaction: "${v.key}". This tracks which files were read/written.`
  if (t === 'memory_write' && v.layer?.includes('semantic')) return `Semantic memory updated — the agent stored a long-term fact: "${v.key}". This includes README content, analysis results, and reports.`
  if (t === 'memory_write' && v.layer?.includes('risk')) return `Risk memory updated — the agent recorded a potential danger: "${v.key}".`
  if (t === 'memory_write') return `Memory layer "${v.layer}" updated with key "${v.key}".`

  if (t === 'checkpoint_created') return `A checkpoint was saved — this is a snapshot of the agent's entire state (memory + files). If something goes wrong later, execution can roll back to this exact point.`
  if (t === 'plan_generated') return `The agent's goal was set: "${v.goal}". The LLM tool-calling loop has started — GPT-4o-mini will now decide what to do step by step.`
  if (t === 'session_completed') return `The session is complete. ${v.outcome || s}`
  if (t === 'session_paused') return 'The session was paused — either by the Safety Engine (detected a problem) or manually by the user.'

  if (t === 'retry_detected') return 'The Safety Engine detected the agent is stuck in a retry loop — repeating the same failing action multiple times.'
  if (t === 'contradiction_detected') return 'The Safety Engine detected the agent contradicted a statement it made earlier.'
  if (t === 'drift_detected') return 'The Safety Engine detected the agent drifted away from the original task.'
  if (t === 'stall_detected') return 'The Safety Engine detected the agent has stalled — no progress in recent steps.'
  if (t === 'budget_overrun') return 'The Safety Engine detected excessive API usage — the agent may be stuck.'
  if (t === 'failure_detected') return `A failure was detected: ${s}`

  if (t === 'replay_started') return 'Recovery initiated — the system is rolling back to a previous checkpoint.'
  if (t === 'checkpoint_restored') return 'Checkpoint restored — memory and sandbox state rolled back to the saved point.'
  if (t === 'replay_completed') return 'Recovery complete — execution resumed from the restored checkpoint.'

  return s || `Event: ${t.replace(/_/g, ' ')}`
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
