<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { tasksApi, type Task } from '../api/tasks'
import { learningApi, type CorrectionCoefficient } from '../api/learning'
import PageHeader from '../components/PageHeader.vue'
import ErrorBanner from '../components/ErrorBanner.vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'

const tasks = ref<Task[]>([])
const coefficients = ref<Record<string, CorrectionCoefficient>>({})
const loading = ref(false)
const error = ref('')
const resetReason = ref<Record<string, string>>({})
const resetting = ref<string | null>(null)

async function load() {
  loading.value = true
  error.value = ''
  try {
    tasks.value = await tasksApi.list()
    const results = await Promise.allSettled(
      tasks.value.map(t => learningApi.get(t.id).then(c => ({ id: t.id, c })))
    )
    for (const r of results) {
      if (r.status === 'fulfilled') {
        coefficients.value[r.value.id] = r.value.c
      }
    }
  } catch (e: unknown) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

async function reset(taskId: string) {
  const reason = resetReason.value[taskId]?.trim()
  if (!reason) { error.value = 'Reset reason required'; return }
  resetting.value = taskId
  error.value = ''
  try {
    coefficients.value[taskId] = await learningApi.reset(taskId, reason)
    resetReason.value[taskId] = ''
  } catch (e: unknown) {
    error.value = (e as Error).message
  } finally {
    resetting.value = null
  }
}

onMounted(load)
</script>

<template>
  <div>
    <PageHeader title="Learning" subtitle="Correction coefficients per task" />
    <ErrorBanner v-if="error" :message="error" />
    <LoadingSpinner v-if="loading" />

    <div v-else class="px-6 py-4 space-y-3">
      <div v-for="task in tasks" :key="task.id"
        class="p-4 bg-gray-900 border border-gray-800 rounded-xl">
        <div class="flex items-start justify-between">
          <div>
            <p class="text-sm font-medium">{{ task.title }}</p>
            <p class="text-xs text-gray-500 mt-0.5">
              Coefficient:
              <span class="text-white font-mono">
                {{ coefficients[task.id]?.coefficient.toFixed(3) ?? '—' }}
              </span>
              <span class="ml-2 text-gray-600">
                ({{ coefficients[task.id]?.session_count ?? 0 }} sessions)
              </span>
            </p>
          </div>
        </div>
        <div class="mt-3 flex gap-2">
          <input
            v-model="resetReason[task.id]"
            placeholder="Reset reason…"
            class="flex-1 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs focus:outline-none focus:border-blue-500"
          />
          <button
            @click="reset(task.id)"
            :disabled="resetting === task.id"
            class="px-3 py-1 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 rounded text-xs font-medium transition-colors"
          >
            {{ resetting === task.id ? '…' : 'Reset' }}
          </button>
        </div>
      </div>

      <p v-if="!tasks.length" class="text-center text-gray-600 py-12 text-sm">No tasks found.</p>
    </div>
  </div>
</template>
