<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { fatigueApi, type FatigueRecord, type FatigueAuditEntry } from '../api/fatigue'
import PageHeader from '../components/PageHeader.vue'
import ErrorBanner from '../components/ErrorBanner.vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'

const today = new Date().toISOString().slice(0, 10)
const date = ref(today)
const record = ref<FatigueRecord | null>(null)
const auditLog = ref<FatigueAuditEntry[]>([])
const loading = ref(false)
const error = ref('')
const overrideScore = ref(50)
const overrideReason = ref('')
const overriding = ref(false)
const showOverride = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await fatigueApi.getForDate(date.value)
    record.value = data.record
    auditLog.value = data.audit_log
  } catch (e: unknown) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

async function submitOverride() {
  if (!overrideReason.value.trim()) {
    error.value = 'Override reason is required'
    return
  }
  overriding.value = true
  error.value = ''
  try {
    await fatigueApi.override(date.value, overrideScore.value, overrideReason.value)
    showOverride.value = false
    overrideReason.value = ''
    await load()
  } catch (e: unknown) {
    error.value = (e as Error).message
  } finally {
    overriding.value = false
  }
}

const scoreColor = computed(() => {
  const s = record.value?.score ?? 0
  if (s >= 75) return 'text-red-400'
  if (s >= 50) return 'text-yellow-400'
  return 'text-green-400'
})

const scoreBarWidth = computed(() => `${record.value?.score ?? 0}%`)

onMounted(load)
</script>

<template>
  <div>
    <PageHeader title="Fatigue" subtitle="Track your daily energy level" />
    <ErrorBanner v-if="error" :message="error" />

    <div class="px-6 py-4 flex items-end gap-4 border-b border-gray-800">
      <div>
        <label class="block text-xs text-gray-400 mb-1">Date</label>
        <input v-model="date" type="date" @change="load"
          class="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
      </div>
      <button @click="showOverride = !showOverride"
        class="px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm font-medium transition-colors">
        Manual Override
      </button>
    </div>

    <!-- Override form -->
    <div v-if="showOverride" class="mx-6 mt-4 p-5 bg-gray-900 border border-gray-800 rounded-xl">
      <h2 class="text-sm font-semibold mb-4 text-gray-300">Override Fatigue Score</h2>
      <div class="space-y-3">
        <div>
          <label class="block text-xs text-gray-400 mb-1">Score (1–100): {{ overrideScore }}</label>
          <input v-model.number="overrideScore" type="range" min="1" max="100" class="w-full" />
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1">Reason *</label>
          <input v-model="overrideReason" required
            class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
            placeholder="Why are you overriding?" />
        </div>
        <div class="flex gap-3">
          <button @click="submitOverride" :disabled="overriding"
            class="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors">
            {{ overriding ? 'Saving…' : 'Apply' }}
          </button>
          <button @click="showOverride = false"
            class="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm font-medium transition-colors">
            Cancel
          </button>
        </div>
      </div>
    </div>

    <LoadingSpinner v-if="loading" />

    <div v-else-if="record" class="px-6 py-5 space-y-6">
      <!-- Score display -->
      <div class="p-6 bg-gray-900 border border-gray-800 rounded-xl text-center">
        <p class="text-xs text-gray-500 uppercase tracking-wide mb-2">Fatigue Score</p>
        <p :class="['text-6xl font-bold', scoreColor]">{{ record.score }}</p>
        <p class="text-xs text-gray-500 mt-1">/ 100</p>
        <div class="mt-4 h-2 bg-gray-800 rounded-full overflow-hidden">
          <div :class="['h-full rounded-full transition-all', record.score >= 75 ? 'bg-red-500' : record.score >= 50 ? 'bg-yellow-500' : 'bg-green-500']"
            :style="{ width: scoreBarWidth }" />
        </div>
      </div>

      <!-- Audit log -->
      <div v-if="auditLog.length">
        <p class="text-xs text-gray-500 uppercase tracking-wide mb-2">Audit Log</p>
        <div class="space-y-2">
          <div v-for="entry in auditLog" :key="entry.id"
            class="flex items-center justify-between px-4 py-2 bg-gray-900 border border-gray-800 rounded-lg text-xs">
            <span class="text-gray-400">{{ entry.cause }}</span>
            <span class="text-gray-500">{{ entry.old_score }} → <span class="text-white">{{ entry.new_score }}</span></span>
            <span class="text-gray-600">{{ entry.created_at.slice(0, 16) }}</span>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="!loading" class="px-6 py-12 text-center text-gray-600 text-sm">
      No fatigue record for this date.
    </div>
  </div>
</template>
