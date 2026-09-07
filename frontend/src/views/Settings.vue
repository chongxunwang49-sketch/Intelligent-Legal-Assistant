<template>
  <div class="fade-in settings-page">
    <!-- 顶部个人信息卡 -->
    <div class="glass-card hero">
      <el-avatar :size="76" :src="user.userInfo?.avatar" class="hero-avatar">
        {{ initial }}
      </el-avatar>
      <div class="hero-info">
        <div class="hero-name">
          <b class="gradient-title">{{ user.userInfo?.username || '—' }}</b>
          <el-tag size="small" :type="tier === 'admin' ? 'warning' : tier === 'lawyer' ? 'success' : 'info'" effect="dark">
            {{ roleLabel }}
          </el-tag>
        </div>
        <div class="muted">{{ user.userInfo?.email || '未绑定邮箱' }}</div>
      </div>
      <div class="hero-right muted">
        账号 ID：{{ user.userInfo?.id }}
        <el-tag v-if="user.userInfo?.is_superuser" size="small" type="danger" effect="plain">超级管理员</el-tag>
      </div>
    </div>

    <!-- 主功能区 -->
    <div class="glass-card body-card">
      <el-tabs v-model="tab" tab-position="left" class="settings-tabs">
        <el-tab-pane name="profile">
          <template #label>
            <span class="tab-label"><el-icon><User /></el-icon> 个人信息</span>
          </template>

          <h3 class="section-title"><el-icon><EditPen /></el-icon>资料与头像</h3>
          <div class="pane-grid">
            <div class="avatar-block glass-card">
              <el-avatar :size="108" :src="user.userInfo?.avatar" class="big-avatar">
                {{ initial }}
              </el-avatar>
              <div class="avatar-ops">
                <el-upload
                  :show-file-list="false" accept="image/png,image/jpeg,image/gif,image/webp"
                  :http-request="doUploadAvatar" :before-upload="beforeAvatarUpload"
                >
                  <el-button size="small" plain><el-icon><UploadFilled /></el-icon>上传头像</el-button>
                </el-upload>
                <el-button v-if="user.userInfo?.avatar" size="small" type="danger" plain @click="removeAvatar">
                  <el-icon><Delete /></el-icon>删除头像
                </el-button>
              </div>
              <p class="muted tip">支持 png / jpg / gif / webp，不超过 5MB</p>
            </div>

            <el-form ref="profileRef" :model="profile" :rules="profileRules" label-width="72px" class="profile-form">
              <el-form-item label="邮箱" prop="email">
                <el-input v-model="profile.email" placeholder="请输入邮箱" clearable>
                  <template #prefix><el-icon><Message /></el-icon></template>
                </el-input>
              </el-form-item>
              <el-form-item label="手机" prop="phone">
                <el-input v-model="profile.phone" placeholder="请输入手机号（可选）" clearable>
                  <template #prefix><el-icon><Iphone /></el-icon></template>
                </el-input>
              </el-form-item>
              <el-form-item label="用户名" class="no-edit">
                <el-input :model-value="user.userInfo?.username" disabled />
              </el-form-item>
              <el-form-item label="注册时间">
                <el-input :model-value="fmtTime(user.userInfo?.created_at)" disabled />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="savingProfile" @click="saveProfile">保存修改</el-button>
              </el-form-item>
            </el-form>
          </div>
        </el-tab-pane>

        <el-tab-pane name="security">
          <template #label>
            <span class="tab-label"><el-icon><Lock /></el-icon> 安全设置</span>
          </template>

          <h3 class="section-title"><el-icon><Key /></el-icon>修改密码</h3>
          <el-form ref="pwdRef" :model="pwd" :rules="pwdRules" label-width="88px" class="pwd-form">
            <el-form-item label="原密码" prop="old_password">
              <el-input v-model="pwd.old_password" type="password" placeholder="请输入原密码" show-password />
            </el-form-item>
            <el-form-item label="新密码" prop="new_password">
              <el-input
                v-model="pwd.new_password" type="password" placeholder="至少 8 位，含字母与数字" show-password
              />
              <div class="pwd-tip muted">建议使用字母 + 数字组合，长度不少于 8 位</div>
            </el-form-item>
            <el-form-item label="确认密码" prop="confirm">
              <el-input v-model="pwd.confirm" type="password" placeholder="请再次输入新密码" show-password />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="savingPwd" @click="changePassword">确认修改</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane name="quota">
          <template #label>
            <span class="tab-label"><el-icon><Odometer /></el-icon> 用量信息</span>
          </template>

          <div class="quota-head">
            <h3 class="section-title"><el-icon><DataAnalysis /></el-icon>今日用量</h3>
            <el-button size="small" plain @click="loadQuota"><el-icon><RefreshRight /></el-icon>刷新</el-button>
          </div>

          <el-alert
            :closable="false" type="info" class="quota-alert"
            :title="tier === 'admin' ? '管理员不限次使用全部功能' : '普通用户按日限次，额度于每日 0 点自动重置'"
            :description="tier === 'admin'
              ? '当前账号为管理员，不受问答与合同审查的每日额度限制。'
              : (tier === 'lawyer'
                ? '法务负责人账号享有管理权限，问答 / 合同审查均按普通额度计次。'
                : '普通账号法律问答每日 50 次、合同审查每日 10 次，超出后当日暂停。')"
          />

          <div class="quota-cards">
            <div class="quota-card glass-card">
              <div class="qc-head">
                <span class="qc-ic"><el-icon><ChatDotRound /></el-icon></span>
                <div>
                  <b>法律问答</b>
                  <small class="muted">今日已用 / 上限</small>
                </div>
              </div>
              <template v-if="qaUnlimited">
                <div class="qc-num gold">不限次</div>
                <el-progress :percentage="100" :show-text="false" color="#46c07b" :stroke-width="8" />
                <p class="muted qc-tip">管理员 / 无限额账号，无每日次数限制</p>
              </template>
              <template v-else-if="qa">
                <div class="qc-num">
                  <em class="gold">{{ qa.used ?? 0 }}</em>
                  <span class="muted"> / {{ qa.limit ?? 0 }}</span>
                </div>
                <el-progress
                  :percentage="qaPercent" :show-text="false"
                  :color="qaPercent >= 90 ? '#e85d5d' : qaPercent >= 70 ? '#e6a23c' : '#46c07b'" :stroke-width="8"
                />
                <p class="muted qc-tip">剩余 {{ qa.remaining ?? 0 }} 次 · 每日 0 点重置</p>
              </template>
              <div v-else class="qc-num muted">加载中…</div>
            </div>

            <div class="quota-card glass-card">
              <div class="qc-head">
                <span class="qc-ic"><el-icon><DocumentChecked /></el-icon></span>
                <div>
                  <b>合同审查</b>
                  <small class="muted">按日限次</small>
                </div>
              </div>
              <template v-if="contractUnlimited">
                <div class="qc-num gold">不限次</div>
                <p class="muted qc-tip">管理员 / 无限额账号，无每日次数限制</p>
              </template>
              <template v-else>
                <div class="qc-num"><em class="gold">10</em><span class="muted"> 次 / 日</span></div>
                <el-progress :percentage="100" :show-text="false" color="#3a7abc" :stroke-width="8" :format="() => ''" />
                <p class="muted qc-tip">每份合同审查计入一次当日额度</p>
              </template>
            </div>
          </div>

          <el-descriptions :column="1" border class="quota-note">
            <el-descriptions-item label="普通用户">法律问答每日 50 次、合同审查每日 10 次，超额当日暂停，次日 0 点重置。</el-descriptions-item>
            <el-descriptions-item label="法务负责人">拥有数据分析与知识库管理等权限，功能额度按普通账号计次。</el-descriptions-item>
            <el-descriptions-item label="管理员">不设每日额度限制，全功能不限次使用。</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 底部退出登录 -->
    <div class="logout-bar">
      <el-button type="danger" plain @click="handleLogout">
        <el-icon><SwitchButton /></el-icon>退出登录
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import type { UploadRequestOptions } from 'element-plus'
import {
  ChatDotRound, DataAnalysis, Delete, DocumentChecked, EditPen, Iphone, Key, Lock,
  Message, Odometer, RefreshRight, SwitchButton, UploadFilled, User,
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { authApi } from '@/api/auth'
import { qaApi } from '@/api/qa'

const router = useRouter()
const user = useUserStore()

const tab = ref('profile')
const initial = computed(() => (user.userInfo?.username || '?').slice(0, 1).toUpperCase())
const roleLabel = computed(() =>
  user.isAdmin ? '管理员' : user.isLawyer ? '法务负责人' : '普通用户')
const tier = computed(() =>
  user.isAdmin ? 'admin' : user.isLawyer ? 'lawyer' : 'user')

function fmtTime(v?: string): string {
  if (!v) return '—'
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return v
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

/* ---------------- 个人信息 ---------------- */
const profileRef = ref<FormInstance>()
const savingProfile = ref(false)
const profile = reactive({ email: '', phone: '' })
watch(
  () => user.userInfo,
  (u) => {
    if (u) {
      profile.email = u.email || ''
      profile.phone = u.phone || ''
    }
  },
  { immediate: true },
)
const profileRules: FormRules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: ['blur', 'change'] },
  ],
  phone: [{ pattern: /^$|^1\d{10}$/, message: '请输入 11 位手机号', trigger: 'blur' }],
}

