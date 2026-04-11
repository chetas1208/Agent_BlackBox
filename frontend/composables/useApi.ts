import type {
  Session, AgentEvent, MemoryItem, Checkpoint, DashboardData,
  SafetyAlert, SandboxFile, ApprovalGate, RecoveryBranch,
  Postmortem, BranchComparison,
} from '~/types'

export function useApi() {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  async function request<T>(path: string, options?: RequestInit): Promise<T> {
    const res = await fetch(`${base}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
    if (!res.ok) {
      throw new Error(`API error: ${res.status} ${res.statusText}`)
    }
    return res.json()
  }

  return {
    getDashboard: () => request<DashboardData>('/api/dashboard'),

    getSessions: () => request<Session[]>('/api/sessions'),
    getSession: (id: string) => request<Session>(`/api/sessions/${id}`),
    createSession: (data: any) => request<Session>('/api/sessions', { method: 'POST', body: JSON.stringify(data) }),
    startSession: (id: string, scenario = 'healthy') => request<any>(`/api/sessions/${id}/start?scenario=${scenario}`, { method: 'POST' }),
    pauseSession: (id: string) => request<Session>(`/api/sessions/${id}/pause`, { method: 'POST' }),
    resumeSession: (id: string) => request<Session>(`/api/sessions/${id}/resume`, { method: 'POST' }),
    cancelSession: (id: string) => request<Session>(`/api/sessions/${id}/cancel`, { method: 'POST' }),

    getEvents: (sessionId: string) => request<AgentEvent[]>(`/api/sessions/${sessionId}/events`),
    getEventStreamUrl: (sessionId: string) => `${base}/api/sessions/${sessionId}/events/stream`,

    getMemory: (sessionId: string, layer?: string, status?: string) => {
      const params = new URLSearchParams()
      if (layer) params.set('layer', layer)
      if (status) params.set('status', status)
      const qs = params.toString()
      return request<MemoryItem[]>(`/api/sessions/${sessionId}/memory${qs ? '?' + qs : ''}`)
    },
    quarantineMemory: (memoryId: string, sessionId: string) =>
      request<MemoryItem>(`/api/memory/${memoryId}/quarantine?session_id=${sessionId}`, { method: 'POST' }),
    promoteMemory: (memoryId: string, sessionId: string) =>
      request<MemoryItem>(`/api/memory/${memoryId}/promote?session_id=${sessionId}`, { method: 'POST' }),

    getCheckpoints: (sessionId: string) => request<Checkpoint[]>(`/api/sessions/${sessionId}/checkpoints`),
    restoreCheckpoint: (sessionId: string, checkpointId: string) =>
      request<any>(`/api/sessions/${sessionId}/restore/${checkpointId}`, { method: 'POST' }),

    replay: (sessionId: string) => request<any>(`/api/sessions/${sessionId}/replay`, { method: 'POST' }),
    getRecoveryReport: (sessionId: string) => request<any>(`/api/sessions/${sessionId}/recovery-report`),

    getAlerts: (sessionId: string) => request<SafetyAlert[]>(`/api/sessions/${sessionId}/alerts`),

    getSandbox: (sessionId: string) => request<{ sandbox_id: string; files: SandboxFile[] }>(`/api/sessions/${sessionId}/sandbox`),

    // Approvals
    getApprovals: (sessionId: string) => request<ApprovalGate[]>(`/api/sessions/${sessionId}/approvals`),
    getPendingApproval: (sessionId: string) => request<ApprovalGate | { status: string }>(`/api/sessions/${sessionId}/approvals/pending`),
    approveAction: (sessionId: string, gateId: string) =>
      request<ApprovalGate>(`/api/sessions/${sessionId}/approvals/${gateId}/approve`, { method: 'POST' }),
    denyAction: (sessionId: string, gateId: string) =>
      request<ApprovalGate>(`/api/sessions/${sessionId}/approvals/${gateId}/deny`, { method: 'POST' }),

    // Branches
    getBranches: (sessionId: string) => request<RecoveryBranch[]>(`/api/sessions/${sessionId}/branches`),
    compareBranches: (sessionId: string) => request<BranchComparison>(`/api/sessions/${sessionId}/branches/compare`),

    // Postmortem
    getPostmortem: (sessionId: string) => request<Postmortem>(`/api/sessions/${sessionId}/postmortem`),
    generatePostmortem: (sessionId: string) => request<Postmortem>(`/api/sessions/${sessionId}/postmortem/generate`, { method: 'POST' }),

    // Seed
    seedAll: () => request<any>('/api/seed', { method: 'POST' }),
    seedScenario: (scenario: string) => request<any>(`/api/seed/${scenario}`, { method: 'POST' }),
  }
}
