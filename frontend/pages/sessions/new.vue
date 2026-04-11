<template>
  <div class="max-w-2xl mx-auto">
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-white mb-2">New Execution Session</h1>
      <p class="text-surface-400">Launch a new agent task with safety monitoring.</p>
    </div>

    <!-- Mode toggle -->
    <div class="flex gap-2 mb-6">
      <button
        class="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        :class="mode === 'real' ? 'bg-accent-600 text-white' : 'bg-surface-800 text-surface-400 hover:text-white'"
        @click="mode = 'real'"
      >
        Real Agent (GitHub Repo)
      </button>
      <button
        class="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        :class="mode === 'demo' ? 'bg-accent-600 text-white' : 'bg-surface-800 text-surface-400 hover:text-white'"
        @click="mode = 'demo'"
      >
        Demo Scenario
      </button>
    </div>

    <form class="card p-6 space-y-5" @submit.prevent="submit">

      <!-- Real agent fields -->
      <template v-if="mode === 'real'">
        <div class="bg-accent-900/20 border border-accent-700/40 rounded-lg p-4 text-sm text-accent-300">
          The agent will clone your repo into a <strong>Blaxel sandbox</strong>, then use GPT-4o-mini
          with real tool-calling to complete your task. All steps are monitored by the Safety Engine.
        </div>

        <div>
          <label class="block text-sm font-medium text-surface-300 mb-1.5">GitHub Repo URL <span class="text-red-400">*</span></label>
          <input v-model="form.repo_url" class="input-field" placeholder="https://github.com/user/repo" required />
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-surface-300 mb-1.5">Branch</label>
            <input v-model="form.branch" class="input-field" placeholder="main" />
          </div>
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
        </div>

        <div>
          <label class="block text-sm font-medium text-surface-300 mb-1.5">Task Title <span class="text-red-400">*</span></label>
          <input v-model="form.title" class="input-field" placeholder="e.g. Fix the failing login test" required />
        </div>

        <div>
          <label class="block text-sm font-medium text-surface-300 mb-1.5">Goal / Instructions</label>
          <textarea
            v-model="form.goal"
            class="input-field min-h-[100px]"
            placeholder="Describe exactly what the agent should do. Be specific. e.g. 'Run pytest, identify the failing test in tests/test_auth.py, fix the root cause, and confirm all tests pass.'"
          />
        </div>
      </template>

      <!-- Demo scenario fields -->
      <template v-else>
        <div class="bg-surface-800/60 border border-surface-700 rounded-lg p-4 text-sm text-surface-400">
          Demo scenarios use simulated agent steps to showcase the safety engine. No real repo needed.
        </div>

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
      </template>

      <!-- Shared options -->
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
          <span class="text-sm text-surface-300">Auto-checkpoint every 10 steps</span>
        </label>
      </div>

      <div v-if="error" class="text-red-400 text-sm bg-red-900/20 border border-red-700/40 rounded-lg p-3">
        {{ error }}
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

const mode = ref<'real' | 'demo'>('real')

const form = reactive({
  title: '',
  description: '',
  goal: '',
  task_type: 'debug',
  repo_url: '' as string | null,
  branch: 'main',
  auto_checkpoint: true,
  safety_policy: 'standard',
  memory_strategy: 'default',
})

const scenario = ref('healthy')
const submitting = ref(false)
const error = ref('')

async function submit() {
  if (!form.title.trim()) return
  error.value = ''
  submitting.value = true

  const payload: Record<string, unknown> = {
    title: form.title,
    description: form.description,
    goal: form.goal,
    task_type: form.task_type,
    auto_checkpoint: form.auto_checkpoint,
    safety_policy: form.safety_policy,
    memory_strategy: form.memory_strategy,
  }

  if (mode.value === 'real') {
    if (!form.repo_url?.trim()) {
      error.value = 'GitHub Repo URL is required for Real Agent mode.'
      submitting.value = false
      return
    }
    payload.repo_url = form.repo_url.trim()
    payload.branch = form.branch || 'main'
    payload.sandbox_profile = 'blaxel'
  }

  try {
    const session = await api.createSession(payload)
    await api.startSession(session.id, mode.value === 'real' ? 'real' : scenario.value)
    navigateTo(`/sessions/${session.id}`)
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Failed to create session'
    console.error(e)
  } finally {
    submitting.value = false
  }
}
</script>
