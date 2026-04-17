<template>
  <div class="max-w-2xl mx-auto">
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-white mb-2">New Execution Session</h1>
      <p class="text-surface-400">Launch a real agent task or run a demo scenario.</p>
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

      <!-- Real agent -->
      <template v-if="mode === 'real'">
        <div class="bg-accent-900/20 border border-accent-700/40 rounded-lg p-4 text-sm text-accent-300">
          The agent clones your repo into a <strong>Blaxel sandbox</strong>, fixes the issue using GPT-4o-mini,
          creates a <strong>GitHub PR</strong>, and all steps are monitored by the Safety Engine.
        </div>

        <!-- GitHub repo picker (if token connected) -->
        <div v-if="auth.isLoggedIn.value && auth.user.value?.github_username">
          <label class="block text-sm font-medium text-surface-300 mb-1.5">
            GitHub Repo
            <span class="text-surface-500 ml-1">(from your account)</span>
          </label>
          <div v-if="loadingRepos" class="text-surface-500 text-sm py-2">Loading repos...</div>
          <select v-else-if="repos.length" v-model="selectedRepo" class="input-field" @change="onRepoSelect">
            <option value="">— Select a repo —</option>
            <option v-for="r in repos" :key="r.full_name" :value="r">
              {{ r.full_name }} {{ r.private ? '🔒' : '' }}
            </option>
          </select>
          <p class="text-surface-500 text-xs mt-1">
            Or paste a URL below manually.
          </p>
        </div>
        <div v-else-if="auth.isLoggedIn.value" class="text-sm text-surface-400 bg-surface-800/60 rounded-lg p-3">
          Connect GitHub in <NuxtLink to="/settings" class="text-accent-400 hover:underline">Settings</NuxtLink> to pick repos from a dropdown.
        </div>

        <div>
          <label class="block text-sm font-medium text-surface-300 mb-1.5">GitHub Repo URL <span class="text-red-400">*</span></label>
          <input v-model="form.repo_url" class="input-field" placeholder="https://github.com/org/repo" />
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
              <option value="refactor">Refactor</option>
              <option value="custom">Custom</option>
            </select>
          </div>
        </div>

        <div>
          <label class="block text-sm font-medium text-surface-300 mb-1.5">Task Title <span class="text-red-400">*</span></label>
          <input v-model="form.title" class="input-field" placeholder="Fix the failing login test" required />
        </div>

        <div>
          <label class="block text-sm font-medium text-surface-300 mb-1.5">Goal / Instructions</label>
          <textarea
            v-model="form.goal"
            class="input-field min-h-[100px]"
            placeholder="Describe exactly what the agent should do. e.g. 'Run pytest, identify the failing test in tests/test_auth.py, fix the root cause, verify all tests pass, then create a PR.'"
          />
        </div>
      </template>

      <!-- Demo scenario -->
      <template v-else>
        <div class="bg-surface-800/60 border border-surface-700 rounded-lg p-4 text-sm text-surface-400">
          Demo scenarios use simulated agent steps to showcase the Safety Engine. No real repo needed.
        </div>

        <div>
          <label class="block text-sm font-medium text-surface-300 mb-1.5">Task Title</label>
          <input v-model="form.title" class="input-field" placeholder="Debug failing auth tests" required />
        </div>

        <div>
          <label class="block text-sm font-medium text-surface-300 mb-1.5">Description</label>
          <textarea v-model="form.description" class="input-field min-h-[80px]" placeholder="Describe what the agent should do..." />
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-surface-300 mb-1.5">Task Type</label>
            <select v-model="form.task_type" class="input-field">
              <option value="debug">Debug</option>
              <option value="investigate">Investigate</option>
              <option value="review">Review</option>
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

      <!-- Shared -->
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

      <label class="flex items-center gap-2 cursor-pointer pt-1">
        <input v-model="form.auto_checkpoint" type="checkbox" class="w-4 h-4 rounded bg-surface-800 border-surface-600" />
        <span class="text-sm text-surface-300">Auto-checkpoint every 10 steps</span>
      </label>

      <div v-if="error" class="text-red-400 text-sm bg-red-900/20 border border-red-700/40 rounded-lg p-3">{{ error }}</div>

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
const auth = useCustomAuth()

const mode = ref<'real' | 'demo'>('real')
const scenario = ref('healthy')
const submitting = ref(false)
const error = ref('')
const repos = ref<any[]>([])
const loadingRepos = ref(false)
const selectedRepo = ref<any>(null)

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

onMounted(async () => {
  if (auth.isLoggedIn.value && auth.user.value?.github_username) {
    loadingRepos.value = true
    try {
      repos.value = await auth.listGithubRepos()
    } catch {}
    loadingRepos.value = false
  }
})

function onRepoSelect() {
  if (!selectedRepo.value) return
  form.repo_url = selectedRepo.value.html_url
  form.branch = selectedRepo.value.default_branch || 'main'
  if (!form.title) form.title = `Work on ${selectedRepo.value.name}`
}

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
    const config = useRuntimeConfig()
    const headers: Record<string, string> = { 'Content-Type': 'application/json', ...auth.getAuthHeaders() }

    const res = await fetch(`${config.public.apiBase}/api/sessions`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    })
    if (!res.ok) throw new Error(`Failed to create session: ${res.status}`)
    const session = await res.json()

    const startRes = await fetch(`${config.public.apiBase}/api/sessions/${session.id}/start?scenario=${mode.value === 'real' ? 'real' : scenario.value}`, {
      method: 'POST',
      headers,
    })
    if (!startRes.ok) throw new Error('Failed to start session')

    navigateTo(`/sessions/${session.id}`)
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : 'Failed to create session'
    if (msg === 'Failed to fetch') {
      error.value =
        'Cannot reach the API. Start the backend (port 8000), e.g. from repo root: cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000 --env-file .env — or run make dev.'
    } else {
      error.value = msg
    }
  } finally {
    submitting.value = false
  }
}
</script>
