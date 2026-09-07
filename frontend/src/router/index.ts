import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { TOKEN_KEY } from '@/api/index'

const routes: RouteRecordRaw[] = [
  { path: '/login', name: 'login', component: () => import('@/views/Login.vue'), meta: { public: true } },
  { path: '/', redirect: () => (canAnalysis() ? '/dashboard' : '/qa') },
  { path: '/dashboard', name: 'dashboard', component: () => import('@/views/Dashboard.vue'), meta: { roles: ['admin', 'legal_admin'], title: '工作台' } },
  { path: '/qa', name: 'qa', component: () => import('@/views/QA.vue'), meta: { roles: ['admin', 'legal_admin', 'user'], title: '法律问答' } },
  { path: '/contract', name: 'contract', component: () => import('@/views/Contract.vue'), meta: { roles: ['admin', 'legal_admin', 'user'], title: '合同审查' } },
  { path: '/knowledge', name: 'knowledge', component: () => import('@/views/Knowledge.vue'), meta: { roles: ['admin', 'legal_admin', 'user'], title: '法规知识库' } },
  { path: '/analysis', name: 'analysis', component: () => import('@/views/Analysis.vue'), meta: { roles: ['admin', 'legal_admin'], title: '数据分析' } },
  { path: '/users', name: 'users', component: () => import('@/views/UserManagement.vue'), meta: { roles: ['admin'], title: '用户管理' } },
  { path: '/settings', name: 'settings', component: () => import('@/views/Settings.vue'), meta: { roles: ['admin', 'legal_admin', 'user'], title: '个人中心' } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

function canAnalysis() {
  const u = useUserStore()
  return u.isAdmin || u.isLawyer
}

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to) => {
  const hasToken = !!localStorage.getItem(TOKEN_KEY)
  const store = useUserStore()
  if (to.meta.public) {
    if (hasToken && to.path === '/login') return canAnalysis() ? '/dashboard' : '/qa'
    return true
  }
  if (!hasToken) return '/login'
  if (!store.userInfo) {
    try {
      await store.fetchUserInfo()
    } catch {
      return '/login'
    }
  }
  const roles = to.meta.roles as string[] | undefined
  if (roles && !store.hasRole(roles)) {
    return canAnalysis() ? '/dashboard' : '/qa'
  }
  return true
})

export default router
