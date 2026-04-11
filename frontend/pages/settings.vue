<template>
  <div class="max-w-2xl mx-auto">
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-white mb-2">Settings</h1>
      <p class="text-surface-400">Connect GitHub to access private repos and create PRs automatically.</p>
    </div>

    <div class="card p-6 space-y-5">
      <div>
        <h2 class="text-lg font-semibold text-white mb-1">GitHub Integration</h2>
        <p class="text-sm text-surface-400 mb-4">
          Paste a GitHub Personal Access Token (PAT) with <code class="text-accent-400">repo</code> scope.
          <a href="https://github.com/settings/tokens/new?scopes=repo&description=AgentBlackBox" target="_blank" class="text-accent-400 hover:text-accent-300 ml-1">Generate one here →</a>
        </p>

        <div v-if="auth.user.value?.github_username" class="flex items-center gap-3 p-3 bg-green-900/20 border border-green-700/40 rounded-lg mb-4">
          <span class="text-green-400 text-sm">Connected as <strong>{{ auth.user.value.github_username }}</strong></span>
        </div>

        <div class="space-y-3">
          <div>
            <label class="block text-sm font-medium text-surface-300 mb-1.5">GitHub Personal Access Token</label>
            <input v-model="ghToken" type="password" class="input-field" placeholder="ghp_xxxxxxxxxxxx" />
          </div>
          <div>
            <label class="block text-sm font-medium text-surface-300 mb-1.5">Your GitHub Username</label>
            <input v-model="ghUsername" class="input-field" placeholder="your-github-username" />
          </div>
        </div>

        <div v-if="ghError" class="text-red-400 text-sm mt-3">{{ ghError }}</div>
        <div v-if="ghSuccess" class="text-green-400 text-sm mt-3">{{ ghSuccess }}</div>

        <button class="btn-primary mt-4" :disabled="ghSaving" @click="saveGithub">
          {{ ghSaving ? 'Saving...' : 'Save GitHub Token' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const auth = useAuth()
const ghToken = ref('')
const ghUsername = ref(auth.user.value?.github_username || '')
const ghSaving = ref(false)
const ghError = ref('')
const ghSuccess = ref('')

async function saveGithub() {
  if (!ghToken.value || !ghUsername.value) return
  ghSaving.value = true
  ghError.value = ''
  ghSuccess.value = ''
  try {
    await auth.saveGithubToken(ghToken.value, ghUsername.value)
    ghSuccess.value = `Connected as ${ghUsername.value}`
    ghToken.value = ''
  } catch (e: unknown) {
    ghError.value = e instanceof Error ? e.message : 'Failed to save token'
  } finally {
    ghSaving.value = false
  }
}
</script>
