<script setup lang="ts">
import { ref } from 'vue'
import { schedulerApi, type ScheduleResult, type ScheduleDecision } from '../api/scheduler'
import PageHeader from '../components/PageHeader.vue'
import ErrorBanner from '../components/ErrorBanner.vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'

const today = new Date().toISOString().slice(0, 10)
const date = ref(today)
const dryRun = ref(true)
const result = ref<ScheduleResult | null>(null)
const loading = ref(false)
const error = ref('')
const confirming = ref<string | null>(null)

async function runScheduler() {
  loading.value = true
  error.value = ''
  result.value = null
  try {
    result.value = await schedulerApi.run(date.value, dryRun.value)
  } catch (e: unknown) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

async function confirmEntry(entryId: string) {
  confirming.value = entryId
  error.value = ''
  try {
    await schedulerApi.confirm(entryId)
  } catch (e: unknown) {
    error.value = (e as Error).message
  } finally {
    confirming.value = null
  }
}

const outcomeColors: Record<string, string> = {
  assigned: 'text-green-400 bg-green-900/30 border-green-800',
  skipped: 'text-yellow-400 bg-yellow-900/30 border-yellow-800',
  deferred: 'text-gray-400 bg-gray-800 border-gray-700',
}

function allDecisions(r: ScheduleResult): ScheduleDecision[] {
  return [...r.assigned, ...r.skipped, ...r.deferred]
}
</script>

<template>
  <div>
    <PageHeader title="Scheduler" subtitle="Assign tasks to free slots" />
    <ErrorBanner v-if="error" :message="error" />

    <div class="px-6 py-4 flex items-end gap-4 border-b border-gray-800">
      <div>
        <label class="block text-xs text-gray-400 mb-1">Date</label>
        <input v-model="date" type="date"
          class="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
      </div>
      <label class="flex items-center gap-2 text-sm text-gray-400 pb-2">
        <input v-model="dryRun" type="checkbox" class="rounded" />
        Dry run (preview only)
      </label>
      <button @click="runScheduler" :disabled="loading"
        class="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors">
        {{ loading ? 'Running…' : 'Run Scheduler' }}
      </button>
    </div>

    <LoadingSpinner v-if="loading" />

    <div v-else-if="result" class="px-6 py-4 space-y-4">
      <!-- Summary -->
      <div class="grid grid-cols-3 gap-3">
        <div class="bg-green-900/20 border border-green-900 rounded-xl p-4 text-center">
          <p class="text-2xl font-bold text-green-400">{{ result.assigned.length }}</p>
          <p class="text-xs text-gray-400 mt-1">Assigned</p>
        </div>
        <div class="bg-yellow-900/20 border border-yellow-900 rounded-xl p-4 text-center">
          <p class="text-2xl font-bold text-yellow-400">{{ result.skipped.length }}</p>
          <p class="text-xs text-gray-400 mt-1">Skipped</p>
        </div>
        <div class="bg-gray-800 border border-gray-700 rounded-xl p-4 text-center">
          <p class="text-2xl font-bold text-gray-400">{{ result.deferred.length }}</p>
          <p class="text-xs text-gray-400 mt-1">Deferred</p>
        </div>
      </div>

      <!-- Decision list -->
      <div class="space-y-2">
        <p class="text-xs text-gray-500 uppercase tracking-wide">Decisions</p>
        <div
          v-for="d in allDecisions(result)"
          :key="d.task_id + (d.slot?.start_time ?? '')"
          :class="['border rounded-xl px-4 py-3 text-sm', outcomeColors[d.outcome]]"
        >
          <div class="flex items-center justify-between">
            <span class="font-medium">{{ d.task_id.slice(0, 8) }}…</span>
            <div class="flex items-center gap-2">
              <span class="text-xs font-semibold uppercase">{{ d.outcome }}</span>
              <button
                v-if="d.outcome === 'assigned' && !dryRun"
                @click="confirmEntry(d.task_id)"
                :disabled="confirming === d.task_id"
                class="text-xs px-2 py-0.5 bg-green-700 hover:bg-green-600 disabled:opacity-50 rounded transition-colors"
              >
                {{ confirming === d.task_id ? '…' : 'Confirm' }}
              </button>
            </div>
          </div>
          <p class="text-xs mt-1 opacity-70">{{ d.reason }}</p>
          <div v-if="d.slot" class="text-xs mt-1 opacity-60">
            {{ d.slot.date }} {{ d.slot.start_time }}–{{ d.slot.end_time }}
          </div>
          <div class="text-xs mt-1 opacity-60 flex gap-3">
            <span>Priority: {{ d.priority_score.toFixed(2) }}</span>
            <span v-if="d.completion_probability != null">
              P: {{ (d.completion_probability * 100).toFixed(0) }}%
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
