<template>
  <div class="login-page fade-in">
    <div class="deco deco-a"></div>
    <div class="deco deco-b"></div>
    <div class="deco deco-c"></div>

    <section class="brand">
      <div class="brand-logo">
        <svg width="52" height="52" viewBox="0 0 24 24">
          <path fill="url(#lg)" d="M12 2 3 6v6c0 5 3.8 9.4 9 10 5.2-.6 9-5 9-10V6L12 2Zm0 3.2 6 2.7v6.1c0 3.5-2.5 6.8-6 7.4-3.5-.6-6-3.9-6-7.4V7.9l6-2.7Z" />
          <path fill="#0a1628" d="m8.2 11.6 2.4 2.4 5.2-5.3 1.4 1.4-6.6 6.7L6.8 13z" />
          <defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#e6c789" /><stop offset="1" stop-color="#c9a96e" />
          </linearGradient></defs>
        </svg>
        <span class="brand-name">
          <b class="gradient-title">智法通</b>
          <em>ZhiFaTong · Legal AI</em>
        </span>
      </div>

      <h1 class="slogan gradient-title">企业级智能法律顾问平台</h1>
      <p class="sub muted">以知识图谱与多智能体协同引擎，为每一家企业提供可靠、专业、可溯源的数智法治服务。</p>

      <ul class="highlights">
        <li>
          <span class="hl-ic"><el-icon><Cpu /></el-icon></span>
          <span class="hl-tx">
            <b>本地大模型 + 知识图谱</b>
            <i class="muted">私有化部署与法规知识推理结合，回答有法可依</i>
          </span>
        </li>
        <li>
          <span class="hl-ic"><el-icon><ChatDotRound /></el-icon></span>
          <span class="hl-tx">
            <b>多 Agent 对抗式合同审查</b>
            <i class="muted">多方角色交叉质证，逐条识别合同风险与责任条款</i>
          </span>
        </li>
        <li>
          <span class="hl-ic"><el-icon><Lock /></el-icon></span>
          <span class="hl-tx">
            <b>数据安全合规</b>
            <i class="muted">全链路加密与权限隔离，守护企业核心经营数据</i>
          </span>
        </li>
      </ul>

      <p class="legal muted">依法治企 · 行稳致远 —— 让每一次经营决策都有法律护航</p>
    </section>

    <section class="panel">
      <div class="glass-card form-card">
        <h2 class="form-title">欢迎登录</h2>
        <el-tabs v-model="tab" stretch class="form-tabs">
          <el-tab-pane label="登录" name="login">
            <el-form ref="loginRef" :model="login" :rules="loginRules" size="large" label-position="top">
              <el-form-item prop="username">
                <el-input v-model="login.username" placeholder="账号" :prefix-icon="User" clearable @keyup.enter="submitLogin" />
              </el-form-item>
              <el-form-item prop="password">
                <el-input
                  v-model="login.password" type="password" placeholder="密码" :prefix-icon="Lock"
                  show-password @keyup.enter="submitLogin"
                />
              </el-form-item>
              <el-button class="submit" type="primary" :loading="loading" @click="submitLogin">
                登 录
              </el-button>
            </el-form>

            <div class="demo-box">
              <div class="demo-tip muted">演示账号一键填入</div>
              <div class="demo-btns">
                <el-button v-for="d in demos" :key="d.username" size="small" round plain @click="fillDemo(d)">
                  {{ d.label }}
                </el-button>
              </div>
            </div>
          </el-tab-pane>

          <el-tab-pane label="注册" name="register">
            <el-form ref="regRef" :model="reg" :rules="regRules" size="large" label-position="top">
              <el-form-item prop="username">
                <el-input v-model="reg.username" placeholder="用户名（至少 3 个字符）" :prefix-icon="User" clearable />
              </el-form-item>
              <el-form-item prop="email">
                <el-input v-model="reg.email" placeholder="邮箱" :prefix-icon="Message" clearable />
              </el-form-item>
              <el-form-item prop="password">
                <el-input
                  v-model="reg.password" type="password" placeholder="密码（至少 8 位，含字母与数字）"
                  :prefix-icon="Lock" show-password @keyup.enter="submitRegister"
                />
              </el-form-item>
              <el-form-item prop="confirm">
                <el-input
                  v-model="reg.confirm" type="password" placeholder="确认密码" :prefix-icon="Lock"
                  show-password @keyup.enter="submitRegister"
                />
              </el-form-item>
              <el-button class="submit" type="primary" :loading="loading" @click="submitRegister">
                注 册
              </el-button>
            </el-form>
          </el-tab-pane>
        </el-tabs>
      </div>
      <p class="foot muted">智法通 © 2026 企业级智能法律顾问平台</p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { ChatDotRound, Cpu, Lock, Message, User } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const tab = ref('login')
