import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'evolution',
      component: () => import('@/views/EvolutionPage.vue'),
    },
    {
      path: '/discovery',
      name: 'discovery',
      component: () => import('@/views/DiscoveryPage.vue'),
    },
    {
      path: '/finance-demo',
      name: 'finance-demo',
      component: () => import('@/views/FinanceCasePage.vue'),
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/',
    },
  ],
})

export default router
