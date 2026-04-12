<template>
  <div class="min-h-screen flex items-center justify-center bg-surface-950 px-4">
    <div class="w-full max-w-md">
      <div class="text-center mb-8">
        <div class="w-12 h-12 rounded-xl bg-accent-600 flex items-center justify-center text-white font-bold text-lg mx-auto mb-4">AB</div>
        <h1 class="text-2xl font-bold text-white">Reset your password</h1>
        <p class="text-surface-400 mt-1">Enter your email to get a reset token</p>
      </div>

      <div class="card p-6 space-y-4">
        <!-- Step 1: Enter email -->
        <template v-if="!resetToken">
          <div>
            <label class="block text-sm font-medium text-surface-300 mb-1.5">Email address</label>
            <input
              v-model="email"
              type="email"
              class="input-field"
              placeholder="you@company.com"
              @keyup.enter="requestReset"
            />
          </div>

          <div v-if="error" class="text-red-400 text-sm bg-red-900/20 border border-red-700/40 rounded-lg p-3">
            {{ error }}
          </div>

          <button class="btn-primary w-full" :disabled="loading" @click="requestReset">
            {{ loading ? 'Sending...' : 'Get Reset Token' }}
          </button>
        </template>

        <!-- Step 2: Show token + new password -->
        <template v-else>
          <div class="bg-amber-900/20 border border-amber-700/40 rounded-lg p-4">
            <p class="text-amber-400 text-sm font-semibold mb-2">Your reset token (valid for 1 hour):</p>
            <code class="block text-xs font-mono text-amber-300 bg-surface-950 p-3 rounded break-all select-all">{{ resetToken }}</code>
            <p class="text-amber-600 text-xs mt-2">In production this would be emailed. Copy it below.</p>
          </div>

          <div>
            <label class="block text-sm font-medium text-surface-300 mb-1.5">New password</label>
            <input
              v-model="newPassword"
              type="password"
              class="input-field"
              placeholder="New password (min 6 chars)"
              @keyup.enter="doReset"
            />
          </div>

          <div v-if="error" class="text-red-400 text-sm bg-red-900/20 border border-red-700/40 rounded-lg p-3">
            {{ error }}
          </div>
          <div v-if="success" class="text-green-400 text-sm bg-green-900/20 border border-green-700/40 rounded-lg p-3">
            {{ success }}
          </div>

          <button class="btn-primary w-full" :disabled="loading || !!success" @click="doReset">
            {{ loading ? 'Resetting...' : success ? 'Done ✓' : 'Reset Password' }}
          </button>

          <NuxtLink v-if="success" to="/login" class="block text-center text-sm text-accent-400 hover:text-accent-300 mt-2">
            Go to Sign In →
          </NuxtLink>
        </template>

        <p class="text-center text-sm text-surface-400">
          Remember it?
          <NuxtLink to="/login" class="text-accent-400 hover:text-accent-300">Sign in</NuxtLink>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: false })

const config = useRuntimeConfig()
const base = config.public.apiBase

const email = ref('')
const newPassword = ref('')
const resetToken = ref('')
const loading = ref(false)
const error = ref('')
const success = ref('')

async function requestReset() {
  if (!email.value) return
  loading.value = true
  error.value = ''
  try {
    const res = await fetch(`${base}/api/auth/forgot-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email.value }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || 'Failed')
    resetToken.value = data.reset_token
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Request failed'
  } finally {
    loading.value = false
  }
}

async function doReset() {
  if (!newPassword.value || newPassword.value.length < 6) {
    error.value = 'Password must be at least 6 characters'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const res = await fetch(`${base}/api/auth/reset-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: resetToken.value, new_password: newPassword.value }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || 'Failed')
    success.value = 'Password reset! You can now sign in with your new password.'
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Reset failed'
  } finally {
    loading.value = false
  }
}
</script>
