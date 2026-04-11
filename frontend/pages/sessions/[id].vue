<template>
  <div v-if="!session" class="flex items-center justify-center py-20">
    <div class="w-6 h-6 border-2 border-accent-500 border-t-transparent rounded-full animate-spin" />
  </div>

  <div v-else>
    <!-- Header -->
    <div class="mb-6">
      <div class="flex items-start justify-between gap-4 mb-3">
        <div>
          <div class="flex items-center gap-3 mb-1">
            <NuxtLink to="/" class="text-surface-500 hover:text-surface-300 transition-colors">
              ← Back
            </NuxtLink>
          </div>
          <h1 class="text-2xl font-bold text-white mb-1">{{ session.title }}</h1>
          <p class="text-surface-400 text-sm">{{ session.goal || session.description }}</p>
        </div>
        <div class="flex items-center gap-2 flex-shrink-0">
          <StatusBadge :status="session.status" dot />
          <span class="badge badge-neutral border text-xs font-mono">{{ session.task_type }}</span>
        </div>
      </div>

      <!-- Meta bar -->
      <div class="flex items-center gap-6 flex-wrap">
        <ProgressBar :value="session.progress_percent" label="Progress" class="w-48" />
        <div class="flex items-center gap-4">
          <RiskGauge :value="session.risk_score" label="Risk" :invert="true" />
          <RiskGauge :value="session.confidence_score" label="Confidence" />
        </div>
        <div class="flex items-center gap-2 ml-auto">
          <button
            v-if="session.status === 'running'"
            class="btn-secondary text-sm"
            @click="doPause"
          >
            ⏸ Pause
          </button>
          <button
            v-if="session.status === 'paused'"
            class="btn-primary text-sm"
            @click="doResume"
          >
            ▶ Resume
          </button>
          <button
            v-if="session.status === 'running' || session.status === 'paused'"
            class="btn-danger text-sm"
            @click="doCancel"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>

    <!-- Plan -->
    <div v-if="session.current_plan?.length" class="card-sm p-4 mb-6">
      <h3 class="text-xs font-semibold text-surface-500 uppercase tracking-wider mb-2">Current Plan</h3>
      <div class="flex flex-wrap gap-2">
        <span
          v-for="(step, i) in session.current_plan"
          :key="i"
          class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-surface-800 text-xs text-surface-300"
        >
          <span class="text-surface-600 font-mono">{{ i + 1 }}.</span>
          {{ step }}
        </span>
      </div>
    </div>

    <!-- Tabs -->
    <div class="border-b border-surface-800 mb-6">
      <nav class="flex gap-1 -mb-px">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          :class="[
            'px-4 py-2.5 text-sm font-medium border-b-2 transition-colors',
            activeTab === tab.id
              ? 'border-accent-500 text-accent-400'
              : 'border-transparent text-surface-500 hover:text-surface-300 hover:border-surface-600',
          ]"
          @click="activeTab = tab.id"
        >
          {{ tab.label }}
          <span v-if="tab.count !== undefined" class="ml-1.5 text-xs font-mono text-surface-600">
            {{ tab.count }}
          </span>
        </button>
      </nav>
    </div>

    <!-- Tab content -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Main column -->
      <div class="lg:col-span-2">
        <!-- Timeline -->
        <div v-if="activeTab === 'timeline'" class="relative">
          <div v-if="!events.length" class="card p-8 text-center text-surface-500">
            Waiting for events...
            <div v-if="isStreaming" class="mt-2">
              <div class="w-4 h-4 border-2 border-accent-500 border-t-transparent rounded-full animate-spin mx-auto" />
            </div>
          </div>
          <div v-else>
            <div class="flex items-center justify-between mb-4">
              <span class="text-sm text-surface-500">{{ events.length }} events</span>
              <div class="flex items-center gap-2">
                <span v-if="isStreaming" class="badge badge-info border text-xs">
                  <span class="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse mr-1.5" />
                  Live
                </span>
              </div>
            </div>
            <div ref="timelineRef">
              <TimelineEvent
                v-for="evt in displayEvents"
                :key="evt.id"
                :event="evt"
              />
            </div>
          </div>
        </div>

        <!-- Memory -->
        <div v-if="activeTab === 'memory'">
          <div class="flex gap-2 mb-4 flex-wrap">
            <button
              v-for="layer in memoryLayers"
              :key="layer.value"
              :class="[
                'badge border text-xs cursor-pointer transition-colors',
                memoryFilter === layer.value ? layer.activeClass : 'bg-surface-800 text-surface-400 border-surface-700 hover:border-surface-600',
              ]"
              @click="memoryFilter = memoryFilter === layer.value ? '' : layer.value"
            >
              {{ layer.label }}
            </button>
          </div>
          <div v-if="!filteredMemory.length" class="card p-8 text-center text-surface-500">
            No memory items{{ memoryFilter ? ' for this layer' : '' }}.
          </div>
          <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <MemoryCard v-for="item in filteredMemory" :key="item.id" :item="item" />
          </div>
        </div>

        <!-- Checkpoints -->
        <div v-if="activeTab === 'checkpoints'">
          <div v-if="!checkpoints.length" class="card p-8 text-center text-surface-500">
            No checkpoints created yet.
          </div>
          <div v-else class="space-y-3">
            <CheckpointCard
              v-for="cp in checkpoints"
              :key="cp.id"
              :checkpoint="cp"
              show-restore
              @restore="doRestore"
            />
          </div>
        </div>

        <!-- Sandbox -->
        <div v-if="activeTab === 'sandbox'">
          <div v-if="!sandboxFiles.length" class="card p-8 text-center text-surface-500">
            No sandbox data available.
          </div>
          <div v-else class="space-y-3">
            <div v-for="file in sandboxFiles" :key="file.path" class="card-sm p-4">
              <div class="flex items-center justify-between mb-2">
                <span class="text-sm font-mono text-accent-400">{{ file.path }}</span>
                <span class="text-xs text-surface-600">{{ file.size }} bytes</span>
              </div>
              <pre class="text-xs font-mono text-surface-400 bg-surface-950 rounded-lg p-3 overflow-x-auto max-h-40">{{ file.content }}</pre>
            </div>
          </div>
        </div>

        <!-- Recovery -->
        <div v-if="activeTab === 'recovery'">
          <div v-if="!recoveryReport" class="card p-8 text-center text-surface-500">
            Loading recovery data...
          </div>
          <div v-else>
            <div class="grid grid-cols-3 gap-4 mb-6">
              <div class="card-sm p-4 text-center">
                <div class="text-2xl font-bold text-surface-200">{{ recoveryReport.failure_count }}</div>
                <div class="text-xs text-surface-500">Failures</div>
              </div>
              <div class="card-sm p-4 text-center">
                <div class="text-2xl font-bold text-surface-200">{{ recoveryReport.recovery_count }}</div>
                <div class="text-xs text-surface-500">Recoveries</div>
              </div>
              <div class="card-sm p-4 text-center">
                <div class="text-2xl font-bold text-surface-200">{{ recoveryReport.checkpoints }}</div>
                <div class="text-xs text-surface-500">Checkpoints</div>
              </div>
            </div>

            <div v-if="recoveryReport.failures?.length" class="mb-6">
              <h3 class="text-sm font-semibold text-surface-400 mb-3">Failure Events</h3>
              <div class="space-y-2">
                <div v-for="f in recoveryReport.failures" :key="f.id" class="card-sm p-3 border-red-500/20">
                  <div class="text-sm text-red-400">{{ f.summary }}</div>
                  <div class="text-xs text-surface-600 font-mono mt-1">{{ f.event_type }} · {{ formatTimestamp(f.created_at) }}</div>
                </div>
              </div>
            </div>

            <div v-if="recoveryReport.recoveries?.length">
              <h3 class="text-sm font-semibold text-surface-400 mb-3">Recovery Events</h3>
              <div class="space-y-2">
                <div v-for="r in recoveryReport.recoveries" :key="r.id" class="card-sm p-3 border-emerald-500/20">
                  <div class="text-sm text-emerald-400">{{ r.summary }}</div>
                  <div class="text-xs text-surface-600 font-mono mt-1">{{ r.event_type }} · {{ formatTimestamp(r.created_at) }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Report -->
        <div v-if="activeTab === 'report'">
          <div v-if="reportLoading" class="card p-8 text-center">
            <div class="w-6 h-6 border-2 border-accent-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p class="text-surface-400 text-sm">Loading report...</p>
          </div>
          <div v-else-if="!reportData?.report" class="card p-8 text-center text-surface-500">
            <div class="text-4xl mb-3">📋</div>
            <p class="font-medium mb-1">No report yet</p>
            <p class="text-sm text-surface-600">The agent generates a report when it calls <code class="text-accent-400">generate_report</code> before completing the task.</p>
            <p v-if="session.status === 'running'" class="text-xs text-surface-600 mt-2">Session is still running — check back soon.</p>
          </div>
          <div v-else>
            <!-- Report header -->
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-2">
                <span class="text-green-400 text-sm font-medium">✓ Report Ready</span>
                <span v-if="reportData.source" class="badge badge-neutral border text-xs">{{ reportData.source }}</span>
                <span v-if="reportData.generated_at" class="text-surface-600 text-xs">{{ reportData.generated_at }}</span>
              </div>
              <button class="btn-secondary text-xs" @click="downloadReport">Download .md</button>
            </div>
            <!-- Rendered markdown -->
            <div class="card p-6 prose-report" v-html="renderedReport" />
          </div>
        </div>

        <!-- JSON -->
        <div v-if="activeTab === 'json'">
          <div class="card p-4">
            <h3 class="text-sm font-semibold text-surface-400 mb-3">Session JSON</h3>
            <pre class="text-xs font-mono text-surface-400 bg-surface-950 rounded-lg p-4 overflow-auto max-h-[600px]">{{ JSON.stringify(session, null, 2) }}</pre>
          </div>
        </div>
      </div>

      <!-- Right sidebar -->
      <div class="space-y-4">
        <!-- Session health -->
        <div class="card p-4">
          <h3 class="text-xs font-semibold text-surface-500 uppercase tracking-wider mb-3">Session Health</h3>
          <div class="flex justify-center gap-6 mb-4">
            <RiskGauge :value="session.risk_score" label="Risk" :invert="true" />
            <RiskGauge :value="session.confidence_score" label="Confidence" />
          </div>
          <div class="space-y-2 text-xs">
            <div class="flex justify-between">
              <span class="text-surface-500">Status</span>
              <StatusBadge :status="session.status" />
            </div>
            <div class="flex justify-between">
              <span class="text-surface-500">Stage</span>
              <span class="text-surface-300 font-mono">{{ session.stage }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-surface-500">Events</span>
              <span class="text-surface-300 font-mono">{{ events.length }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-surface-500">Sandbox</span>
              <span class="text-surface-300 font-mono text-[11px]">{{ session.sandbox_id?.slice(0, 12) || 'none' }}</span>
            </div>
          </div>
        </div>

        <!-- Checkpoints sidebar -->
        <div class="card p-4">
          <h3 class="text-xs font-semibold text-surface-500 uppercase tracking-wider mb-3">
            Checkpoints ({{ checkpoints.length }})
          </h3>
          <div v-if="!checkpoints.length" class="text-xs text-surface-600 text-center py-3">
            No checkpoints yet
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="cp in checkpoints.slice(-5)"
              :key="cp.id"
              class="flex items-center gap-2 text-xs"
            >
              <span class="text-surface-600">💾</span>
              <span class="text-surface-300 truncate flex-1">{{ cp.label || cp.id.slice(0, 8) }}</span>
              <span class="text-surface-600 font-mono">#{{ cp.event_index }}</span>
            </div>
          </div>
        </div>

        <!-- Active alerts -->
        <div class="card p-4">
          <h3 class="text-xs font-semibold text-surface-500 uppercase tracking-wider mb-3">
            Safety Alerts
          </h3>
          <div v-if="!alerts.length" class="text-xs text-surface-600 text-center py-3">
            No alerts — all clear
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="alert in alerts.slice(0, 5)"
              :key="alert.id"
              :class="['card-sm p-2.5', alert.severity === 'error' || alert.severity === 'critical' ? 'border-red-500/20' : 'border-amber-500/20']"
            >
              <div class="text-xs text-surface-300 mb-1">{{ alert.message }}</div>
              <div class="flex items-center gap-2">
                <span class="badge badge-neutral text-[10px] border">{{ alert.detector_type }}</span>
                <span :class="['badge border text-[10px]', alert.resolved ? 'badge-success' : 'badge-error']">
                  {{ alert.resolved ? 'resolved' : 'active' }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- Memory summary -->
        <div class="card p-4">
          <h3 class="text-xs font-semibold text-surface-500 uppercase tracking-wider mb-3">
            Memory Summary
          </h3>
          <div class="space-y-1.5 text-xs">
            <div v-for="layer in memoryLayers" :key="layer.value" class="flex items-center justify-between">
              <span :class="['badge border text-[10px]', layer.activeClass]">{{ layer.label }}</span>
              <span class="text-surface-400 font-mono">
                {{ memory.filter(m => m.layer === layer.value).length }}
              </span>
            </div>
            <div class="pt-1 border-t border-surface-800 flex items-center justify-between">
              <span class="text-surface-500">Quarantined</span>
              <span class="text-red-400 font-mono">
                {{ memory.filter(m => m.status === 'quarantined').length }}
              </span>
            </div>
          </div>
        </div>

        <!-- Outcome -->
        <div v-if="session.outcome" class="card p-4">
          <h3 class="text-xs font-semibold text-surface-500 uppercase tracking-wider mb-2">Outcome</h3>
          <p class="text-sm text-surface-300">{{ session.outcome }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Session, MemoryItem, Checkpoint, SafetyAlert, SandboxFile } from '~/types'
import { formatTimestamp } from '~/utils/format'

const route = useRoute()
const api = useApi()

const sessionId = computed(() => route.params.id as string)

const session = ref<Session | null>(null)
const memory = ref<MemoryItem[]>([])
const checkpoints = ref<Checkpoint[]>([])
const alerts = ref<SafetyAlert[]>([])
const sandboxFiles = ref<SandboxFile[]>([])
const recoveryReport = ref<any>(null)
const reportData = ref<{ report: string | null; source: string | null; generated_at: string } | null>(null)
const reportLoading = ref(false)
const memoryFilter = ref('')

const activeTab = ref('timeline')

const { events, isStreaming } = useEventStream(sessionId)

const tabs = computed(() => [
  { id: 'timeline', label: 'Timeline', count: events.value.length },
  { id: 'report', label: reportData.value?.report ? '📋 Report ✓' : '📋 Report' },
  { id: 'memory', label: 'Memory', count: memory.value.length },
  { id: 'checkpoints', label: 'Checkpoints', count: checkpoints.value.length },
  { id: 'sandbox', label: 'Sandbox' },
  { id: 'recovery', label: 'Recovery' },
  { id: 'json', label: 'JSON' },
])

const memoryLayers = [
  { value: 'working_memory', label: 'Working', activeClass: 'bg-blue-500/20 text-blue-400 border-blue-500/30' },
  { value: 'episodic_memory', label: 'Episodic', activeClass: 'bg-purple-500/20 text-purple-400 border-purple-500/30' },
  { value: 'semantic_memory', label: 'Semantic', activeClass: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' },
  { value: 'risk_memory', label: 'Risk', activeClass: 'bg-red-500/20 text-red-400 border-red-500/30' },
]

const displayEvents = computed(() => [...events.value].reverse().slice(0, 200))

const filteredMemory = computed(() => {
  if (!memoryFilter.value) return memory.value
  return memory.value.filter(m => m.layer === memoryFilter.value)
})

// Simple markdown → HTML renderer (no external lib needed)
function renderMarkdown(md: string): string {
  return md
    .replace(/^### (.+)$/gm, '<h3 class="text-base font-semibold text-white mt-5 mb-2">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="text-lg font-bold text-white mt-6 mb-3 border-b border-surface-700 pb-2">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 class="text-xl font-bold text-accent-400 mb-1">$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong class="text-surface-200">$1</strong>')
    .replace(/`([^`]+)`/g, '<code class="bg-surface-800 text-accent-400 px-1.5 py-0.5 rounded text-xs font-mono">$1</code>')
    .replace(/^```[\s\S]*?^```/gm, (block) => {
      const code = block.replace(/^```[^\n]*\n/, '').replace(/```$/, '')
      return `<pre class="bg-surface-950 rounded-lg p-3 text-xs font-mono text-surface-400 overflow-x-auto my-3">${code}</pre>`
    })
    .replace(/^---$/gm, '<hr class="border-surface-700 my-4">')
    .replace(/^- (.+)$/gm, '<li class="text-surface-300 text-sm ml-4 list-disc">$1</li>')
    .replace(/^(\d+\.) (.+)$/gm, '<li class="text-surface-300 text-sm ml-4 list-decimal">$2</li>')
    .replace(/^(?!<[h1-6|li|hr|pre])(.+)$/gm, '<p class="text-surface-300 text-sm mb-2">$1</p>')
    .replace(/<\/li>\n<li/g, '</li><li')
}

const renderedReport = computed(() => {
  if (!reportData.value?.report) return ''
  return renderMarkdown(reportData.value.report)
})

async function loadReport() {
  reportLoading.value = true
  try {
    reportData.value = await api.getReport(sessionId.value)
  } catch { /* empty */ } finally {
    reportLoading.value = false
  }
}

function downloadReport() {
  if (!reportData.value?.report) return
  const blob = new Blob([reportData.value.report], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `agent-report-${sessionId.value.slice(0, 8)}.md`
  a.click()
  URL.revokeObjectURL(url)
}

async function loadSession() {
  try {
    session.value = await api.getSession(sessionId.value)
  } catch { /* empty */ }
}

async function loadSideData() {
  try {
    const [mem, cps, al] = await Promise.all([
      api.getMemory(sessionId.value),
      api.getCheckpoints(sessionId.value),
      api.getAlerts(sessionId.value),
    ])
    memory.value = mem
    checkpoints.value = cps
    alerts.value = al
  } catch { /* empty */ }
}

async function loadSandbox() {
  try {
    const data = await api.getSandbox(sessionId.value)
    sandboxFiles.value = data.files || []
  } catch { /* empty */ }
}

async function loadRecovery() {
  try {
    recoveryReport.value = await api.getRecoveryReport(sessionId.value)
  } catch { /* empty */ }
}

async function doPause() {
  await api.pauseSession(sessionId.value)
  await loadSession()
}

async function doResume() {
  await api.resumeSession(sessionId.value)
  await loadSession()
}

async function doCancel() {
  await api.cancelSession(sessionId.value)
  await loadSession()
}

async function doRestore(checkpointId: string) {
  await api.restoreCheckpoint(sessionId.value, checkpointId)
  await loadSession()
}

onMounted(() => {
  loadSession()
  loadSideData()
  loadReport()
})

watch(activeTab, (tab) => {
  if (tab === 'sandbox') loadSandbox()
  if (tab === 'recovery') loadRecovery()
  if (tab === 'report') loadReport()
})

useIntervalFn(async () => {
  await loadSession()
  await loadSideData()
}, 2000)
</script>