const loading = ref(false)
const loginRef = ref<FormInstance>()
const regRef = ref<FormInstance>()

const login = reactive({ username: '', password: '' })
const reg = reactive({ username: '', email: '', password: '', confirm: '' })

const loginRules: FormRules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const regRules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 32, message: '用户名长度 3 ~ 32 个字符', trigger: 'blur' },
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: ['blur', 'change'] },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    {
      validator: (_r, v: string, cb: (e?: Error) => void) => {
        if (!/^(?=.*[A-Za-z])(?=.*\d)\S{8,}$/.test(v || '')) cb(new Error('密码需至少 8 位且同时包含字母与数字'))
        else cb()
      },
      trigger: ['blur', 'change'],
    },
  ],
  confirm: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_r, v: string, cb: (e?: Error) => void) => {
        if (v !== reg.password) cb(new Error('两次输入的密码不一致'))
        else cb()
      },
      trigger: ['blur', 'change'],
    },
  ],
}

const demos = [
  { label: '管理员 admin', username: 'admin', password: 'admin123' },
  { label: '法务 lawyer', username: 'lawyer', password: 'lawyer123' },
  { label: '普通 user', username: 'user', password: 'user123456' },
]

function fillDemo(d: { username: string; password: string }) {
  tab.value = 'login'
  login.username = d.username
  login.password = d.password
}

/** 成功后按角色跳转：管理员/法务 -> 工作台，普通用户 -> 法律问答 */
function homePath(): string {
  return userStore.isAdmin || userStore.isLawyer ? '/dashboard' : '/qa'
}

async function submitLogin() {
  if (loading.value) return
  const valid = await loginRef.value?.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await userStore.login(login.username, login.password)
    router.push(homePath())
  } catch {
    /* 错误已由 axios 拦截器统一提示 */
  } finally {
    loading.value = false
  }
}

async function submitRegister() {
  if (loading.value) return
  const valid = await regRef.value?.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await userStore.register({
      username: reg.username,
      email: reg.email,
      password: reg.password,
    })
    router.push(homePath())
  } catch {
    /* 错误已由 axios 拦截器统一提示 */
  } finally {
    loading.value = false
  }
}
</script>

