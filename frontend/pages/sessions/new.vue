<template>
  <div class="max-w-2xl mx-auto">
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-white mb-2">New Execution Session</h1>
      <p class="text-surface-400">Launch a new agent task with safety monitoring.</p>
    </div>

    <form class="card p-6 space-y-5" @submit.prevent="submit">
      <div>
        <label class="block text-sm font-medium text-surface-300 mb-1.5">Task Title</label>
        <input v-model="form.title" class="input-field" placeholder="e.g. Debug failing auth tests" required />
      </div>

      <div>
        <label class="block text-sm font-medium text-surface-300 mb-1.5">Description</label>
        <textarea v-model="form.description" class="input-field min-h-[80px]" placeholder="Describe what the agent should do..." />
      </div>

      <div>
        <label class="block text-sm font-medium text-surface-300 mb-1.5">Goal</label>
        <input v-model="form.goal" class="input-field" placeholder="e.g. Fix failing test and verify all tests pass" />
      </div>

      <!-- Repo input -->
      <div class="space-y-3 rounded-2xl border border-surface-800 bg-surface-950/60 p-4">
        <div class="flex items-center gap-2 mb-1">
          <span class="text-sm font-medium text-surface-300">Repository</span>
          <span class="text-[10px] text-surface-600 bg-surface-800 px-1.5 py-0.5 rounded">cloned into sandbox</span>
        </div>
        <div>
          <label class="block text-xs text-surface-500 mb-1">Repository URL</label>
          <input
            v-model="form.repo_url"
            class="input-field"
            placeholder="https://github.com/owner/repo.git"
          />
        </div>
        <div>
          <label class="block text-xs text-surface-500 mb-1">Branch / Ref</label>
          <input
            v-model="form.repo_ref"
            class="input-field"
            placeholder="main (default)"
          />
        </div>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block text-sm font-medium text-surface-300 mb-1.5">Task Type</label>
          <select v-model="form.task_type" class="input-field">
            <option value="debug">Debug</option>
            <option value="investigate">Investigate</option>
            <option value="review">Review</option>
            <option value="research">Research</option>
            <option value="refactor">Refactor</option>
            <option value="custom">Custom</option>
          </select>
        </div>
        <div>
          <label class="block text-sm font-medium text-surface-300 mb-1.5">Scenario</label>
          <select v-model="scenario" class="input-field">
            <option value="healthy">Healthy Run</option>
            <option value="retry_loop">Retry Loop</option>
            <option value="contradiction">Contradiction</option>
            <option value="recovery">Recovery</option>
          </select>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block text-sm font-medium text-surface-300 mb-1.5">Safety Policy</label>
          <select v-model="form.safety_policy" class="input-field">
            <option value="standard">Standard</option>
            <option value="strict">Strict</option>
            <option value="permissive">Permissive</option>
          </select>
        </div>
        <div>
          <label class="block text-sm font-medium text-surface-300 mb-1.5">Memory Strategy</label>
          <select v-model="form.memory_strategy" class="input-field">
            <option value="default">Default</option>
            <option value="aggressive_cache">Aggressive Cache</option>
            <option value="minimal">Minimal</option>
          </select>
        </div>
      </div>

      <div class="flex items-center gap-3 pt-2">
        <label class="flex items-center gap-2 cursor-pointer">
          <input v-model="form.auto_checkpoint" type="checkbox" class="w-4 h-4 rounded bg-surface-800 border-surface-600 text-accent-600 focus:ring-accent-500" />
          <span class="text-sm text-surface-300">Auto-checkpoint</span>
        </label>
      </div>

      <div class="flex gap-3 pt-4 border-t border-surface-800">
        <button type="submit" class="btn-primary" :disabled="submitting">
          {{ submitting ? 'Creating...' : 'Create & Start Session' }}
        </button>
        <NuxtLink to="/" class="btn-secondary">Cancel</NuxtLink>
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
const api = useApi()

const form = reactive({
  title: '',
  description: '',
  goal: '',
  task_type: 'debug',
  repo_url: '',
  repo_ref: '',
  auto_checkpoint: true,
  safety_policy: 'standard',
  memory_strategy: 'default',
})

const scenario = ref('healthy')
const submitting = ref(false)

async function submit() {
  if (!form.title.trim()) return
  submitting.value = true
  try {
    const payload: Record<string, any> = { ...form }
    // Only send repo fields if filled in
    if (!payload.repo_url?.trim()) delete payload.repo_url
    if (!payload.repo_ref?.trim()) delete payload.repo_ref

    const session = await api.createSession(payload)
    await api.startSession(session.id, scenario.value)
    navigateTo(`/sessions/${session.id}`)
  } catch (e) {
    console.error(e)
  } finally {
    submitting.value = false
  }
}
</script>
