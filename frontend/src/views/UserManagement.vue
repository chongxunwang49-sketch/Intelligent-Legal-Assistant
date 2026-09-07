<template>
  <div class="fade-in um-page">
    <!-- 筛选栏 -->
    <div class="glass-card toolbar">
      <div class="filters">
        <el-input
          v-model="filters.keyword" placeholder="搜索用户名 / 邮箱 / 手机号" clearable style="width: 230px"
          :prefix-icon="Search" @keyup.enter="handleSearch" @clear="handleSearch"
        />
        <el-select v-model="filters.role" placeholder="角色" clearable style="width: 150px" @change="handleSearch">
          <el-option v-for="r in roleOptions" :key="r.code" :label="r.name" :value="r.code" />
        </el-select>
        <el-select v-model="filters.status" placeholder="状态" clearable style="width: 140px" @change="handleSearch">
          <el-option label="正常" value="active" />
          <el-option label="已禁用" value="disabled" />
        </el-select>
        <el-button @click="handleSearch"><el-icon><Search /></el-icon>查询</el-button>
        <el-button plain @click="resetFilters"><el-icon><RefreshLeft /></el-icon>重置</el-button>
      </div>
      <el-button type="primary" @click="openCreate">
        <el-icon><Plus /></el-icon>新建用户
      </el-button>
    </div>

    <!-- 用户列表 -->
    <div class="glass-card table-card">
      <el-table v-loading="loading" :data="users" row-key="id">
        <el-table-column prop="id" label="ID" width="70" align="center" />
        <el-table-column prop="username" label="用户名" min-width="130" show-overflow-tooltip />
        <el-table-column prop="email" label="邮箱" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ row.email || '—' }}</template>
        </el-table-column>
        <el-table-column label="角色" min-width="150">
          <template #default="{ row }">
            <template v-for="name in roleNames(row)" :key="name">
              <el-tag
                size="small" effect="dark" class="role-tag"
                :type="roleTagType(row, name)"
              >{{ name }}</el-tag>
            </template>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.is_active ? 'success' : 'danger'">
              {{ row.is_active ? '正常' : '已禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最后登录" width="165">
          <template #default="{ row }">{{ fmtTime(row.last_login) }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="165">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <div class="ops">
              <el-button link type="primary" @click="openEdit(row)"><el-icon><EditPen /></el-icon>编辑</el-button>
              <el-button link type="warning" @click="openReset(row)"><el-icon><Key /></el-icon>重置密码</el-button>
              <el-tooltip v-if="isSelf(row) && row.is_active" content="不能禁用自己" placement="top">
                <span><el-button link type="danger" disabled><el-icon><CircleClose /></el-icon>禁用</el-button></span>
              </el-tooltip>
              <el-button v-else-if="row.is_active" link type="danger" @click="toggleStatus(row, false)">
                <el-icon><CircleClose /></el-icon>禁用
              </el-button>
              <el-button v-else link type="success" @click="toggleStatus(row, true)">
                <el-icon><CircleCheck /></el-icon>启用
              </el-button>
              <el-tooltip v-if="isSelf(row)" content="不能删除自己的账号" placement="top">
                <span><el-button link type="danger" disabled><el-icon><Delete /></el-icon>删除</el-button></span>
              </el-tooltip>
              <el-button v-else link type="danger" @click="removeUser(row)">
                <el-icon><Delete /></el-icon>删除
              </el-button>
            </div>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无用户" :image-size="90" />
        </template>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="page" v-model:page-size="pageSize" :total="total"
          :page-sizes="[10, 20, 50, 100]" layout="total, sizes, prev, pager, next, jumper" background
          @current-change="loadList" @size-change="handleSizeChange"
        />
      </div>
    </div>

    <!-- 新建用户 -->
    <el-dialog v-model="createVisible" title="新建用户" width="460px" destroy-on-close>
      <el-form ref="createRef" :model="createForm" :rules="createRules" label-width="84px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="createForm.username" placeholder="3 ~ 32 个字符" clearable />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="createForm.email" placeholder="登录 / 找回密码使用" clearable />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="createForm.password" type="password" placeholder="至少 6 位，勿使用弱口令" show-password />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="createForm.phone" placeholder="选填" clearable />
        </el-form-item>
        <el-alert :closable="false" type="info" title="新建用户默认分配「普通用户」角色，创建后可再调整其角色。" />
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingCreate" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 编辑：角色 + 资料 -->
    <el-dialog v-model="editVisible" title="编辑用户" width="480px" destroy-on-close>
      <el-alert
        v-if="isSelf(editingRow)" :closable="false" type="warning" show-icon class="self-alert"
        title="该账号是您本人：不能移除自己的管理员角色，也不能被禁用或删除（后端会拒绝）。"
      />
      <el-form ref="editRef" :model="editForm" :rules="editRules" label-width="84px">
        <el-form-item label="用户名">
          <el-input :model-value="editForm.username" disabled />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="editForm.email" clearable />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="editForm.phone" clearable />
        </el-form-item>
        <el-form-item label="角色">
          <el-checkbox-group v-model="editForm.roleCodes" class="role-checks">
            <el-checkbox v-for="r in roleOptions" :key="r.code" :value="r.code">
              <span class="check-item"><b>{{ r.name }}</b><i class="muted">{{ r.description || r.code }}</i></span>
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingEdit" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码 -->
    <el-dialog v-model="resetVisible" title="重置密码" width="420px" destroy-on-close>
      <el-alert
        :closable="false" type="info" show-icon class="self-alert"
        :title="`将重置「${resetForm.username}」的登录密码，请为其设置新的初始密码。`"
      />
      <el-form ref="resetRef" :model="resetForm" :rules="resetRules" label-width="84px" class="reset-form">
        <el-form-item label="新密码" prop="new_password">
          <el-input v-model="resetForm.new_password" type="password" placeholder="至少 6 位，勿使用弱口令" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingReset" @click="submitReset">确认重置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import {
  CircleCheck, CircleClose, Delete, EditPen, Key, Plus, RefreshLeft, Search,
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { userApi } from '@/api/user'

interface RoleItem {
  id: number
  name: string
  code: string
  description?: string
  is_default?: boolean
  permission_codes?: string[]
}
interface UserRow {
  id: number
  username: string
  email: string
  phone?: string | null
  avatar?: string | null
  is_active: boolean
  is_superuser: boolean
  last_login?: string | null
  created_at?: string | null
  roles: RoleItem[]
}

const userStore = useUserStore()
const myId = computed(() => userStore.userInfo?.id)
const isSelf = (row: UserRow) => !!myId.value && row.id === myId.value

/* ---------------- 列表与筛选 ---------------- */
const loading = ref(false)
const users = ref<UserRow[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const filters = reactive({ keyword: '', role: '', status: '' })

const FALLBACK_ROLES: RoleItem[] = [
  { id: 1, name: '超级管理员', code: 'admin', description: '拥有全部权限，可管理用户与系统' },
  { id: 2, name: '法务负责人', code: 'legal_admin', description: '业务功能 + 数据分析 + 知识库管理' },
  { id: 3, name: '普通用户', code: 'user', description: '法律问答 / 合同审查 / 法规检索' },
]
const roleList = ref<RoleItem[]>([])
const roleOptions = computed<RoleItem[]>(() => (roleList.value.length ? roleList.value : FALLBACK_ROLES))

function fmtTime(v?: string | null): string {
  if (!v) return '—'
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return v
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

function roleNames(row: UserRow): string[] {
  const names = row.roles.map((r) => r.name).filter(Boolean)
  if (row.is_superuser && !names.includes('超级管理员')) names.unshift('超级管理员')
  return names
}
function roleTagType(row: UserRow, name: string): 'warning' | 'success' | 'info' | 'danger' {
  if (name === '超级管理员') return 'danger'
  const code = row.roles.find((r) => r.name === name)?.code
  if (code === 'legal_admin') return 'success'
  return 'info'
}

async function loadRoles() {
  try {
    roleList.value = await userApi.roles()
  } catch {
    /* 兜底常量 */
  }
}
async function loadList() {
  loading.value = true
  try {
    const resp = await userApi.list({
      page: page.value,
      page_size: pageSize.value,
      keyword: filters.keyword.trim() || undefined,
      role: filters.role || undefined,
      status: filters.status || undefined,
    })
    users.value = (resp.items || []) as UserRow[]
    total.value = resp.total || 0
    if (resp.page && resp.page !== page.value) page.value = resp.page
  } catch {
    /* 拦截器已提示 */
  } finally {
    loading.value = false
  }
}
function handleSearch() {
  page.value = 1
  loadList()
}
function resetFilters() {
  filters.keyword = ''
  filters.role = ''
  filters.status = ''
  handleSearch()
}
function handleSizeChange() {
  page.value = 1
  loadList()
}

/* ---------------- 新建用户 ---------------- */
const createVisible = ref(false)
const savingCreate = ref(false)
const createRef = ref<FormInstance>()
const createForm = reactive({ username: '', email: '', password: '', phone: '' })
const createRules: FormRules = {
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
    { min: 6, max: 64, message: '密码长度至少 6 位', trigger: 'blur' },
  ],
  phone: [{ pattern: /^$|^1\d{10}$/, message: '请输入 11 位手机号', trigger: 'blur' }],
}
function openCreate() {
  Object.assign(createForm, { username: '', email: '', password: '', phone: '' })
  createVisible.value = true
}
async function submitCreate() {
  const valid = await createRef.value?.validate().catch(() => false)
  if (!valid) return
  savingCreate.value = true
  try {
    await userApi.create({
      username: createForm.username,
      email: createForm.email,
      password: createForm.password,
      phone: createForm.phone || undefined,
      role_codes: ['user'],
    })
    ElMessage.success('用户创建成功')
    createVisible.value = false
    handleSearch()
  } catch {
    /* 拦截器已提示 */
  } finally {
    savingCreate.value = false
  }
}

/* ---------------- 编辑（角色 + 资料） ---------------- */
const editVisible = ref(false)
const savingEdit = ref(false)
const editRef = ref<FormInstance>()
const editingRow = ref<UserRow | null>(null)
const editForm = reactive({ id: 0, username: '', email: '', phone: '', roleCodes: [] as string[] })
const editRules: FormRules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: ['blur', 'change'] },
  ],
  phone: [{ pattern: /^$|^1\d{10}$/, message: '请输入 11 位手机号', trigger: 'blur' }],
}
function openEdit(row: UserRow) {
  editingRow.value = row
  editForm.id = row.id
  editForm.username = row.username
  editForm.email = row.email
  editForm.phone = row.phone || ''
  editForm.roleCodes = row.roles.map((r) => r.code)
  editVisible.value = true
}
async function submitEdit() {
  const valid = await editRef.value?.validate().catch(() => false)
  if (!valid) return
  savingEdit.value = true
  try {
    await userApi.update(editForm.id, { email: editForm.email, phone: editForm.phone })
    await userApi.setRoles(editForm.id, editForm.roleCodes)
    ElMessage.success('已保存修改')
    editVisible.value = false
    handleSearch()
  } catch {
    /* 拦截器已提示（例如不能移除自己的管理员角色） */
  } finally {
    savingEdit.value = false
  }
}

