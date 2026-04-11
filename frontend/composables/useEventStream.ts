import type { AgentEvent } from '~/types'

export function useEventStream(sessionId: Ref<string>) {
  const api = useApi()
  const events = ref<AgentEvent[]>([])
  const isStreaming = ref(false)
  let eventSource: EventSource | null = null

  function startStream() {
    if (eventSource) stopStream()

    const url = api.getEventStreamUrl(sessionId.value)
    eventSource = new EventSource(url)
    isStreaming.value = true

    eventSource.onmessage = (e) => {
      try {
        const event: AgentEvent = JSON.parse(e.data)
        events.value = [...events.value, event]
      } catch { /* keepalive or parse error */ }
    }

    eventSource.onerror = () => {
      isStreaming.value = false
    }
  }

  function stopStream() {
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
    isStreaming.value = false
  }

  async function loadExisting() {
    try {
      events.value = await api.getEvents(sessionId.value)
    } catch { /* empty */ }
  }

  onMounted(() => {
    loadExisting()
    startStream()
  })

  onUnmounted(() => {
    stopStream()
  })

  watch(sessionId, () => {
    events.value = []
    loadExisting()
    startStream()
  })

  return { events, isStreaming, startStream, stopStream, loadExisting }
}
