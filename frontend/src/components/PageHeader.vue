<script setup lang="ts">
defineProps<{ title: string; subtitle?: string }>()
</script>

<template>
  <div class="px-6 py-5 border-b border-gray-800">
    <h1 class="text-xl font-semibold">{{ title }}</h1>
    <p v-if="subtitle" class="text-sm text-gray-400 mt-0.5">{{ subtitle }}</p>
  </div>
</template>
