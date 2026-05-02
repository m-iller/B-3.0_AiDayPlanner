<script setup lang="ts">
import { RouterView, RouterLink } from 'vue-router'

const navItems = [
  { to: '/calendar',    label: 'Calendar',    icon: '📅' },
  { to: '/tasks',       label: 'Tasks',       icon: '✅' },
  { to: '/scheduler',   label: 'Scheduler',   icon: '⚡' },
  { to: '/fatigue',     label: 'Fatigue',     icon: '🔋' },
  { to: '/tracking',    label: 'Tracker',     icon: '⏱️' },
  { to: '/learning',    label: 'Learning',    icon: '📈' },
  { to: '/probability', label: 'Probability', icon: '🎯' },
]
</script>

<template>
  <div class="flex h-screen bg-gray-950 text-gray-100">
    <!-- Sidebar -->
    <nav class="w-56 shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col">
      <div class="px-5 py-4 border-b border-gray-800">
        <span class="text-lg font-semibold tracking-tight">AI Day Planner</span>
      </div>
      <ul class="flex-1 py-3 space-y-0.5 px-2">
        <li v-for="item in navItems" :key="item.to">
          <RouterLink
            :to="item.to"
            class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
            active-class="bg-gray-800 text-white"
          >
            <span>{{ item.icon }}</span>
            <span>{{ item.label }}</span>
          </RouterLink>
        </li>
      </ul>
    </nav>

    <!-- Main content -->
    <main class="flex-1 overflow-y-auto">
      <RouterView />
    </main>
  </div>
</template>
