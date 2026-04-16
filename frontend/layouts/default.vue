<template>
  <div class="min-h-screen flex flex-col">
    <header class="sticky top-0 z-50 border-b border-surface-800 bg-surface-950/80 backdrop-blur-xl">
      <div class="max-w-[1600px] mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
        <NuxtLink to="/" class="flex items-center gap-2.5 group">
          <div class="w-8 h-8 rounded-lg bg-accent-600 flex items-center justify-center text-white font-bold text-sm">
            AB
          </div>
          <span class="text-lg font-bold text-surface-100 group-hover:text-white transition-colors">
            Agent Black Box
          </span>
        </NuxtLink>

        <nav class="flex items-center gap-1">
          <NuxtLink
            to="/"
            class="px-3 py-1.5 text-sm font-medium text-surface-400 hover:text-white rounded-lg hover:bg-surface-800 transition-all"
          >
            Dashboard
          </NuxtLink>
          <NuxtLink
            to="/sessions/new"
            class="px-3 py-1.5 text-sm font-medium text-surface-400 hover:text-white rounded-lg hover:bg-surface-800 transition-all"
          >
            New Session
          </NuxtLink>
          <button class="ml-2 btn-primary text-sm !py-1.5" @click="seedDemo">
            Seed Demo
          </button>

          <!-- Auth: Clerk when configured, fallback otherwise -->
          <div class="ml-3 flex items-center gap-2">
            <template v-if="clerkEnabled">
              <SignedIn>
                <NuxtLink
                  to="/settings"
                  class="px-3 py-1.5 text-sm font-medium text-surface-400 hover:text-white rounded-lg hover:bg-surface-800 transition-all"
                >
                  Settings
                </NuxtLink>
                <UserButton :after-sign-out-url="'/'" />
              </SignedIn>
              <SignedOut>
                <SignInButton mode="modal">
                  <button class="px-3 py-1.5 text-sm font-medium text-accent-400 hover:text-accent-300 rounded-lg hover:bg-surface-800 transition-all">
                    Sign in
                  </button>
                </SignInButton>
                <SignUpButton mode="modal">
                  <button class="px-3 py-1.5 text-sm font-medium text-surface-400 hover:text-white rounded-lg hover:bg-surface-800 transition-all">
                    Sign up
                  </button>
                </SignUpButton>
              </SignedOut>
            </template>
            <template v-else>
              <template v-if="customAuth.isLoggedIn.value">
                <NuxtLink
                  to="/settings"
                  class="px-3 py-1.5 text-sm font-medium text-surface-400 hover:text-white rounded-lg hover:bg-surface-800 transition-all"
                >
                  {{ customAuth.user.value?.name || 'Settings' }}
                </NuxtLink>
                <button
                  class="px-3 py-1.5 text-sm font-medium text-surface-500 hover:text-white rounded-lg hover:bg-surface-800 transition-all"
                  @click="customAuth.logout()"
                >
                  Sign out
                </button>
              </template>
              <template v-else>
                <NuxtLink
                  to="/login"
                  class="px-3 py-1.5 text-sm font-medium text-accent-400 hover:text-accent-300 rounded-lg hover:bg-surface-800 transition-all"
                >
                  Sign in
                </NuxtLink>
              </template>
            </template>
          </div>
        </nav>
      </div>
    </header>

    <main class="flex-1">
      <div class="max-w-[1600px] mx-auto px-4 sm:px-6 py-6">
        <slot />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
const api = useApi()
const customAuth = useCustomAuth()
const clerkEnabled = useRuntimeConfig().public.clerkEnabled as boolean

onMounted(() => {
  if (!clerkEnabled) {
    customAuth.fetchMe()
  }
})

async function seedDemo() {
  try {
    await api.seedAll()
    navigateTo('/')
    window.location.reload()
  } catch (e) {
    console.error('Seed failed:', e)
  }
}
</script>
