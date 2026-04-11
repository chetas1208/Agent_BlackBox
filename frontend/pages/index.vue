<template>
  <div>
    <!-- Hero -->
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-white mb-2">Dashboard</h1>
      <p class="text-surface-400">Runtime safety, observability, and recovery for autonomous AI agents.</p>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="flex items-center justify-center py-20">
      <div class="w-6 h-6 border-2 border-accent-500 border-t-transparent rounded-full animate-spin" />
    </div>

    <template v-else>
      <!-- Summary cards -->
      <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
        <StatCard title="Total Sessions" :value="data?.summary.total ?? 0" icon="📊" />
        <StatCard title="Active" :value="data?.summary.active ?? 0" icon="▶️" subtitle="Running now" />
        <StatCard title="Paused" :value="data?.summary.paused ?? 0" icon="⏸️" subtitle="Awaiting action" />
        <StatCard title="Failed" :value="data?.summary.failed ?? 0" icon="💥" subtitle="Needs attention" />
        <StatCard title="Completed" :value="data?.summary.completed ?? 0" icon="✅" />
        <StatCard title="Recovered" :value="data?.summary.recovered ?? 0" icon="🔄" subtitle="Auto-healed" />
      </div>

      <!-- Quick actions -->
      <div class="flex gap-3 mb-8">
        <NuxtLink to="/sessions/new" class="btn-primary">
          + New Session
        </NuxtLink>
        <button class="btn-secondary" @click="seedAndRefresh('healthy')">
          ▶ Healthy Run
        </button>
        <button class="btn-secondary" @click="seedAndRefresh('retry_loop')">
          🔁 Retry Loop
        </button>
        <button class="btn-secondary" @click="seedAndRefresh('contradiction')">
          ⚡ Contradiction
        </button>
        <button class="btn-secondary" @click="seedAndRefresh('recovery')">
          🔄 Recovery
        </button>
      </div>

      <!-- Recent sessions -->
      <div class="card mb-8">
        <div class="px-5 py-4 border-b border-surface-800">
          <h2 class="text-lg font-semibold text-surface-200">Recent Sessions</h2>
        </div>
        <div v-if="!data?.recent_sessions?.length" class="px-5 py-12 text-center text-surface-500">
          No sessions yet. Click "Seed Demo" or create a new session to get started.
        </div>
        <div v-else class="divide-y divide-surface-800/50">
          <NuxtLink
            v-for="session in data.recent_sessions"
            :key="session.id"
            :to="`/sessions/${session.id}`"
            class="flex items-center gap-4 px-5 py-3.5 hover:bg-surface-800/40 transition-colors group"
          >
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2.5 mb-0.5">
                <span class="text-sm font-medium text-surface-200 group-hover:text-white truncate transition-colors">
                  {{ session.title }}
                </span>
                <StatusBadge :status="session.status" dot />
              </div>
              <div class="text-xs text-surface-500 truncate">
                {{ session.goal || session.description }}
              </div>
            </div>
            <div class="flex items-center gap-4 flex-shrink-0">
              <div class="text-right">
                <div class="text-xs text-surface-500">Progress</div>
                <div class="text-sm font-mono text-surface-300">{{ session.progress_percent }}%</div>
              </div>
              <div class="text-right">
                <div class="text-xs text-surface-500">Risk</div>
                <div :class="['text-sm font-mono', riskColor(session.risk_score)]">
                  {{ (session.risk_score * 100).toFixed(0) }}%
                </div>
              </div>
              <div class="text-xs text-surface-600 font-mono w-16 text-right">
                {{ timeAgo(session.updated_at) }}
              </div>
            </div>
          </NuxtLink>
        </div>
      </div>

      <!-- Critical events -->
      <div class="card">
        <div class="px-5 py-4 border-b border-surface-800">
          <h2 class="text-lg font-semibold text-surface-200">Recent Critical Events</h2>
        </div>
        <div v-if="!data?.critical_events?.length" class="px-5 py-8 text-center text-surface-500">
          No critical events recorded.
        </div>
        <div v-else class="divide-y divide-surface-800/50">
          <div
            v-for="evt in data.critical_events.slice(0, 10)"
            :key="evt.id"
            class="flex items-center gap-3 px-5 py-3"
          >
            <span class="text-base flex-shrink-0">{{ eventTypeIcon(evt.event_type) }}</span>
            <div class="flex-1 min-w-0">
              <span class="text-sm text-surface-300 truncate block">{{ evt.summary }}</span>
              <span class="text-xs text-surface-600 font-mono">{{ evt.event_type }}</span>
            </div>
            <SeverityBadge :severity="evt.severity" />
            <span class="text-xs text-surface-600 font-mono flex-shrink-0">
              {{ formatTimestamp(evt.created_at) }}
            </span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { DashboardData } from '~/types'
import { riskColor, timeAgo, formatTimestamp, eventTypeIcon } from '~/utils/format'

const api = useApi()
const data = ref<DashboardData | null>(null)
const loading = ref(true)

async function load() {
  try {
    data.value = await api.getDashboard()
  } catch { /* empty */ }
  loading.value = false
}

async function seedAndRefresh(scenario: string) {
  try {
    const result = await api.seedScenario(scenario)
    if (result.session_id) {
      navigateTo(`/sessions/${result.session_id}`)
    }
  } catch (e) {
    console.error(e)
  }
}

onMounted(load)

useIntervalFn(load, 3000)
</script>
