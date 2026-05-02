<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { tasksApi, type Task, type TaskCreateRequest } from '../api/tasks'
import { trackingApi, type TrackingSession } from '../api/tracking'
import { learningApi, type CorrectionCoefficient } from '../api/learning'
import ErrorBanner from '../components/ErrorBanner.vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import TaskForm from '../components/TaskForm.vue'

const route = useRoute()
const router = useRouter()
const taskId = route.params.id as string

const task = ref<Task | null>(null)
const sessions = ref<TrackingSession[]>([])
const coefficient = ref<CorrectionCoefficient | null>(null)
const loading = ref(false)
const error = ref('')
const editing = ref(false)
const saving = ref(false)
const trackingLoading = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [t, s, c] = await Promise.all([
      tasksApi.get(taskId),
      trackingApi.getSessions(taskId),
      learningApi.get(taskId),
    ])
    task.value = t
    sessions.value = s
    coefficient.value = c
  } catch (e: unknown) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

async function updateTask(data: TaskCreateRequest) {
  saving.value = true
  error.value = ''
  try {
    task.value = await tasksApi.update(taskId, data)
    editing.value = false
  } catch (e: unknown) {
    error.value = (e as Error).message
  } finally {
    saving.value = false
  }
}

async function trackAction(action: 'start' | 'stop' | 'interrupt_start' | 'interrupt_end') {
  trackingLoading.value = true
  error.value = ''
  try {
    if (action === 'start') await trackingApi.start(taskId)
    else if (action === 'stop') await trackingApi.stop(taskId)
    else if (action === 'interrupt_start') await trackingApi.interruptStart(taskId)
    else await trackingApi.interruptEnd(taskId)
    await load()
  } catch (e: unknown) {
    error.value = (e as Error).message
  } finally {
    trackingLoading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="px-6 py-4 border-b border-gray-800 flex items-center gap-3">
      <button @click="router.back()" class="text-gray-500 hover:text-white text-sm">← Back</button>
      <h1 class="text-xl font-semibold">{{ task?.title ?? 'Task Detail' }}</h1>
    </div>

    <ErrorBanner v-if="error" :message="error" />
    <LoadingSpinner v-if="loading" />

    <div v-else-if="task" class="px-6 py-5 space-y-6">
      <!-- Attributes -->
      <div v-if="!editing" class="p-5 bg-gray-900 border border-gray-800 rounded-xl space-y-3">
        <div class="flex justify-between items-start">
          <div>
            <p class="text-xs text-gray-500">State: <span class="text-white">{{ task.state }}</span></p>
            <p class="text-xs text-gray-500 mt-1">Type: <span class="text-white">{{ task.task_type }}</span></p>
          </div>
          <button @click="editing = true" class="text-xs text-blue-400 hover:text-blue-300">Edit</button>
        </div>
        <div class="grid grid-cols-3 gap-3 text-center">
          <div class="bg-gray-800 rounded-lg py-2">
            <p class="text-xs text-gray-500">Difficulty</p>
            <p class="text-lg font-bold">{{ task.difficulty }}</p>
          </div>
          <div class="bg-gray-800 rounded-lg py-2">
            <p class="text-xs text-gray-500">Urgency</p>
            <p class="text-lg font-bold">{{ task.urgency }}</p>
          </div>
          <div class="bg-gray-800 rounded-lg py-2">
            <p class="text-xs text-gray-500">Importance</p>
            <p class="text-lg font-bold">{{ task.importance }}</p>
          </div>
        </div>
        <p class="text-xs text-gray-500">Est. duration: <span class="text-white">{{ task.estimated_duration }} min</span></p>
        <p v-if="task.description" class="text-sm text-gray-300 whitespace-pre-wrap">{{ task.description }}</p>
        <p v-if="coefficient" class="text-xs text-gray-500">
          Correction coefficient: <span class="text-white">{{ coefficient.coefficient.toFixed(3) }}</span>
          ({{ coefficient.session_count }} sessions)
        </p>
      </div>

      <div v-else class="p-5 bg-gray-900 border border-gray-800 rounded-xl">
        <TaskForm :initial="task" :loading="saving" @submit="updateTask" @cancel="editing = false" />
      </div>

      <!-- Tracking controls -->
      <div class="p-5 bg-gray-900 border border-gray-800 rounded-xl">
        <h2 class="text-sm font-semibold mb-3 text-gray-300">Time Tracking</h2>
        <div class="flex gap-2 flex-wrap">
          <button @click="trackAction('start')" :disabled="trackingLoading"
            class="px-3 py-1.5 bg-green-700 hover:bg-green-600 disabled:opacity-50 rounded text-xs font-medium transition-colors">
            ▶ Start
          </button>
          <button @click="trackAction('interrupt_start')" :disabled="trackingLoading"
            class="px-3 py-1.5 bg-yellow-700 hover:bg-yellow-600 disabled:opacity-50 rounded text-xs font-medium transition-colors">
            ⏸ Interrupt
          </button>
          <button @click="trackAction('interrupt_end')" :disabled="trackingLoading"
            class="px-3 py-1.5 bg-blue-700 hover:bg-blue-600 disabled:opacity-50 rounded text-xs font-medium transition-colors">
            ▶ Resume
          </button>
          <button @click="trackAction('stop')" :disabled="trackingLoading"
            class="px-3 py-1.5 bg-red-700 hover:bg-red-600 disabled:opacity-50 rounded text-xs font-medium transition-colors">
            ■ Stop
          </button>
        </div>

        <div v-if="sessions.length" class="mt-4 space-y-2">
          <p class="text-xs text-gray-500 uppercase tracking-wide">Sessions</p>
          <div v-for="s in sessions" :key="s.id"
            class="text-xs text-gray-400 bg-gray-800 rounded px-3 py-2 flex justify-between">
            <span>{{ s.start_time.slice(0, 16) }}</span>
            <span v-if="s.actual_duration">{{ s.actual_duration }} min actual</span>
            <span v-else class="text-yellow-400">in progress</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