function beforeAvatarUpload(file: File): boolean {
  const ok = ['image/png', 'image/jpeg', 'image/gif', 'image/webp'].includes(file.type)
  if (!ok) ElMessage.warning('仅支持 png / jpg / gif / webp 图片')
  if (file.size > 5 * 1024 * 1024) {
    ElMessage.warning('头像大小不能超过 5MB')
    return false
  }
  return ok
}
async function doUploadAvatar(opts: UploadRequestOptions) {
  try {
    user.userInfo = await authApi.uploadAvatar(opts.file)
    ElMessage.success('头像已更新')
  } catch {
    /* 拦截器已提示 */
  }
}
async function removeAvatar() {
  try {
    user.userInfo = await authApi.deleteAvatar()
    ElMessage.success('头像已删除')
  } catch {
    /* 拦截器已提示 */
  }
}

async function saveProfile() {
  const valid = await profileRef.value?.validate().catch(() => false)
  if (!valid) return
  savingProfile.value = true
  try {
    user.userInfo = await authApi.updateMe({
      email: profile.email,
      phone: profile.phone,
    })
    ElMessage.success('个人信息已更新')
  } catch {
    /* 拦截器已提示 */
  } finally {
    savingProfile.value = false
  }
}

/* ---------------- 安全设置 ---------------- */
const pwdRef = ref<FormInstance>()
const savingPwd = ref(false)
const pwd = reactive({ old_password: '', new_password: '', confirm: '' })
const pwdRules: FormRules = {
  old_password: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    {
      validator: (_r, v: string, cb: (e?: Error) => void) => {
        if (!/^(?=.*[A-Za-z])(?=.*\d)\S{8,}$/.test(v || '')) cb(new Error('密码需至少 8 位且同时包含字母与数字'))
        else cb()
      },
      trigger: ['blur', 'change'],
    },
  ],
  confirm: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_r, v: string, cb: (e?: Error) => void) => {
        if (v !== pwd.new_password) cb(new Error('两次输入的密码不一致'))
        else cb()
      },
      trigger: ['blur', 'change'],
    },
  ],
}
async function changePassword() {
  const valid = await pwdRef.value?.validate().catch(() => false)
  if (!valid) return
  savingPwd.value = true
  try {
    await authApi.changePassword(pwd.old_password, pwd.new_password)
    ElMessage.success('密码修改成功')
    pwdRef.value?.resetFields()
  } catch {
    /* 拦截器已提示 */
  } finally {
    savingPwd.value = false
  }
}

