<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { calendarApi, type WeeklyView, type TimeBlockCreateRequest } from '../api/calendar'
import PageHeader from '../components/PageHeader.vue'
import ErrorBanner from '../components/ErrorBanner.vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'

const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function currentWeek(): { week: number; year: number } {
  const now = new Date()
  const start = new Date(now.getFullYear(), 0, 1)
  const week = Math.ceil(((now.getTime() - start.getTime()) / 86400000 + start.getDay() + 1) / 7)
  return { week, year: now.getFullYear() }
}

const { week: initWeek, year: initYear } = currentWeek()
const weekNum = ref(initWeek)
const year = ref(initYear)
const weekData = ref<WeeklyView | null>(null)
const loading = ref(false)
const error = ref('')
const showBlockForm = ref(false)
const blockForm = ref<TimeBlockCreateRequest>({
  day_of_week: 0,
  start_time: '09:00',
  end_time: '10:00',
  label: '',
  is_recurring: true,
})
const savingBlock = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  try {
    weekData.value = await calendarApi.getWeek(weekNum.value, year.value)
  } catch (e: unknown) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

async function deleteBlock(id: string) {
  if (!confirm('Delete this time block?')) return
  try {
    await calendarApi.deleteBlock(id)
    await load()
  } catch (e: unknown) {
    error.value = (e as Error).message
  }
}

async function createBlock() {
  savingBlock.value = true
  error.value = ''
  try {
    await calendarApi.createBlock(blockForm.value)
    showBlockForm.value = false
    await load()
  } catch (e: unknown) {
    error.value = (e as Error).message
  } finally {
    savingBlock.value = false
  }
}

function prevWeek() { weekNum.value--; load() }
function nextWeek() { weekNum.value++; load() }

const blocksByDay = computed(() => {
  const map: Record<number, typeof weekData.value extends null ? never : WeeklyView['time_blocks']> = {}
  if (!weekData.value) return map
  for (const b of weekData.value.time_blocks) {
    if (!map[b.day_of_week]) map[b.day_of_week] = []
    map[b.day_of_week].push(b)
  }
  return map
})

onMounted(load)
</script>

<template>
  <div>
    <PageHeader title="Calendar" :subtitle="`Week ${weekNum}, ${year}`" />
    <ErrorBanner v-if="error" :message="error" />

    <!-- Week nav -->
    <div class="px-6 py-3 flex items-center gap-4 border-b border-gray-800">
      <button @click="prevWeek" class="text-gray-400 hover:text-white px-2 py-1 rounded hover:bg-gray-800 text-sm">← Prev</button>
      <span class="text-sm text-gray-300">Week {{ weekNum }} / {{ year }}</span>
      <button @click="nextWeek" class="text-gray-400 hover:text-white px-2 py-1 rounded hover:bg-gray-800 text-sm">Next →</button>
      <div class="flex-1" />
      <button @click="showBlockForm = !showBlockForm"
        class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 rounded text-xs font-medium transition-colors">
        + Time Block
      </button>
    </div>

    <!-- Block form -->
    <div v-if="showBlockForm" class="mx-6 mt-4 p-5 bg-gray-900 border border-gray-800 rounded-xl">
      <h2 class="text-sm font-semibold mb-4 text-gray-300">New Time Block</h2>
      <form @submit.prevent="createBlock" class="grid grid-cols-2 gap-3">
        <div>
          <label class="block text-xs text-gray-400 mb-1">Day</label>
          <select v-model.number="blockForm.day_of_week"
            class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
            <option v-for="(d, i) in DAY_NAMES" :key="i" :value="i">{{ d }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1">Label</label>
          <input v-model="blockForm.label" required
            class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1">Start</label>
          <input v-model="blockForm.start_time" type="time"
            class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1">End</label>
          <input v-model="blockForm.end_time" type="time"
            class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
        </div>
        <div class="col-span-2 flex items-center gap-2">
          <input v-model="blockForm.is_recurring" type="checkbox" id="recurring" class="rounded" />
          <label for="recurring" class="text-xs text-gray-400">Recurring weekly</label>
        </div>
        <div class="col-span-2 flex gap-3">
          <button type="submit" :disabled="savingBlock"
            class="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors">
            {{ savingBlock ? 'Saving…' : 'Save' }}
          </button>
          <button type="button" @click="showBlockForm = false"
            class="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm font-medium transition-colors">
            Cancel
          </button>
        </div>
      </form>
    </div>

    <LoadingSpinner v-if="loading" />

    <!-- Week grid -->
    <div v-else-if="weekData" class="px-6 py-4 grid grid-cols-7 gap-2">
      <div v-for="(day, idx) in DAY_NAMES" :key="idx" class="space-y-2">
        <p class="text-xs font-semibold text-gray-500 text-center uppercase">{{ day }}</p>

        <!-- Time blocks -->
        <div v-for="block in (blocksByDay[idx] ?? [])" :key="block.id"
          class="bg-red-900/40 border border-red-800 rounded-lg px-2 py-1.5 text-xs group relative">
          <p class="font-medium text-red-300 truncate">{{ block.label }}</p>
          <p class="text-red-400/70">{{ block.start_time }}–{{ block.end_time }}</p>
          <button @click="deleteBlock(block.id)"
            class="absolute top-1 right-1 hidden group-hover:block text-red-400 hover:text-red-200 text-xs">✕</button>
        </div>

        <!-- Free slots -->
        <div v-for="slot in (weekData.free_slots[Object.keys(weekData.free_slots)[idx]] ?? [])" :key="slot.start_time"
          class="bg-green-900/20 border border-green-900 rounded-lg px-2 py-1.5 text-xs">
          <p class="text-green-400/80">{{ slot.start_time }}–{{ slot.end_time }}</p>
          <p class="text-green-600">{{ slot.duration_minutes }}min free</p>
        </div>

        <p v-if="!blocksByDay[idx]?.length" class="text-xs text-gray-700 text-center py-2">—</p>
      </div>
    </div>
  </div>
</template>
