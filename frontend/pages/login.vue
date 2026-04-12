<template>
  <div class="min-h-screen flex items-center justify-center bg-surface-950 px-4">
    <div class="w-full max-w-md">
      <div class="text-center mb-8">
        <div class="w-12 h-12 rounded-xl bg-accent-600 flex items-center justify-center text-white font-bold text-lg mx-auto mb-4">AB</div>
        <h1 class="text-2xl font-bold text-white">Agent Black Box</h1>
        <p class="text-surface-400 mt-1">Sign in to your workspace</p>
      </div>

      <div class="card p-6 space-y-4">
        <div>
          <label class="block text-sm font-medium text-surface-300 mb-1.5">Email</label>
          <input v-model="form.email" type="email" class="input-field" placeholder="you@company.com" @keyup.enter="submit" />
        </div>
        <div>
          <div class="flex items-center justify-between mb-1.5">
            <label class="block text-sm font-medium text-surface-300">Password</label>
            <NuxtLink to="/forgot-password" class="text-xs text-accent-400 hover:text-accent-300">
              Forgot password?
            </NuxtLink>
          </div>
          <input v-model="form.password" type="password" class="input-field" placeholder="••••••••" @keyup.enter="submit" />
        </div>

        <div v-if="error" class="text-red-400 text-sm bg-red-900/20 border border-red-700/40 rounded-lg p-3">{{ error }}</div>

        <button class="btn-primary w-full" :disabled="loading" @click="submit">
          {{ loading ? 'Signing in...' : 'Sign In' }}
        </button>

        <p class="text-center text-sm text-surface-400">
          No account?
          <NuxtLink to="/register" class="text-accent-400 hover:text-accent-300">Create one</NuxtLink>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: false })

const auth = useAuth()
const form = reactive({ email: '', password: '' })
const loading = ref(false)
const error = ref('')

async function submit() {
  if (!form.email || !form.password) return
  loading.value = true
  error.value = ''
  try {
    await auth.login(form.email, form.password)
    navigateTo('/')
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Login failed'
  } finally {
    loading.value = false
  }
}
</script>
