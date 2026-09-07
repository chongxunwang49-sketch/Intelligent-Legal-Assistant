import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import '@/styles/global.scss'
import App from '@/App.vue'
import router from '@/router'
import { useUserStore } from '@/stores/user'
import { TOKEN_KEY } from '@/api/index'

// 应用保存的主题
const savedTheme = localStorage.getItem('zhifatong_theme') || 'default'
document.documentElement.setAttribute('data-theme', savedTheme)

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus)

async function bootstrap() {
  const root = document.getElementById('app-loading')
  if (localStorage.getItem(TOKEN_KEY)) {
    const store = useUserStore()
    try {
      await store.fetchUserInfo()
    } catch {
      localStorage.removeItem(TOKEN_KEY)
    }
  }
  await router.isReady()
  app.mount('#app')
  if (root) root.remove()
}

bootstrap()
