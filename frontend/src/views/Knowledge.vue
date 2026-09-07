<template>
  <div class="kb-page fade-in">
    <!-- 顶部：标题 + 统计 -->
    <div class="kb-head">
      <div class="kb-head-left">
        <h2 class="gradient-title kb-title">
          <el-icon class="kb-title-ico"><Reading /></el-icon>
          {{ pageTitle }}
        </h2>
        <p class="muted kb-sub">{{ pageSub }}</p>
      </div>
      <div class="kb-stats">
        <div class="stat-chip glass-card">
          <div class="stat-num">{{ stats.total_documents ?? '--' }}</div>
          <div class="stat-label">文档总数</div>
        </div>
        <div class="stat-chip glass-card">
          <div class="stat-num">{{ stats.total_chunks ?? '--' }}</div>
          <div class="stat-label">检索分块</div>
        </div>
      </div>
    </div>

    <!-- 顶部检索框 -->
    <div class="glass-card search-card">
      <div class="search-bar">
        <el-icon class="search-ico"><Search /></el-icon>
        <input
          v-model="query"
          class="search-input"
          placeholder="输入关键词进行法规语义检索，如：试用期工资、经济补偿金计算…"
          maxlength="200"
          @keyup.enter="doSearch"
        />
        <el-button type="primary" :loading="searching" :icon="Search" class="search-btn" @click="doSearch">
          语义检索
        </el-button>
      </div>
      <div class="search-tip muted" v-if="!searched">
        支持对法律、案例、司法解释的全文语义检索，检索结果将标注匹配度与原文片段。
      </div>
    </div>

    <!-- 检索结果卡片 -->
    <div v-if="searched" class="section">
      <div class="section-title">
        <el-icon><Document /></el-icon>
        检索结果
        <span class="muted result-count">共 {{ results.length }} 条</span>
        <el-button link size="small" type="primary" @click="clearSearch">清空检索</el-button>
      </div>
      <div v-loading="searching" class="result-list">
        <div
          v-for="(r, i) in results"
          :key="r.id || i"
          class="result-card"
          @click="openDetail(r.document_id)"
        >
          <div class="res-head">
            <div class="res-tags">
              <el-tag size="small" :type="docTypeTag(r.doc_type)" effect="dark" class="res-type">{{ r.doc_type || '法律' }}</el-tag>
              <el-tag v-if="r.effectiveness" size="small" :type="effType(r.effectiveness)">{{ r.effectiveness }}</el-tag>
              <span v-if="r.law_name || r.article_no" class="res-article muted">
                <el-icon><Document /></el-icon>
                {{ r.law_name || r.title }}{{ r.article_no ? ` · 第${r.article_no}条` : '' }}
              </span>
            </div>
            <el-tag size="small" :type="scoreType(r.score)" effect="plain" class="score-tag">
              匹配 {{ Math.round((r.score || 0) * 100) }}%
            </el-tag>
          </div>
          <h3 class="res-title" :title="r.title">{{ r.title }}</h3>
          <div class="res-content" v-html="highlight(r.content, query)"></div>
        </div>

        <el-empty v-if="!searching && !results.length" description="未检索到相关内容，试试更换关键词" />
      </div>
    </div>

    <!-- 文档浏览 -->
    <div class="section">
      <div class="section-title">
        <el-icon><FolderOpened /></el-icon>
        {{ isManage ? '文档管理' : '法规文档库' }}
        <span class="muted result-count">共 {{ total }} 篇</span>
      </div>

      <div class="glass-card docs-card">
        <!-- 工具条：类型筛选 + 上传 -->
        <div class="docs-toolbar">
          <div class="type-filter">
            <span class="muted filter-label">类型筛选：</span>
            <el-radio-group v-model="typeFilter" size="small" @change="onTypeChange">
              <el-radio-button value="">全部</el-radio-button>
              <el-radio-button v-for="t in typeOptions" :key="t" :value="t">{{ t }}</el-radio-button>
            </el-radio-group>
          </div>
          <div class="toolbar-btns">
            <el-button :icon="Refresh" :loading="docsLoading" @click="reloadAll">刷新</el-button>
            <el-button v-if="isManage" type="primary" :icon="Upload" @click="uploadVisible = true">上传文档</el-button>
          </div>
        </div>

        <el-table :data="docs" v-loading="docsLoading" stripe :row-key="rowKey" class="docs-table">
          <el-table-column prop="id" label="ID" width="70" align="center" />
          <el-table-column label="标题" min-width="230" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="doc-title-link" @click="openDetail(row.id)">{{ row.title || '未命名' }}</span>
              <el-tag v-for="t in (row.tags || [])" :key="t" size="small" effect="plain" class="doc-tag">{{ t }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="docTypeTag(row.doc_type)" effect="dark">{{ row.doc_type || '法律' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="效力" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="effType(row.effectiveness)">{{ effLabel(row.effectiveness) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column v-if="isManage" prop="chunk_count" label="分块数" width="90" align="center" />
          <el-table-column v-if="isManage" label="状态" width="105">
            <template #default="{ row }">
              <el-tag size="small" :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="上传时间" width="150">
            <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" :width="isManage ? 150 : 90" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" :icon="View" @click="openDetail(row.id)">详情</el-button>
              <el-popconfirm
                v-if="isManage"
                title="确定删除该文档吗？删除后不可恢复"
                confirm-button-text="删除"
                cancel-button-text="取消"
                @confirm="removeDoc(row)"
              >
                <template #reference>
                  <el-button link type="danger" size="small" :icon="Delete">删除</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>

        <div class="docs-pager">
          <el-pagination
            background
            layout="total, prev, pager, next"
            :total="total"
            :page-size="pageSize"
            :current-page="page"
            @current-change="onPageChange"
          />
        </div>
      </div>
    </div>

    <!-- 上传对话框 -->
    <el-dialog v-model="uploadVisible" title="上传法规文档" width="480px">
      <el-form label-width="80px" label-position="left">
        <el-form-item label="文档类型">
          <el-radio-group v-model="uploadType">
            <el-radio-button v-for="t in typeOptions" :key="t" :value="t">{{ t }}</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="文件">
          <div class="file-pick">
            <input
              ref="fileRef"
              type="file"
              class="file-input"
              accept=".pdf,.doc,.docx,.txt"
              @change="onFileChange"
            />
            <div v-if="!file" class="file-drop" @click="fileRef && fileRef.click()">
              <el-icon class="file-ico"><UploadFilled /></el-icon>
              <span>点击选择文件（PDF / Word / TXT）</span>
            </div>
            <div v-else class="file-chosen">
              <el-icon><Document /></el-icon>
              <span class="file-name">{{ file.name }}</span>
              <span class="muted">{{ (file.size / 1024).toFixed(1) }} KB</span>
              <el-button link type="danger" size="small" @click="resetFile">移除</el-button>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" :disabled="!file" @click="doUpload">上传并索引</el-button>
      </template>
    </el-dialog>

    <!-- 详情对话框 -->
    <el-dialog v-model="detailVisible" class="kb-dialog" width="780px" top="6vh">
      <div v-if="detail" class="kb-detail">
        <div class="detail-head">
          <div class="detail-title">
            <el-tag size="small" :type="docTypeTag(detail.doc_type)" effect="dark" class="detail-type">{{ detail.doc_type || '法律' }}</el-tag>
            <span class="d-title-text">{{ detail.title || '未命名' }}</span>
          </div>
          <el-tag size="small" :type="effType(detail.effectiveness)">{{ effLabel(detail.effectiveness) }}</el-tag>
        </div>

        <div class="detail-meta">
          <span>文档 ID：{{ detail.id }}</span>
          <span v-if="detail.version">版本：{{ detail.version }}</span>
          <span v-if="detail.chunk_count !== undefined">分块：{{ detail.chunk_count }}</span>
          <span v-if="isManage && detail.status">状态：{{ statusLabel(detail.status) }}</span>
          <span v-if="detail.effective_date">生效：{{ fmtTime(detail.effective_date) }}</span>
          <span v-if="detail.abolished_date">废止：{{ fmtTime(detail.abolished_date) }}</span>
        </div>

        <div class="detail-block">
          <div class="block-title"><el-icon><DocumentChecked /></el-icon> 摘要</div>
          <p class="detail-summary">{{ detail.summary || '暂无摘要' }}</p>
        </div>

        <div class="detail-block">
          <div class="block-title flex between center">
            <span class="flex center gap8"><el-icon><Document /></el-icon> 正文内容</span>
            <el-button link type="primary" size="small" :loading="contentLoading" @click="toggleContent">
              {{ fullContent ? '收起全文' : '查看全文' }}
            </el-button>
          </div>
          <div v-if="!fullContent && detail.chunks_preview" class="chunk-preview">
            <div v-for="ch in detail.chunks_preview" :key="ch.vector_id || ch.index" class="chunk-item">
              <el-tag v-if="ch.article_no" size="small" effect="plain" class="chunk-art">第{{ ch.article_no }}条</el-tag>
              <span class="muted">[片段 {{ ch.index + 1 }}]</span>
              <p>{{ ch.content }}…</p>
            </div>
          </div>
          <div v-if="fullContent" class="full-content">
            {{ fullContent }}
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Delete, Document, DocumentChecked, FolderOpened, Reading, Refresh, Search, Upload, UploadFilled, View,
} from '@element-plus/icons-vue'
import { knowledgeApi } from '@/api/knowledge'
import { useUserStore } from '@/stores/user'

const user = useUserStore()

/* ---------------- 类型定义 ---------------- */
interface SearchItem {
  id?: string
  document_id?: number
  title?: string
  doc_type?: string
  law_name?: string
  article_no?: string
  effectiveness?: string
  content?: string
  score?: number
}

interface DocRow {
  id: number
  title: string
  doc_type?: string
  effectiveness?: string
  status?: string
  chunk_count?: number
  file_name?: string
  tags?: string[]
  created_at?: string
  [k: string]: any
}

const typeOptions = ['法律', '案例', '司法解释']

/* ---------------- 角色 ---------------- */
const isManage = computed(() => user.isLawyer)
const pageTitle = computed(() => (isManage.value ? '法规知识库' : '法规检索库'))
const pageSub = computed(() =>
  isManage.value
    ? '维护与检索法律文档库，支持上传、索引、删除与语义检索'
    : '面向全量法规文档的智能语义检索，结果仅供参考，请以官方文本为准'
)

/* ---------------- 数据状态 ---------------- */
const stats = reactive<{ total_documents?: number; total_chunks?: number }>({})
const query = ref('')
const searched = ref(false)
const searching = ref(false)
const results = ref<SearchItem[]>([])

const docs = ref<DocRow[]>([])
const docsLoading = ref(false)
const typeFilter = ref('')
const page = ref(1)
const pageSize = 10
const total = ref(0)

/* 上传 */
const uploadVisible = ref(false)
const uploading = ref(false)
const uploadType = ref('法律')
const file = ref<File | null>(null)
const fileRef = ref<HTMLInputElement | null>(null)

/* 详情 */
const detailVisible = ref(false)
const detail = ref<DocRow | null>(null)
const detailId = ref<number | null>(null)
const fullContent = ref('')
const contentLoading = ref(false)

onMounted(() => {
  loadStats()
  loadDocs()
})

/* ---------------- 通用 ---------------- */
function rowKey(row: DocRow) {
  return row.id
}

function fmtTime(s?: string): string {
  if (!s) return '-'
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return String(s).slice(0, 16)
  const y = d.getFullYear()
  const m = `${d.getMonth() + 1}`.padStart(2, '0')
  const day = `${d.getDate()}`.padStart(2, '0')
  const hh = `${d.getHours()}`.padStart(2, '0')
  const mm = `${d.getMinutes()}`.padStart(2, '0')
  const now = new Date()
  if (d.toDateString() === now.toDateString()) return `${hh}:${mm}`
  if (y === now.getFullYear()) return `${m}-${day} ${hh}:${mm}`
  return `${y}-${m}-${day}`
}

/* 高亮关键词 */
function escHtml(s: string): string {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function highlight(text: string, keyword: string): string {
  const safe = escHtml(text || '')
  const keys = (keyword || '').split(/\s+/).filter(Boolean)
  if (!keys.length) return safe
  const patterns = keys.map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).filter(Boolean)
  if (!patterns.length) return safe
  try {
    const re = new RegExp(`(${patterns.join('|')})`, 'gi')
    return safe.replace(re, '<em class="hl">$1</em>')
  } catch {
    return safe
  }
}

/* ---------------- 标签映射 ---------------- */
function docTypeTag(t?: string): any {
  const map: Record<string, any> = { 法律: 'primary', 案例: 'warning', 司法解释: 'success' }
  return map[t || ''] || 'info'
}
function effType(e?: string): any {
  const map: Record<string, any> = { 有效: 'success', 部分修订: 'warning', 已废止: 'info' }
  return map[e || ''] || 'info'
}
function effLabel(e?: string): string {
  const map: Record<string, string> = { 有效: '有效', 部分修订: '部分修订', 已废止: '已废止' }
  return map[e || ''] || e || '有效'
}
function statusLabel(s?: string): string {
  const map: Record<string, string> = { pending: '待处理', processing: '处理中', completed: '已完成', failed: '失败' }
  return map[s || ''] || s || '未知'
}
function statusType(s?: string): any {
  const map: Record<string, any> = { pending: 'info', processing: 'warning', completed: 'success', failed: 'danger' }
  return map[s || ''] || 'info'
}
function scoreType(score?: number): any {
  if (score == null) return 'info'
  if (score >= 0.8) return 'success'
  if (score >= 0.6) return 'warning'
  return 'info'
}

/* ---------------- 检索 ---------------- */
async function doSearch() {
  const q = query.value.trim()
  if (!q) {
    ElMessage.warning('请输入检索关键词')
    return
  }
  searching.value = true
  try {
    const res = (await knowledgeApi.search({ query: q, top_k: 8 })) as any
    results.value = (res?.items || []).map((it: any) => ({
      id: it.id,
      document_id: it.document_id,
      title: it.title || '',
      doc_type: it.doc_type,
      law_name: it.law_name,
      article_no: it.article_no,
      effectiveness: it.effectiveness,
      content: it.content || '',
      score: typeof it.score === 'number' ? it.score : 0,
    }))
    searched.value = true
  } catch {
    results.value = []
    searched.value = true
  } finally {
    searching.value = false
  }
}

function clearSearch() {
  searched.value = false
  results.value = []
  query.value = ''
}

/* ---------------- 统计 / 文档列表 ---------------- */
async function loadStats() {
  try {
    const res = (await knowledgeApi.stats()) as any
    stats.total_documents = res?.total_documents ?? 0
    stats.total_chunks = res?.total_chunks ?? 0
  } catch {
    stats.total_documents = 0
    stats.total_chunks = 0
  }
}

async function loadDocs() {
  docsLoading.value = true
  try {
    const params: any = { page: page.value, page_size: pageSize }
    if (typeFilter.value) params.doc_type = typeFilter.value
    const res = (await knowledgeApi.documents(params)) as any
    docs.value = res?.items || []
    total.value = Number(res?.total ?? docs.value.length)
  } catch {
    docs.value = []
    total.value = 0
  } finally {
    docsLoading.value = false
  }
}

function onTypeChange() {
  page.value = 1
  loadDocs()
}

function onPageChange(p: number) {
  page.value = p
  loadDocs()
}

function reloadAll() {
  page.value = 1
  loadStats()
  loadDocs()
}

/* ---------------- 上传 ---------------- */
function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  const f = input.files?.[0]
  if (f) {
    if (f.size > 20 * 1024 * 1024) {
      ElMessage.warning('文件大小不能超过 20MB')
      resetFile()
      return
    }
    file.value = f
  }
}

function resetFile() {
  file.value = null
  if (fileRef.value) fileRef.value.value = ''
}

async function doUpload() {
  if (!file.value) return
  uploading.value = true
  try {
    await knowledgeApi.upload(file.value, uploadType.value)
    ElMessage.success('上传并索引成功')
    uploadVisible.value = false
    resetFile()
    page.value = 1
    loadStats()
    loadDocs()
  } catch {
    /* 拦截器已提示 */
  } finally {
    uploading.value = false
  }
}

/* ---------------- 删除 ---------------- */
async function removeDoc(row: DocRow) {
  try {
    await knowledgeApi.remove(row.id)
    ElMessage.success('文档已删除')
    if (total.value > 1 && docs.value.length === 1 && page.value > 1) page.value -= 1
    loadStats()
    loadDocs()
  } catch {
    /* 拦截器已提示 */
  }
}

/* ---------------- 详情 ---------------- */
async function openDetail(id?: number) {
  if (!id) {
    ElMessage.info('该文档暂无详情')
    return
  }
  detailId.value = id
  detailVisible.value = true
  fullContent.value = ''
  try {
    const res = (await knowledgeApi.detail(id)) as any
    detail.value = res
  } catch {
    detail.value = null
  }
}

async function toggleContent() {
  if (fullContent.value) {
    fullContent.value = ''
    return
  }
  if (!detailId.value) return
  contentLoading.value = true
  try {
    const res = (await knowledgeApi.content(detailId.value)) as any
    fullContent.value = res?.content || '该文档暂无可预览的正文内容'
  } catch {
    fullContent.value = ''
  } finally {
    contentLoading.value = false
  }
}
</script>

<style lang="scss" scoped>
.kb-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  max-width: 1280px;
  margin: 0 auto;
}

/* 头部 */
.kb-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.kb-head-left { display: flex; flex-direction: column; gap: 6px; }
.kb-title { display: flex; align-items: center; gap: 8px; font-size: 22px; margin: 0; letter-spacing: 1px; }
.kb-title-ico { font-size: 20px; }
.kb-sub { margin: 0; font-size: 13px; }

.kb-stats { display: flex; gap: 12px; }
.stat-chip {
  min-width: 108px;
  text-align: center;
  padding: 10px 16px;
}
.stat-num {
  font-size: 22px;
  font-weight: 700;
  color: var(--accent);
  line-height: 1.2;
}
.stat-label { font-size: 12px; color: var(--text-secondary); margin-top: 2px; }

/* 检索区 */
.search-card { padding: 18px 20px; }
.search-bar { display: flex; align-items: center; gap: 12px; }
.search-ico { font-size: 20px; color: var(--accent); flex: none; }
.search-input {
  flex: 1;
  height: 40px;
  background: rgba(10, 22, 40, 0.5);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0 14px;
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
  &:focus { border-color: rgba(201, 169, 110, 0.6); box-shadow: 0 0 0 3px rgba(201, 169, 110, 0.08); }
  &::placeholder { color: var(--text-muted); }
}
.search-btn { flex: none; }
.search-tip { margin-top: 12px; font-size: 12px; padding-left: 32px; }

/* 区块 */
.section { display: flex; flex-direction: column; gap: 12px; }
.result-count { font-size: 12px; font-weight: 400; }
.section-title .el-button { margin-left: auto; }

/* 结果卡片 */
.result-list { display: flex; flex-direction: column; gap: 12px; }
.result-card {
  padding: 16px 18px;
  border-radius: 12px;
  background: rgba(18, 35, 60, 0.6);
  border: 1px solid var(--border);
  cursor: pointer;
  transition: border-color 0.2s, transform 0.2s, box-shadow 0.2s;
  &:hover {
    border-color: rgba(201, 169, 110, 0.55);
    transform: translateY(-1px);
    box-shadow: 0 8px 22px rgba(0, 0, 0, 0.25);
  }
}
.res-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.res-tags { display: flex; align-items: center; gap: 6px; min-width: 0; }
.res-article { display: inline-flex; align-items: center; gap: 4px; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.score-tag { flex: none; }
.res-title { margin: 10px 0 6px; font-size: 15px; color: var(--text-primary); }
.res-content {
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
:deep(.hl) {
  color: var(--accent);
  font-style: normal;
  font-weight: 600;
  background: rgba(201, 169, 110, 0.18);
  padding: 0 2px;
  border-radius: 3px;
}

/* 文档卡片 */
.docs-card { padding: 14px 16px; }
.docs-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.type-filter { display: flex; align-items: center; gap: 10px; }
.filter-label { font-size: 13px; }
.toolbar-btns { display: flex; gap: 8px; }

.docs-table { width: 100%; }
.doc-title-link { color: var(--text-primary); cursor: pointer; &:hover { color: var(--accent); text-decoration: underline; } }
.doc-tag { margin-left: 6px; }
.docs-pager { display: flex; justify-content: flex-end; margin-top: 14px; }

/* 上传 */
.file-pick { width: 100%; }
.file-input { display: none; }
.file-drop {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 26px;
  border: 1px dashed var(--border);
  border-radius: 10px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
  &:hover { border-color: rgba(201, 169, 110, 0.6); background: rgba(201, 169, 110, 0.06); }
}
.file-ico { font-size: 30px; color: var(--accent); }
.file-chosen {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border);
  .el-icon { color: var(--accent); }
}
.file-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* 详情 */
.kb-detail { display: flex; flex-direction: column; gap: 14px; }
.detail-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.detail-title { display: flex; align-items: center; gap: 10px; min-width: 0; }
.detail-type { flex: none; }
.d-title-text { font-size: 16px; font-weight: 700; }
.detail-meta { display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 12px; color: var(--text-secondary); background: rgba(255,255,255,0.03); padding: 8px 12px; border-radius: 8px; }
.detail-block { display: flex; flex-direction: column; gap: 8px; }
.block-title { display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 600; color: var(--accent); }
.detail-summary { margin: 0; font-size: 13px; line-height: 1.8; color: var(--text-primary); background: rgba(255,255,255,0.03); padding: 10px 12px; border-radius: 8px; }
.chunk-preview { display: flex; flex-direction: column; gap: 10px; }
.chunk-item { font-size: 13px; color: var(--text-secondary); background: rgba(255,255,255,0.03); padding: 10px 12px; border-radius: 8px; }
.chunk-item p { margin: 6px 0 0; line-height: 1.7; color: var(--text-primary); }
.chunk-art { margin-right: 6px; }
.full-content {
  max-height: 46vh;
  overflow: auto;
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.9;
  color: var(--text-primary);
  background: rgba(255,255,255,0.03);
  padding: 12px 14px;
  border-radius: 8px;
}

:deep(.el-dialog__title) { color: var(--text-primary); }
:deep(.el-dialog__body) { max-height: 80vh; overflow: auto; }
</style>
