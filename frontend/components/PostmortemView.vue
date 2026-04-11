<template>
  <div class="space-y-6">
    <!-- Mission Summary -->
    <div class="card p-5">
      <h3 class="text-xs font-semibold text-surface-500 uppercase tracking-wider mb-2">Mission Summary</h3>
      <p class="text-sm text-surface-300">{{ postmortem.mission_summary }}</p>
      <div class="mt-3 flex items-center gap-3">
        <span class="text-xs text-surface-500">Outcome:</span>
        <span class="text-sm font-medium text-surface-200">{{ postmortem.final_outcome }}</span>
      </div>
    </div>

    <!-- Stats -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
      <div class="card-sm p-3 text-center">
        <div class="text-xl font-bold text-surface-200">{{ postmortem.total_events }}</div>
        <div class="text-[10px] text-surface-500 uppercase">Events</div>
      </div>
      <div class="card-sm p-3 text-center">
        <div class="text-xl font-bold text-surface-200">{{ postmortem.total_checkpoints }}</div>
        <div class="text-[10px] text-surface-500 uppercase">Checkpoints</div>
      </div>
      <div class="card-sm p-3 text-center">
        <div class="text-xl font-bold text-surface-200">{{ postmortem.total_recovery_attempts }}</div>
        <div class="text-[10px] text-surface-500 uppercase">Recoveries</div>
      </div>
      <div class="card-sm p-3 text-center">
        <div class="text-xl font-bold text-surface-200">{{ formatDuration(postmortem.duration_seconds) }}</div>
        <div class="text-[10px] text-surface-500 uppercase">Duration</div>
      </div>
    </div>

    <!-- Root Cause -->
    <div class="card p-5 border-red-500/20">
      <h3 class="text-xs font-semibold text-red-400 uppercase tracking-wider mb-2">Root Cause</h3>
      <p class="text-sm text-surface-300">{{ postmortem.root_cause }}</p>
    </div>

    <!-- Sections from backend -->
    <div v-for="section in postmortem.sections" :key="section.title" :class="['card p-5', section.severity === 'error' ? 'border-red-500/20' : section.severity === 'warning' ? 'border-amber-500/20' : '']">
      <h3 :class="['text-xs font-semibold uppercase tracking-wider mb-2', section.severity === 'error' ? 'text-red-400' : section.severity === 'warning' ? 'text-amber-400' : 'text-surface-500']">
        {{ section.title }}
      </h3>
      <pre class="text-xs text-surface-400 whitespace-pre-wrap font-sans">{{ section.content }}</pre>
    </div>

    <!-- Policy Recommendations -->
    <div class="card p-5">
      <h3 class="text-xs font-semibold text-accent-400 uppercase tracking-wider mb-3">Policy Recommendations</h3>
      <ul class="space-y-2">
        <li v-for="(rec, i) in postmortem.policy_recommendations" :key="i" class="flex items-start gap-2 text-sm text-surface-300">
          <span class="text-accent-500 mt-0.5 flex-shrink-0">→</span>
          {{ rec }}
        </li>
      </ul>
    </div>

    <!-- Key Events -->
    <div v-if="postmortem.key_events?.length" class="card p-5">
      <h3 class="text-xs font-semibold text-surface-500 uppercase tracking-wider mb-3">Key Events</h3>
      <div class="space-y-1.5">
        <div v-for="(evt, i) in postmortem.key_events" :key="i" class="flex items-center gap-2 text-xs">
          <span :class="['badge border text-[10px]', evt.severity === 'error' || evt.severity === 'critical' ? 'badge-error' : evt.severity === 'warning' ? 'badge-warning' : 'badge-info']">
            {{ evt.severity }}
          </span>
          <span class="text-surface-400 truncate">{{ evt.summary }}</span>
          <span class="text-surface-600 font-mono ml-auto flex-shrink-0">{{ evt.type }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Postmortem } from '~/types'
defineProps<{ postmortem: Postmortem }>()

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(0)}s`
  const mins = Math.floor(seconds / 60)
  const secs = Math.round(seconds % 60)
  return `${mins}m ${secs}s`
}
</script>
