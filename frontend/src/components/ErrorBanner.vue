<script setup lang="ts">
defineProps<{ message: string }>()
</script>

<template>
  <div class="mx-6 mt-4 px-4 py-3 bg-red-900/40 border border-red-700 rounded-lg text-sm text-red-300">
    {{ message }}
  </div>
</template>
