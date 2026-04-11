<template>
  <div class="min-h-screen flex flex-col">
    <!-- Top nav -->
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
          <button
            class="ml-2 btn-primary text-sm !py-1.5"
            @click="seedDemo"
          >
            Seed Demo
          </button>
        </nav>
      </div>
    </header>

    <!-- Main content -->
    <main class="flex-1">
      <div class="max-w-[1600px] mx-auto px-4 sm:px-6 py-6">
        <slot />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
const api = useApi()

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
