<template>
  <div class="card p-5">
    <div class="flex items-center justify-between mb-3">
      <span class="text-sm font-medium text-surface-500">{{ title }}</span>
      <span class="text-lg">{{ icon }}</span>
    </div>
    <div class="text-3xl font-bold text-surface-100 tracking-tight">
      {{ value }}
    </div>
    <div v-if="subtitle" class="text-xs text-surface-500 mt-1">
      {{ subtitle }}
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  value: string | number
  icon: string
  subtitle?: string
}>()
</script>
