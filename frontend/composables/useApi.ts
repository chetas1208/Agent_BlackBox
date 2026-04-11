import type { Session, AgentEvent, MemoryItem, Checkpoint, DashboardData, SafetyAlert, SandboxFile } from '~/types'

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
    // Dashboard
    getDashboard: () => request<DashboardData>('/api/dashboard'),

    // Sessions
    getSessions: () => request<Session[]>('/api/sessions'),
    getSession: (id: string) => request<Session>(`/api/sessions/${id}`),
    getSessionSummary: () => request<any>('/api/sessions/summary'),
    createSession: (data: any) => request<Session>('/api/sessions', { method: 'POST', body: JSON.stringify(data) }),
    startSession: (id: string, scenario = 'healthy') => request<any>(`/api/sessions/${id}/start?scenario=${scenario}`, { method: 'POST' }),
    pauseSession: (id: string) => request<Session>(`/api/sessions/${id}/pause`, { method: 'POST' }),
    resumeSession: (id: string) => request<Session>(`/api/sessions/${id}/resume`, { method: 'POST' }),
    cancelSession: (id: string) => request<Session>(`/api/sessions/${id}/cancel`, { method: 'POST' }),

    // Events
    getEvents: (sessionId: string) => request<AgentEvent[]>(`/api/sessions/${sessionId}/events`),
    getEventStreamUrl: (sessionId: string) => `${base}/api/sessions/${sessionId}/events/stream`,

    // Memory
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

    // Checkpoints
    getCheckpoints: (sessionId: string) => request<Checkpoint[]>(`/api/sessions/${sessionId}/checkpoints`),
    createCheckpoint: (sessionId: string, label = 'manual') =>
      request<Checkpoint>(`/api/sessions/${sessionId}/checkpoints?label=${label}`, { method: 'POST' }),
    restoreCheckpoint: (sessionId: string, checkpointId: string) =>
      request<any>(`/api/sessions/${sessionId}/restore/${checkpointId}`, { method: 'POST' }),

    // Recovery
    replay: (sessionId: string) => request<any>(`/api/sessions/${sessionId}/replay`, { method: 'POST' }),
    getRecoveryReport: (sessionId: string) => request<any>(`/api/sessions/${sessionId}/recovery-report`),

    // Safety
    getAlerts: (sessionId: string) => request<SafetyAlert[]>(`/api/sessions/${sessionId}/alerts`),

    // Sandbox
    getSandbox: (sessionId: string) => request<{ sandbox_id: string; files: SandboxFile[] }>(`/api/sessions/${sessionId}/sandbox`),
    getSandboxFiles: (sessionId: string) => request<SandboxFile[]>(`/api/sessions/${sessionId}/sandbox/files`),

    // Seed
    seedAll: () => request<any>('/api/seed', { method: 'POST' }),
    seedScenario: (scenario: string) => request<any>(`/api/seed/${scenario}`, { method: 'POST' }),
  }
}
