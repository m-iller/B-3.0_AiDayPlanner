<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { tasksApi, type Task } from '../api/tasks'
import { trackingApi, type TrackingSession } from '../api/tracking'
import PageHeader from '../components/PageHeader.vue'
import ErrorBanner from '../components/ErrorBanner.vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'

const tasks = ref<Task[]>([])
const selectedTaskId = ref('')
const sessions = ref<TrackingSession[]>([])
const loading = ref(false)
const actionLoading = ref(false)
const error = ref('')

async function loadTasks() {
  loading.value = true
  try {
    tasks.value = await tasksApi.list()
  } catch (e: unknown) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

async function loadSessions() {
  if (!selectedTaskId.value) return
  try {
    sessions.value = await trackingApi.getSessions(selectedTaskId.value)
  } catch (e: unknown) {
    error.value = (e as Error).message
  }
}

async function action(type: 'start' | 'stop' | 'interrupt_start' | 'interrupt_end') {
  if (!selectedTaskId.value) return
  actionLoading.value = true
  error.value = ''
  try {
    if (type === 'start') await trackingApi.start(selectedTaskId.value)
    else if (type === 'stop') await trackingApi.stop(selectedTaskId.value)
    else if (type === 'interrupt_start') await trackingApi.interruptStart(selectedTaskId.value)
    else await trackingApi.interruptEnd(selectedTaskId.value)
    await loadSessions()
  } catch (e: unknown) {
    error.value = (e as Error).message
  } finally {
    actionLoading.value = false
  }
}

const selectedTask = () => tasks.value.find(t => t.id === selectedTaskId.value)

onMounted(loadTasks)
</script>

<template>
  <div>
    <PageHeader title="Time Tracker" subtitle="Record actual time spent on tasks" />
    <ErrorBanner v-if="error" :message="error" />
    <LoadingSpinner v-if="loading" />

    <div v-else class="px-6 py-5 space-y-5">
      <!-- Task selector -->
      <div>
        <label class="block text-xs text-gray-400 mb-1">Select Task</label>
        <select v-model="selectedTaskId" @change="loadSessions"
          class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
          <option value="">— choose a task —</option>
          <option v-for="t in tasks" :key="t.id" :value="t.id">
            {{ t.title }} ({{ t.state }})
          </option>
        </select>
      </div>

      <!-- Controls -->
      <div v-if="selectedTaskId" class="p-5 bg-gray-900 border border-gray-800 rounded-xl">
        <p class="text-sm font-medium mb-3">{{ selectedTask()?.title }}</p>
        <p class="text-xs text-gray-500 mb-4">State: {{ selectedTask()?.state }}</p>
        <div class="flex gap-2 flex-wrap">
          <button @click="action('start')" :disabled="actionLoading"
            class="px-3 py-1.5 bg-green-700 hover:bg-green-600 disabled:opacity-50 rounded text-xs font-medium transition-colors">
            ▶ Start
          </button>
          <button @click="action('interrupt_start')" :disabled="actionLoading"
            class="px-3 py-1.5 bg-yellow-700 hover:bg-yellow-600 disabled:opacity-50 rounded text-xs font-medium transition-colors">
            ⏸ Interrupt
          </button>
          <button @click="action('interrupt_end')" :disabled="actionLoading"
            class="px-3 py-1.5 bg-blue-700 hover:bg-blue-600 disabled:opacity-50 rounded text-xs font-medium transition-colors">
            ▶ Resume
          </button>
          <button @click="action('stop')" :disabled="actionLoading"
            class="px-3 py-1.5 bg-red-700 hover:bg-red-600 disabled:opacity-50 rounded text-xs font-medium transition-colors">
            ■ Stop
          </button>
        </div>
      </div>

      <!-- Sessions -->
      <div v-if="sessions.length">
        <p class="text-xs text-gray-500 uppercase tracking-wide mb-2">Sessions</p>
        <div class="space-y-2">
          <div v-for="s in sessions" :key="s.id"
            class="px-4 py-3 bg-gray-900 border border-gray-800 rounded-xl text-xs space-y-1">
            <div class="flex justify-between">
              <span class="text-gray-400">Started: {{ s.start_time.slice(0, 16) }}</span>
              <span v-if="s.actual_duration" class="text-green-400 font-medium">{{ s.actual_duration }} min</span>
              <span v-else class="text-yellow-400">in progress</span>
            </div>
            <div v-if="s.interruptions?.length" class="text-gray-600">
              {{ s.interruptions.length }} interruption(s)
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
