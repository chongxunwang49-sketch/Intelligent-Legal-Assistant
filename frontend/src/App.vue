<template>
  <router-view v-if="isLoginPage" />
  <el-container v-else class="layout">
    <el-aside :width="collapsed ? '64px' : '240px'" class="sidebar">
      <div class="logo" @click="$router.push('/')">
        <svg width="26" height="26" viewBox="0 0 24 24"><path fill="#c9a96e" d="M12 2 3 6v6c0 5 3.8 9.4 9 10 5.2-.6 9-5 9-10V6L12 2Zm0 3.2 6 2.7v6.1c0 3.5-2.5 6.8-6 7.4-3.5-.6-6-3.9-6-7.4V7.9l6-2.7Z"/></svg>
        <span v-show="!collapsed" class="logo-text gradient-title">智法通</span>
      </div>
      <el-menu :default-active="route.path" router class="menu" :collapse="collapsed">
        <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">
          <el-icon><component :is="m.icon" /></el-icon>
          <template #title>{{ m.title }}</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-left">
          <el-icon class="collapse-btn" @click="collapsed = !collapsed"><Expand v-if="collapsed" /><Fold v-else /></el-icon>
          <span class="page-title">{{ route.meta.title || '' }}</span>
        </div>
        <div class="header-right">
          <el-dropdown trigger="click" @command="applyTheme">
            <span class="head-btn"><el-icon><Brush /></el-icon> 主题</span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-for="t in themes" :key="t.value" :command="t.value">{{ t.label }}</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>

          <el-popover placement="bottom-end" :width="320" trigger="click" @show="notify.fetchList()">
            <template #reference>
              <span class="head-btn"><el-badge :value="notify.unreadCount" :hidden="!notify.unreadCount" :max="99"><el-icon><Bell /></el-icon></el-badge></span>
            </template>
            <div class="notify-panel">
              <div class="notify-head"><b>通知</b><el-button link type="primary" @click="notify.markAll()">全部已读</el-button></div>
              <el-scrollbar height="260px">
                <div v-for="n in notify.items" :key="n.id" class="notify-item" :class="{ unread: !n.is_read }" @click="notify.markRead(n.id)">
                  <div class="notify-title">{{ n.title }}</div>
                  <div class="muted">{{ n.content }}</div>
                </div>
                <el-empty v-if="!notify.items.length" description="暂无通知" :image-size="60" />
              </el-scrollbar>
            </div>
          </el-popover>

          <el-dropdown trigger="click" @command="onUserCommand">
            <span class="head-btn user">
              <el-avatar :size="28" :src="user.userInfo?.avatar">{{ (user.userInfo?.username || '?').slice(0, 1).toUpperCase() }}</el-avatar>
              <span class="uname">{{ user.userInfo?.username }}</span>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled>{{ roleLabel }}</el-dropdown-item>
                <el-dropdown-item command="settings">个人中心</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Bell, Brush, ChatDotRound, DataAnalysis, DocumentChecked, Expand, Fold, Odometer, Reading, Setting, User, UserFilled,
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { useNotificationStore } from '@/stores/notification'

const route = useRoute()
const router = useRouter()
const user = useUserStore()
const notify = useNotificationStore()
const collapsed = ref(false)
const isLoginPage = computed(() => route.path === '/login')

const themes = [
  { value: 'default', label: '深邃星空' },
  { value: 'ink', label: '墨韵商务' },
  { value: 'aurora', label: '极光暗夜' },
  { value: 'forest', label: '青松绿野' },
]

const allMenus = [
  { path: '/dashboard', title: '工作台', icon: Odometer, roles: ['admin', 'legal_admin'] },
  { path: '/qa', title: '法律问答', icon: ChatDotRound, roles: ['admin', 'legal_admin', 'user'] },
  { path: '/contract', title: '合同审查', icon: DocumentChecked, roles: ['admin', 'legal_admin', 'user'] },
  { path: '/knowledge', title: '法规知识库', icon: Reading, roles: ['admin', 'legal_admin', 'user'] },
  { path: '/analysis', title: '数据分析', icon: DataAnalysis, roles: ['admin', 'legal_admin'] },
  { path: '/users', title: '用户管理', icon: User, roles: ['admin'] },
  { path: '/settings', title: '个人中心', icon: Setting, roles: ['admin', 'legal_admin', 'user'] },
]
const menus = computed(() => allMenus.filter((m) => user.hasRole(m.roles)))
const roleLabel = computed(() => (user.isAdmin ? '超级管理员' : user.isLawyer ? '法务负责人' : '普通用户'))

function applyTheme(v: string) {
  document.documentElement.setAttribute('data-theme', v)
  localStorage.setItem('zhifatong_theme', v)
}
async function onUserCommand(cmd: string) {
  if (cmd === 'settings') router.push('/settings')
  else if (cmd === 'logout') {
    await user.logout()
    router.push('/login')
  }
}
</script>

<style lang="scss" scoped>
.layout { height: 100vh; background: var(--bg-primary); }
.sidebar {
  background: var(--bg-sidebar); border-right: 1px solid var(--border);
  display: flex; flex-direction: column; transition: width .2s;
}
.logo { height: var(--header-height); display: flex; align-items: center; gap: 10px; padding: 0 18px; cursor: pointer; }
.logo-text { font-size: 20px; font-weight: 700; letter-spacing: 2px; }
.menu { border-right: none; background: transparent; --el-menu-bg-color: transparent; --el-menu-text-color: var(--text-secondary); --el-menu-active-color: var(--accent); --el-menu-hover-bg-color: rgba(255,255,255,.05); }
.header { height: var(--header-height); display: flex; align-items: center; justify-content: space-between; background: var(--bg-header); border-bottom: 1px solid var(--border); backdrop-filter: blur(10px); }
.header-left { display: flex; align-items: center; gap: 12px; }
.collapse-btn { cursor: pointer; font-size: 20px; color: var(--text-secondary); }
.page-title { font-size: 16px; font-weight: 600; color: var(--text-primary); }
.header-right { display: flex; align-items: center; gap: 16px; }
.head-btn { display: inline-flex; align-items: center; gap: 6px; color: var(--text-secondary); cursor: pointer; font-size: 14px; }
.head-btn:hover { color: var(--accent); }
.head-btn.user { gap: 8px; }
.uname { color: var(--text-primary); }
.content { background: transparent; overflow: auto; padding: 18px; }
.notify-panel { padding: 4px; }
.notify-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.notify-item { padding: 8px 10px; border-radius: 8px; cursor: pointer; border-bottom: 1px solid var(--border); }
.notify-item:hover { background: rgba(255,255,255,.04); }
.notify-item.unread .notify-title { color: var(--accent); }
.notify-title { font-weight: 600; }
</style>