<style lang="scss" scoped>
.login-page {
  position: relative;
  min-height: 100vh;
  display: flex;
  overflow: hidden;
  background:
    radial-gradient(900px 500px at 12% 8%, rgba(58, 122, 188, 0.18), transparent 60%),
    radial-gradient(760px 520px at 92% 100%, rgba(201, 169, 110, 0.14), transparent 60%),
    linear-gradient(135deg, #081120 0%, #0c1a30 48%, #12284a 100%);
}
.login-page::before {
  content: '';
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(90, 140, 200, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(90, 140, 200, 0.05) 1px, transparent 1px);
  background-size: 46px 46px;
  mask-image: radial-gradient(900px 600px at 25% 30%, #000 0%, transparent 75%);
  -webkit-mask-image: radial-gradient(900px 600px at 25% 30%, #000 0%, transparent 75%);
}
.deco { position: absolute; border-radius: 50%; filter: blur(1px); pointer-events: none; }
.deco-a { width: 340px; height: 340px; right: -120px; top: -120px; border: 1px solid rgba(201, 169, 110, 0.35); }
.deco-b { width: 240px; height: 240px; right: -70px; top: -70px; border: 1px dashed rgba(201, 169, 110, 0.4); }
.deco-c { width: 180px; height: 180px; left: 46%; bottom: -90px; background: rgba(201, 169, 110, 0.05); }

.brand {
  position: relative; z-index: 1;
  flex: 1.15;
  display: flex; flex-direction: column; justify-content: center;
  padding: 60px 7vw 60px 8vw;
}
.brand-logo { display: flex; align-items: center; gap: 14px; margin-bottom: 40px; }
.brand-logo svg { filter: drop-shadow(0 4px 14px rgba(201, 169, 110, 0.35)); }
.brand-name { display: flex; flex-direction: column; line-height: 1.1; }
.brand-name b { font-size: 30px; letter-spacing: 6px; font-weight: 700; }
.brand-name em { font-style: normal; font-size: 11px; color: var(--text-muted); letter-spacing: 2px; margin-top: 5px; }

.slogan { margin: 0 0 16px; font-size: clamp(30px, 3.4vw, 46px); font-weight: 700; letter-spacing: 2px; line-height: 1.25; }
.sub { margin: 0 0 34px; font-size: 15px; max-width: 520px; line-height: 1.9; }

.highlights { list-style: none; margin: 0 0 42px; padding: 0; display: grid; gap: 20px; max-width: 560px; }
.highlights li { display: flex; gap: 14px; align-items: flex-start; }
.hl-ic {
  width: 42px; height: 42px; flex: none;
  display: flex; align-items: center; justify-content: center;
  border-radius: 12px; color: var(--accent);
  background: var(--accent-soft);
  border: 1px solid rgba(201, 169, 110, 0.35);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
  font-size: 20px;
}
.hl-tx { display: flex; flex-direction: column; gap: 4px; }
.hl-tx b { font-size: 15px; }
.hl-tx i { font-style: normal; font-size: 13px; line-height: 1.6; }

.legal { margin: 0; font-size: 13px; letter-spacing: 4px; }

.panel {
  position: relative; z-index: 1;
  width: 440px; flex: none;
  display: flex; flex-direction: column; justify-content: center; align-items: center;
  padding: 40px 40px 24px;
}
.form-card { width: 100%; padding: 30px 30px 22px; border-radius: 20px; }
.form-title { margin: 0 0 4px; font-size: 20px; font-weight: 600; letter-spacing: 2px; }

.form-tabs :deep(.el-tabs__item) { color: var(--text-secondary); font-size: 15px; }
.form-tabs :deep(.el-tabs__item.is-active) { color: var(--accent); }
.form-tabs :deep(.el-tabs__active-bar) { background: linear-gradient(90deg, var(--accent), transparent); }
.form-tabs :deep(.el-tabs__nav-wrap::after) { background: var(--border); }

.submit {
  width: 100%; margin-top: 6px; letter-spacing: 8px; font-weight: 600;
  border: none; color: #fff;
  background: linear-gradient(135deg, var(--primary-light), var(--primary-lighter)) !important;
}
.submit:hover { filter: brightness(1.12); }

.demo-box { margin-top: 18px; padding-top: 14px; border-top: 1px dashed var(--border); }
.demo-tip { font-size: 12px; margin-bottom: 10px; }
.demo-btns { display: flex; flex-wrap: wrap; gap: 8px; }
.demo-btns :deep(.el-button) { margin: 0; }

.foot { margin: 14px 0 0; font-size: 12px; letter-spacing: 1px; }

@media (max-width: 960px) {
  .login-page { flex-direction: column; overflow: auto; }
  .brand { padding: 40px 28px 16px; }
  .legal, .sub { max-width: none; }
  .panel { width: 100%; padding: 20px; }
  .form-card { padding: 22px 20px; }
}
</style>
