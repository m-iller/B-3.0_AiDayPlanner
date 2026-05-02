<script setup lang="ts">
import { reactive } from 'vue'
import type { TaskCreateRequest } from '../api/tasks'

const props = defineProps<{
  initial?: Partial<TaskCreateRequest>
  loading?: boolean
}>()

const emit = defineEmits<{
  submit: [data: TaskCreateRequest]
  cancel: []
}>()

const form = reactive<TaskCreateRequest>({
  title: props.initial?.title ?? '',
  description: props.initial?.description ?? '',
  difficulty: props.initial?.difficulty ?? 5,
  urgency: props.initial?.urgency ?? 5,
  importance: props.initial?.importance ?? 5,
  estimated_duration: props.initial?.estimated_duration ?? 60,
  task_type: props.initial?.task_type ?? 'one_time',
  dependency_ids: props.initial?.dependency_ids ?? [],
  recurrence_rule: props.initial?.recurrence_rule ?? null,
})

function submit() {
  emit('submit', { ...form })
}
</script>

<template>
  <form @submit.prevent="submit" class="space-y-4">
    <div>
      <label class="block text-xs text-gray-400 mb-1">Title *</label>
      <input
        v-model="form.title"
        required
        class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
        placeholder="Task title"
      />
    </div>

    <div>
      <label class="block text-xs text-gray-400 mb-1">Description</label>
      <textarea
        v-model="form.description"
        rows="3"
        class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500 resize-none"
        placeholder="Markdown supported"
      />
    </div>

    <div class="grid grid-cols-3 gap-3">
      <div>
        <label class="block text-xs text-gray-400 mb-1">Difficulty (1–10)</label>
        <input v-model.number="form.difficulty" type="number" min="1" max="10"
          class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
      </div>
      <div>
        <label class="block text-xs text-gray-400 mb-1">Urgency (1–10)</label>
        <input v-model.number="form.urgency" type="number" min="1" max="10"
          class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
      </div>
      <div>
        <label class="block text-xs text-gray-400 mb-1">Importance (1–10)</label>
        <input v-model.number="form.importance" type="number" min="1" max="10"
          class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
      </div>
    </div>

    <div class="grid grid-cols-2 gap-3">
      <div>
        <label class="block text-xs text-gray-400 mb-1">Est. Duration (min)</label>
        <input v-model.number="form.estimated_duration" type="number" min="1"
          class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
      </div>
      <div>
        <label class="block text-xs text-gray-400 mb-1">Type</label>
        <select v-model="form.task_type"
          class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
          <option value="one_time">One-time</option>
          <option value="recurring">Recurring</option>
          <option value="no_date">No date</option>
        </select>
      </div>
    </div>

    <div class="flex gap-3 pt-2">
      <button
        type="submit"
        :disabled="loading"
        class="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors"
      >
        {{ loading ? 'Saving…' : 'Save' }}
      </button>
      <button
        type="button"
        @click="emit('cancel')"
        class="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm font-medium transition-colors"
      >
        Cancel
      </button>
    </div>
  </form>
</template>
