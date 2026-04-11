import type { EventSeverity, EventType, SessionStatus, MemoryLayer, MemoryStatus } from '~/types'

export function formatTimestamp(ts: string): string {
  const d = new Date(ts)
  return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function formatDateTime(ts: string): string {
  const d = new Date(ts)
  return d.toLocaleString('en-US', {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export function timeAgo(ts: string): string {
  const now = Date.now()
  const then = new Date(ts).getTime()
  const diff = Math.floor((now - then) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

export function severityColor(severity: EventSeverity): string {
  const map: Record<EventSeverity, string> = {
    debug: 'badge-neutral',
    info: 'badge-info',
    warning: 'badge-warning',
    error: 'badge-error',
    critical: 'badge-critical',
  }
  return map[severity] || 'badge-neutral'
}

export function statusColor(status: SessionStatus): string {
  const map: Record<SessionStatus, string> = {
    pending: 'badge-neutral',
    running: 'badge-info',
    paused: 'badge-warning',
    completed: 'badge-success',
    failed: 'badge-error',
    recovered: 'badge-success',
    cancelled: 'badge-neutral',
  }
  return map[status] || 'badge-neutral'
}

export function memoryLayerLabel(layer: MemoryLayer): string {
  const map: Record<MemoryLayer, string> = {
    working_memory: 'Working',
    episodic_memory: 'Episodic',
    semantic_memory: 'Semantic',
    risk_memory: 'Risk',
  }
  return map[layer] || layer
}

export function memoryLayerColor(layer: MemoryLayer): string {
  const map: Record<MemoryLayer, string> = {
    working_memory: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    episodic_memory: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
    semantic_memory: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    risk_memory: 'bg-red-500/20 text-red-400 border-red-500/30',
  }
  return map[layer] || ''
}

export function memoryStatusColor(status: MemoryStatus): string {
  const map: Record<MemoryStatus, string> = {
    active: 'badge-success',
    stale: 'badge-warning',
    quarantined: 'badge-error',
    archived: 'badge-neutral',
  }
  return map[status] || 'badge-neutral'
}

export function eventTypeIcon(type: EventType): string {
  const icons: Partial<Record<EventType, string>> = {
    session_created: '🚀',
    plan_generated: '📋',
    memory_read: '📖',
    memory_write: '✏️',
    tool_invoked: '🔧',
    tool_result: '📦',
    checkpoint_created: '💾',
    checkpoint_restored: '🔄',
    failure_detected: '💥',
    contradiction_detected: '⚡',
    retry_detected: '🔁',
    risk_score_changed: '📊',
    drift_detected: '🧭',
    replay_started: '▶️',
    replay_completed: '✅',
    session_completed: '🏁',
    session_paused: '⏸️',
    agent_step: '🤖',
    memory_quarantined: '🔒',
    stall_detected: '⏳',
    budget_overrun: '💰',
  }
  return icons[type] || '📌'
}

export function riskColor(score: number): string {
  if (score < 0.3) return 'text-emerald-400'
  if (score < 0.6) return 'text-amber-400'
  return 'text-red-400'
}

export function confidenceColor(score: number): string {
  if (score > 0.7) return 'text-emerald-400'
  if (score > 0.4) return 'text-amber-400'
  return 'text-red-400'
}

export function percentColor(pct: number): string {
  if (pct >= 80) return 'bg-emerald-500'
  if (pct >= 40) return 'bg-accent-500'
  return 'bg-amber-500'
}