/* ---------------- 启用 / 禁用 ---------------- */
async function toggleStatus(row: UserRow, toActive: boolean) {
  try {
    await userApi.setStatus(row.id, toActive)
    ElMessage.success(toActive ? '已启用' : '已禁用')
    handleSearch()
  } catch {
    /* 拦截器已提示（例如不能禁用自己） */
  }
}

/* ---------------- 重置密码 ---------------- */
const resetVisible = ref(false)
const savingReset = ref(false)
const resetRef = ref<FormInstance>()
const resetForm = reactive({ id: 0, username: '', new_password: '' })
const resetRules: FormRules = {
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, max: 64, message: '密码长度至少 6 位', trigger: 'blur' },
  ],
}
function openReset(row: UserRow) {
  resetForm.id = row.id
  resetForm.username = row.username
  resetForm.new_password = ''
  resetVisible.value = true
}
async function submitReset() {
  const valid = await resetRef.value?.validate().catch(() => false)
  if (!valid) return
  savingReset.value = true
  try {
    await userApi.resetPwd(resetForm.id, resetForm.new_password)
    ElMessage.success('密码已重置')
    resetVisible.value = false
  } catch {
    /* 拦截器已提示 */
  } finally {
    savingReset.value = false
  }
}

/* ---------------- 删除 ---------------- */
async function removeUser(row: UserRow) {
  if (isSelf(row)) {
    ElMessage.warning('不能删除自己的账号')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定删除用户「${row.username}」吗？删除后不可恢复，其名下数据将一并清空。`,
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await userApi.remove(row.id)
    ElMessage.success('用户已删除')
    if (users.value.length === 1 && page.value > 1) page.value -= 1
    handleSearch()
  } catch {
    /* 拦截器已提示 */
  }
}

onMounted(() => {
  loadRoles()
  loadList()
})
</script>

<style lang="scss" scoped>
.um-page { max-width: 1280px; margin: 0 auto; display: grid; gap: 16px; }

.toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 16px 20px; flex-wrap: wrap; }
.filters { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }

.table-card { padding: 8px 14px 14px; }
.role-tag { margin: 0 6px 4px 0; }
.ops { display: inline-flex; align-items: center; gap: 2px; white-space: nowrap; }
.ops .el-button { margin: 0; }

.pager { display: flex; justify-content: flex-end; padding-top: 14px; }

.self-alert { margin-bottom: 16px; }
.role-checks { display: grid; gap: 4px; width: 100%; }
.check-item { display: inline-flex; flex-direction: column; line-height: 1.35; }
.check-item b { font-weight: 600; }
.check-item i { font-style: normal; font-size: 12px; }
.reset-form { margin-top: 14px; }
</style>
