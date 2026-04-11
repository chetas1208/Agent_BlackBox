export type SessionStatus = 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'recovered' | 'cancelled'
export type SessionStage = 'planning' | 'executing' | 'evaluating' | 'recovering' | 'checkpointing' | 'finishing' | 'idle'
export type TaskType = 'debug' | 'investigate' | 'review' | 'research' | 'refactor' | 'custom'

export interface Session {
  id: string
  title: string
  description: string
  goal: string
  task_type: TaskType
  status: SessionStatus
  stage: SessionStage
  sandbox_id: string | null
  risk_score: number
  confidence_score: number
  progress_percent: number
  current_plan: string[]
  last_checkpoint_id: string | null
  event_count: number
  auto_checkpoint: boolean
  safety_policy: string
  memory_strategy: string
  started_at: string | null
  ended_at: string | null
  created_at: string
  updated_at: string
  outcome: string | null
}

export type EventType =
  | 'session_created' | 'plan_generated' | 'memory_read' | 'memory_write'
  | 'tool_invoked' | 'tool_result' | 'checkpoint_created' | 'checkpoint_restored'
  | 'failure_detected' | 'contradiction_detected' | 'retry_detected'
  | 'risk_score_changed' | 'drift_detected' | 'policy_blocked'
  | 'replay_started' | 'replay_completed' | 'session_completed'
  | 'session_paused' | 'session_resumed' | 'sandbox_action'
  | 'stall_detected' | 'budget_overrun' | 'memory_quarantined'
  | 'memory_promoted' | 'agent_step'

export type EventActor = 'agent' | 'runtime' | 'safety_engine' | 'operator' | 'recovery_engine'
export type EventSeverity = 'debug' | 'info' | 'warning' | 'error' | 'critical'

export interface AgentEvent {
  id: string
  session_id: string
  event_type: EventType
  actor: EventActor
  severity: EventSeverity
  summary: string
  payload: Record<string, any>
  related_memory_ids: string[]
  checkpoint_id: string | null
  created_at: string
}

export type MemoryLayer = 'working_memory' | 'episodic_memory' | 'semantic_memory' | 'risk_memory'
export type MemoryStatus = 'active' | 'stale' | 'quarantined' | 'archived'

export interface MemoryItem {
  id: string
  session_id: string
  layer: MemoryLayer
  key: string
  value: any
  source: string
  confidence: number
  contradiction_score: number
  importance_score: number
  recency_score: number
  status: MemoryStatus
  dependency_refs: string[]
  tags: string[]
  created_at: string
  updated_at: string
  expires_at: string | null
}

export interface Checkpoint {
  id: string
  session_id: string
  label: string
  event_index: number
  plan_snapshot: string[]
  memory_snapshot_ref: string
  sandbox_snapshot_ref: string
  safety_status: string
  risk_score_at: number
  confidence_at: number
  created_at: string
}

export interface SafetyAlert {
  id: string
  session_id: string
  detector_type: string
  severity: string
  message: string
  trigger_event_id: string | null
  resolved: boolean
  action_taken: string | null
  created_at: string
}

export interface DashboardData {
  summary: {
    total: number
    active: number
    paused: number
    failed: number
    completed: number
    recovered: number
  }
  recent_sessions: Session[]
  critical_events: AgentEvent[]
}

export interface SandboxFile {
  path: string
  content: string
  size: number
}
