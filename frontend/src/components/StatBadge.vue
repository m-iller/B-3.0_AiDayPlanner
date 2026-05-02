<script setup lang="ts">
defineProps<{ label: string; value: string | number; color?: string }>()
</script>

<template>
  <div class="flex flex-col items-center px-4 py-3 bg-gray-800 rounded-lg">
    <span class="text-xs text-gray-400 uppercase tracking-wide">{{ label }}</span>
    <span :class="['text-2xl font-bold mt-1', color ?? 'text-white']">{{ value }}</span>
  </div>
</template>
