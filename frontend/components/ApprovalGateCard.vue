<template>
  <div :class="['card p-5 border-2 transition-all', isPending ? 'border-amber-500/50 bg-amber-950/10' : 'border-surface-700']">
    <!-- Pending indicator -->
    <div v-if="isPending" class="flex items-center gap-2 mb-3">
      <span class="w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse" />
      <span class="text-sm font-semibold text-amber-400 uppercase tracking-wider">Approval Required</span>
    </div>
    <div v-else class="flex items-center gap-2 mb-3">
      <span :class="['badge border text-xs', gate.status === 'approved' || gate.status === 'auto_approved' ? 'badge-success' : 'badge-error']">
        {{ gate.status }}
      </span>
      <span v-if="gate.resolved_by" class="text-xs text-surface-500">by {{ gate.resolved_by }}</span>
    </div>

    <!-- Action info -->
    <div class="flex items-center gap-2 mb-2">
      <span class="badge badge-warning border text-xs">{{ gate.action_type.replace(/_/g, ' ') }}</span>
      <span :class="['badge border text-xs', riskClass]">risk: {{ gate.risk_level }}</span>
    </div>

    <h4 class="text-sm font-medium text-surface-200 mb-1">{{ gate.action_summary }}</h4>
    <p class="text-xs text-surface-400 mb-3">{{ gate.rationale }}</p>

    <!-- Evidence -->
    <div v-if="gate.evidence?.length" class="mb-3">
      <span class="text-xs text-surface-500 block mb-1">Evidence:</span>
      <ul class="space-y-0.5">
        <li v-for="(e, i) in gate.evidence" :key="i" class="text-xs text-surface-400 pl-3 relative before:content-['•'] before:absolute before:left-0 before:text-surface-600">
          {{ e }}
        </li>
      </ul>
    </div>

    <!-- Risk score -->
    <div class="mb-4">
      <div class="flex justify-between text-xs mb-1">
        <span class="text-surface-500">Risk Score</span>
        <span :class="riskTextClass">{{ (gate.risk_score * 100).toFixed(0) }}%</span>
      </div>
      <div class="h-1.5 bg-surface-800 rounded-full overflow-hidden">
        <div :class="['h-full rounded-full transition-all', riskBarClass]" :style="{ width: `${gate.risk_score * 100}%` }" />
      </div>
    </div>

    <!-- Actions -->
    <div v-if="isPending" class="flex gap-2">
      <button class="flex-1 px-4 py-2 text-sm font-medium text-emerald-400 bg-emerald-600/15 border border-emerald-500/30 rounded-xl hover:bg-emerald-600/25 transition-colors" @click="$emit('approve', gate.id)">
        Approve
      </button>
      <button class="flex-1 px-4 py-2 text-sm font-medium text-red-400 bg-red-600/15 border border-red-500/30 rounded-xl hover:bg-red-600/25 transition-colors" @click="$emit('deny', gate.id)">
        Deny
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ApprovalGate } from '~/types'
const props = defineProps<{ gate: ApprovalGate }>()
defineEmits<{ approve: [id: string]; deny: [id: string] }>()

const isPending = computed(() => props.gate.status === 'pending')
const riskClass = computed(() => {
  if (props.gate.risk_level === 'critical') return 'bg-red-500/20 text-red-400 border-red-500/30'
  if (props.gate.risk_level === 'high') return 'bg-red-500/15 text-red-400 border-red-500/25'
  if (props.gate.risk_level === 'medium') return 'bg-amber-500/20 text-amber-400 border-amber-500/30'
  return 'bg-surface-700/50 text-surface-400 border-surface-600'
})
const riskTextClass = computed(() => props.gate.risk_score > 0.6 ? 'text-red-400' : props.gate.risk_score > 0.3 ? 'text-amber-400' : 'text-surface-400')
const riskBarClass = computed(() => props.gate.risk_score > 0.6 ? 'bg-red-500' : props.gate.risk_score > 0.3 ? 'bg-amber-500' : 'bg-emerald-500')
</script>
