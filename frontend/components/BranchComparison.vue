<template>
  <div>
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-sm font-semibold text-surface-300">Recovery Branches</h3>
      <span class="text-xs text-surface-600 font-mono">{{ branches.length }} branches</span>
    </div>

    <div v-if="!branches.length" class="card p-8 text-center text-surface-500">
      No recovery branches created.
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div
        v-for="branch in branches"
        :key="branch.id"
        :class="['card-sm p-4 transition-all', branch.is_winner ? 'border-emerald-500/40 bg-emerald-950/10' : branch.status === 'failed' || branch.status === 'discarded' ? 'border-red-500/20 opacity-70' : '']"
      >
        <!-- Header -->
        <div class="flex items-start justify-between gap-2 mb-2">
          <div class="flex items-center gap-2">
            <span :class="['badge border text-xs', statusClass(branch.status)]">
              {{ branch.status }}
            </span>
            <span v-if="branch.is_winner" class="badge bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-xs font-semibold">
              WINNER
            </span>
          </div>
          <span class="text-[10px] text-surface-600 font-mono">{{ branch.id.slice(0, 8) }}</span>
        </div>

        <!-- Strategy -->
        <h4 class="text-sm font-medium text-surface-200 mb-1">{{ branch.strategy }}</h4>
        <p v-if="branch.description" class="text-xs text-surface-400 mb-3">{{ branch.description }}</p>

        <!-- Outcome -->
        <div v-if="branch.outcome" class="text-xs p-2 rounded-lg bg-surface-950 text-surface-300 mb-3">
          {{ branch.outcome }}
        </div>

        <!-- Stats -->
        <div class="grid grid-cols-3 gap-2 text-xs">
          <div>
            <span class="text-surface-600 block">Confidence</span>
            <span :class="branch.confidence_score > 0.7 ? 'text-emerald-400' : branch.confidence_score > 0.4 ? 'text-amber-400' : 'text-red-400'">
              {{ (branch.confidence_score * 100).toFixed(0) }}%
            </span>
          </div>
          <div>
            <span class="text-surface-600 block">Risk</span>
            <span :class="branch.risk_score > 0.5 ? 'text-red-400' : 'text-surface-400'">
              {{ (branch.risk_score * 100).toFixed(0) }}%
            </span>
          </div>
          <div>
            <span class="text-surface-600 block">Events</span>
            <span class="text-surface-300">{{ branch.event_count }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { RecoveryBranch, BranchComparison } from '~/types'
defineProps<{ branches: RecoveryBranch[]; comparison: BranchComparison | null }>()

function statusClass(status: string): string {
  const map: Record<string, string> = {
    running: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    completed: 'bg-surface-700/50 text-surface-400 border-surface-600',
    failed: 'bg-red-500/20 text-red-400 border-red-500/30',
    selected: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    discarded: 'bg-surface-700/50 text-surface-500 border-surface-600',
  }
  return map[status] || map.completed
}
</script>