/* ---------------- 用量信息 ---------------- */
interface QuotaResp {
  used?: number
  remaining?: number
  limit?: number
}
const qa = ref<QuotaResp | null>(null)
const qaUnlimited = computed(() => qa.value !== null && (qa.value.limit ?? -1) < 0)
const contractUnlimited = computed(() => tier.value === 'admin')
const qaPercent = computed(() => {
  const limit = qa.value?.limit
  if (!limit || limit < 0) return 0
  return Math.min(100, Math.round(((qa.value?.used ?? 0) / limit) * 100))
})
async function loadQuota() {
  try {
    qa.value = await qaApi.quota()
  } catch {
    qa.value = null
  }
}
watch(tab, (v) => {
  if (v === 'quota') loadQuota()
})

/* ---------------- 退出登录 ---------------- */
async function handleLogout() {
  await user.logout()
  router.push('/login')
}
</script>

<style lang="scss" scoped>
.settings-page { max-width: 1080px; margin: 0 auto; }

.hero { display: flex; align-items: center; gap: 20px; padding: 22px 26px; margin-bottom: 16px; }
.hero-avatar { flex: none; background: linear-gradient(135deg, var(--primary-light), var(--accent)); color: #fff; font-size: 26px; }
.hero-info { flex: 1; min-width: 0; }
.hero-name { display: flex; align-items: center; gap: 12px; margin-bottom: 6px; }
.hero-name b { font-size: 20px; letter-spacing: 1px; }
.hero-right { display: flex; flex-direction: column; align-items: flex-end; gap: 8px; font-size: 13px; }

.body-card { padding: 22px 26px 26px; }
.settings-tabs :deep(.el-tabs__header) { margin-right: 18px; }
.tab-label { display: inline-flex; align-items: center; gap: 8px; font-size: 15px; }

.pane-grid { display: grid; grid-template-columns: 220px 1fr; gap: 24px; }
.avatar-block { display: flex; flex-direction: column; align-items: center; gap: 16px; padding: 26px 18px; border-radius: 16px; }
.big-avatar { flex: none; background: linear-gradient(135deg, var(--primary-light), var(--accent)); color: #fff; font-size: 40px; }
.avatar-ops { display: flex; flex-direction: column; gap: 8px; align-items: center; }
.avatar-ops :deep(.el-button) { margin: 0; }
.avatar-block .tip { font-size: 12px; margin: 0; text-align: center; line-height: 1.6; }
.profile-form { max-width: 460px; }

.no-edit :deep(.el-input__inner) { color: var(--text-muted); }
.pwd-form { max-width: 460px; }
.pwd-tip { font-size: 12px; line-height: 1.6; margin-top: 4px; }

.quota-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.quota-head .section-title { margin: 0; }
.quota-alert { margin-bottom: 16px; }
.quota-cards { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
.quota-card { padding: 18px 20px; }
.qc-head { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.qc-head b { display: block; font-size: 15px; }
.qc-head small { font-size: 12px; }
.qc-ic {
  width: 42px; height: 42px; flex: none; border-radius: 12px; font-size: 20px;
  display: flex; align-items: center; justify-content: center; color: var(--accent);
  background: var(--accent-soft); border: 1px solid rgba(201, 169, 110, 0.35);
}
.qc-num { font-size: 16px; margin-bottom: 10px; }
.qc-num em { font-style: normal; font-size: 30px; font-weight: 700; }
.qc-num.gold { font-size: 24px; font-weight: 700; color: var(--accent); }
.qc-tip { margin: 10px 0 0; font-size: 12px; }
.quota-note { max-width: 760px; }

.logout-bar { display: flex; justify-content: center; padding: 18px 0 4px; }

@media (max-width: 720px) {
  .hero { flex-direction: column; text-align: center; }
  .hero-right { align-items: center; }
  .pane-grid { grid-template-columns: 1fr; }
  .quota-cards { grid-template-columns: 1fr; }
}
</style>
