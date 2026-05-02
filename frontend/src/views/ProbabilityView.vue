<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { tasksApi, type Task } from '../api/tasks'
import { probabilityApi, type DayAggregate } from '../api/probability'
import PageHeader from '../components/PageHeader.vue'
import ErrorBanner from '../components/ErrorBanner.vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'

const today = new Date().toISOString().slice(0, 10)
const date = ref(today)
const tasks = ref<Task[]>([])
const dayAggregate = ref<DayAggregate | null>(null)
const loading = ref(false)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [t, agg] = await Promise.all([
      tasksApi.list(),
      probabilityApi.forDay(date.value),
    ])
    tasks.value = t
    dayAggregate.value = agg
  } catch (e: unknown) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

function pctColor(p: number) {
  if (p >= 0.7) return 'text-green-400'
  if (p >= 0.4) return 'text-yellow-400'
  return 'text-red-400'
}

onMounted(load)
</script>

<template>
  <div>
    <PageHeader title="Probability" subtitle="Completion likelihood per task and day" />
    <ErrorBanner v-if="error" :message="error" />

    <div class="px-6 py-4 flex items-end gap-4 border-b border-gray-800">
      <div>
        <label class="block text-xs text-gray-400 mb-1">Date</label>
        <input v-model="date" type="date" @change="load"
          class="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
      </div>
    </div>

    <LoadingSpinner v-if="loading" />

    <div v-else class="px-6 py-5 space-y-5">
      <!-- Day aggregate -->
      <div v-if="dayAggregate"
        :class="['p-5 border rounded-xl text-center', dayAggregate.overload_warning ? 'bg-red-900/20 border-red-800' : 'bg-gray-900 border-gray-800']">
        <p class="text-xs text-gray-500 uppercase tracking-wide mb-1">Day Aggregate</p>
        <p :class="['text-5xl font-bold', pctColor(dayAggregate.aggregate_probability)]">
          {{ (dayAggregate.aggregate_probability * 100).toFixed(0) }}%
        </p>
        <p v-if="dayAggregate.overload_warning" class="text-xs text-red-400 mt-2 font-medium">
          ⚠ Overload warning — day is too packed
        </p>
      </div>

      <!-- Per-task probabilities -->
      <div v-if="dayAggregate?.task_probabilities?.length">
        <p class="text-xs text-gray-500 uppercase tracking-wide mb-2">Per-Task</p>
        <div class="space-y-2">
          <div v-for="tp in dayAggregate.task_probabilities" :key="tp.task_id"
            class="flex items-center justify-between px-4 py-3 bg-gray-900 border border-gray-800 rounded-xl text-sm">
            <span class="text-gray-300 truncate flex-1">
              {{ tasks.find(t => t.id === tp.task_id)?.title ?? tp.task_id.slice(0, 8) + '…' }}
            </span>
            <span :class="['font-bold ml-4', pctColor(tp.probability)]">
              {{ (tp.probability * 100).toFixed(0) }}%
            </span>
          </div>
        </div>
      </div>

      <p v-else-if="!loading" class="text-center text-gray-600 text-sm py-8">
        No scheduled tasks for this date.
      </p>
    </div>
  </div>
</template>
