<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { tasksApi, type Task, type TaskCreateRequest } from '../api/tasks'
import PageHeader from '../components/PageHeader.vue'
import ErrorBanner from '../components/ErrorBanner.vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import TaskForm from '../components/TaskForm.vue'

const router = useRouter()
const tasks = ref<Task[]>([])
const loading = ref(false)
const error = ref('')
const showForm = ref(false)
const saving = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  try {
    tasks.value = await tasksApi.list()
  } catch (e: unknown) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

async function createTask(data: TaskCreateRequest) {
  saving.value = true
  error.value = ''
  try {
    await tasksApi.create(data)
    showForm.value = false
    await load()
  } catch (e: unknown) {
    error.value = (e as Error).message
  } finally {
    saving.value = false
  }
}

async function deleteTask(id: string) {
  if (!confirm('Delete this task?')) return
  try {
    await tasksApi.delete(id)
    await load()
  } catch (e: unknown) {
    error.value = (e as Error).message
  }
}

const stateColors: Record<string, string> = {
  pending: 'text-gray-400',
  in_progress: 'text-blue-400',
  interrupted: 'text-yellow-400',
  completed: 'text-green-400',
}

onMounted(load)
</script>

<template>
  <div>
    <PageHeader title="Tasks" subtitle="Manage your task backlog" />
    <ErrorBanner v-if="error" :message="error" />

    <div class="px-6 py-4 flex justify-end">
      <button
        @click="showForm = !showForm"
        class="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-colors"
      >
        {{ showForm ? 'Cancel' : '+ New Task' }}
      </button>
    </div>

    <div v-if="showForm" class="mx-6 mb-6 p-5 bg-gray-900 border border-gray-800 rounded-xl">
      <h2 class="text-sm font-semibold mb-4 text-gray-300">New Task</h2>
      <TaskForm :loading="saving" @submit="createTask" @cancel="showForm = false" />
    </div>

    <LoadingSpinner v-if="loading" />

    <div v-else class="px-6 space-y-2">
      <div
        v-for="task in tasks"
        :key="task.id"
        class="flex items-center gap-4 px-4 py-3 bg-gray-900 border border-gray-800 rounded-xl hover:border-gray-700 transition-colors cursor-pointer"
        @click="router.push(`/tasks/${task.id}`)"
      >
        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium truncate">{{ task.title }}</p>
          <p class="text-xs text-gray-500 mt-0.5">
            D:{{ task.difficulty }} U:{{ task.urgency }} I:{{ task.importance }} · {{ task.estimated_duration }}min
          </p>
        </div>
        <span :class="['text-xs font-medium', stateColors[task.state] ?? 'text-gray-400']">
          {{ task.state }}
        </span>
        <span class="text-xs text-gray-600 bg-gray-800 px-2 py-0.5 rounded">{{ task.task_type }}</span>
        <button
          @click.stop="deleteTask(task.id)"
          class="text-gray-600 hover:text-red-400 transition-colors text-xs px-2"
        >✕</button>
      </div>

      <p v-if="!tasks.length" class="text-center text-gray-600 py-12 text-sm">
        No tasks yet. Create one above.
      </p>
    </div>
  </div>
</template>
