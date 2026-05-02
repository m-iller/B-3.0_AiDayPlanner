import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/calendar' },
    {
      path: '/calendar',
      component: () => import('../views/CalendarView.vue'),
      meta: { title: 'Calendar' },
    },
    {
      path: '/tasks',
      component: () => import('../views/TasksView.vue'),
      meta: { title: 'Tasks' },
    },
    {
      path: '/tasks/:id',
      component: () => import('../views/TaskDetailView.vue'),
      meta: { title: 'Task Detail' },
    },
    {
      path: '/scheduler',
      component: () => import('../views/SchedulerView.vue'),
      meta: { title: 'Scheduler' },
    },
    {
      path: '/fatigue',
      component: () => import('../views/FatigueView.vue'),
      meta: { title: 'Fatigue' },
    },
    {
      path: '/tracking',
      component: () => import('../views/TrackingView.vue'),
      meta: { title: 'Time Tracker' },
    },
    {
      path: '/learning',
      component: () => import('../views/LearningView.vue'),
      meta: { title: 'Learning' },
    },
    {
      path: '/probability',
      component: () => import('../views/ProbabilityView.vue'),
      meta: { title: 'Probability' },
    },
  ],
})

router.afterEach((to) => {
  document.title = `${to.meta.title ?? 'AI Day Planner'} — AI Day Planner`
})

export default router
