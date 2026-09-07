<template>
  <div class="page contract fade-in">
    <!-- 顶部：额度提示 + 上传 -->
    <div class="glass-card top-bar">
      <div class="quota">
        <div class="quota-icon"><el-icon :size="20"><Stamp /></el-icon></div>
        <div class="quota-body">
          <div class="quota-title"><b>每日审查额度</b><el-tag size="small" type="warning" effect="plain">10 份</el-tag></div>
          <div class="muted">每位用户每天可免费审查 10 份合同，超额部分建议联系法务负责人开通企业套餐。</div>
        </div>
      </div>
      <el-upload
        class="up"
        drag
        action="#"
        accept=".pdf,.doc,.docx,.txt"
        :show-file-list="false"
        :http-request="doUpload"
        :disabled="uploading"
      >
        <div class="up-body" :class="{ uploading }">
          <el-icon :size="30" class="up-icon"><UploadFilled /></el-icon>
          <div class="up-text"><b>{{ uploading ? '合同解析中，请稍候…' : '将合同文件拖拽到此处，或点击上传' }}</b></div>
          <div class="muted up-tip">支持 PDF / Word / TXT 格式 · 上传成功后系统将自动解析并抽取条款</div>
        </div>
      </el-upload>
    </div>

    <!-- 统计小条 -->
    <div class="mini-stats">
      <div class="mini-stat glass-card"><div class="mini-num gold">{{ stats.total }}</div><div class="muted mini-label">合同总数</div></div>
      <div class="mini-stat glass-card"><div class="mini-num green">{{ stats.reviewed }}</div><div class="muted mini-label">已审查</div></div>
      <div class="mini-stat glass-card"><div class="mini-num blue">{{ stats.pending }}</div><div class="muted mini-label">待审查</div></div>
      <div class="mini-stat glass-card"><div class="mini-num">{{ stats.avg == null ? '—' : stats.avg.toFixed(1) }}</div><div class="muted mini-label">平均合规分</div></div>
    </div>

    <!-- 合同表格 -->
    <div class="glass-card">
      <div class="section-title between">
        <span class="sec"><el-icon><DocumentChecked /></el-icon>合同审查列表</span>
        <el-button size="small" :icon="RefreshLeft" text @click="loadHistory">刷新</el-button>
      </div>

      <el-table v-loading="tableLoading" :data="list" style="width: 100%">
        <el-table-column label="合同标题" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="row-title"><el-icon><Document /></el-icon>{{ row.title || '未命名合同' }}</div>
          </template>
        </el-table-column>

        <el-table-column label="合同类型" width="170">
          <template #default="{ row }">
            <el-popover
              placement="bottom"
              :width="190"
              trigger="click"
              :visible="typeEditor.id === row.id"
              @show="openTypeEditor(row)"
            >
              <template #reference>
                <span class="type-cell" @click="openTypeEditor(row)">
                  <el-tag size="small" effect="plain" type="info" class="type-tag">{{ row.contract_type || '未分类' }}</el-tag>
                  <el-icon class="type-edit"><EditPen /></el-icon>
                </span>
              </template>
              <div>
                <div class="muted type-hint">修改合同类型（用于精准审查）</div>
                <el-select
                  v-model="typeEditor.value"
                  filterable
                  allow-create
                  default-first-option
                  placeholder="选择或输入类型"
                  style="width: 100%"
                  @change="confirmType"
                >
                  <el-option v-for="t in typeOptions" :key="t" :label="t" :value="t" />
                </el-select>
              </div>
            </el-popover>
          </template>
        </el-table-column>

        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="statusMeta(row.status).tag" effect="dark">{{ statusMeta(row.status).label }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column label="风险分" width="92" align="center">
          <template #default="{ row }">
            <el-tooltip v-if="hasScore(row)" :content="`共识别 ${row.risk_clause_count ?? 0} 处风险条款`" placement="top">
              <div class="score-cell">
                <el-progress
                  type="dashboard"
                  :percentage="scorePct(row)"
                  :width="52"
                  :stroke-width="6"
                  :color="scoreColor(scoreNum(row))"
                />
              </div>
            </el-tooltip>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>

        <el-table-column label="风险等级" width="96">
          <template #default="{ row }">
            <el-tag size="small" :type="riskMeta(row.risk_level).tag" effect="light">{{ riskMeta(row.risk_level).label }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column label="审查时间" width="168">
          <template #default="{ row }">
            <span class="muted time">{{ fmtTime(row.created_at) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <div class="ops">
              <el-button
                v-if="row.status === 'uploaded' || row.status === 'parsed' || row.status === 'failed'"
                size="small" type="primary" :icon="MagicStick" :loading="reviewingId === row.id" @click="startReview(row)"
              >开始审查</el-button>
              <el-button
                v-if="row.status === 'reviewed'"
                size="small" type="warning" plain :icon="View" @click="showReport(row)"
              >查看报告</el-button>
              <el-button
                v-if="row.status === 'reviewed'"
                size="small" :icon="Download" text @click="downloadOptimized(row)"
              >优化下载</el-button>
              <el-popconfirm title="确认删除该合同记录？" confirm-button-text="删除" cancel-button-text="取消" @confirm="removeRow(row)">
                <template #reference>
                  <el-button size="small" type="danger" text :icon="Delete" />
                </template>
              </el-popconfirm>
            </div>
          </template>
        </el-table-column>

        <template #empty>
          <el-empty description="暂无合同记录，上传一份合同开始智能审查" :image-size="90" />
        </template>
      </el-table>
    </div>

    <!-- 审查进度对话框 -->
    <el-dialog v-model="reviewDlg" :width="440" :show-close="false" :close-on-click-modal="false" :close-on-press-escape="false" align-center>
      <div class="review-run">
        <div class="run-ring">
          <svg viewBox="0 0 80 80" class="run-svg">
            <circle cx="40" cy="40" r="32" fill="none" stroke="rgba(201,169,110,.2)" stroke-width="6" />
            <circle cx="40" cy="40" r="32" fill="none" stroke="url(#rgrad)" stroke-width="6" stroke-linecap="round" class="run-arc" />
            <defs><linearGradient id="rgrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#c9a96e" /><stop offset="100%" stop-color="#3a7abc" /></linearGradient></defs>
          </svg>
          <el-icon :size="26" class="run-center"><MagicStick /></el-icon>
        </div>
        <div class="run-title">多 Agent 对抗式审查中…</div>
        <div class="run-step muted"><span class="step-index">{{ reviewStep + 1 }}/{{ reviewSteps.length }}</span>{{ reviewSteps[reviewStep] }}</div>
        <el-progress :percentage="reviewProgress" :show-text="false" :stroke-width="4" :color="'#c9a96e'" class="run-bar" />
      </div>
    </el-dialog>

    <!-- 审查报告对话框 -->
    <el-dialog v-model="reportDlg" :width="min(reportWidth, 960)" :top="'3vh'" class="report-dlg">
      <template #header>
        <div class="rep-header">
          <span class="rep-icon"><el-icon :size="18"><View /></el-icon></span>
          <span>合同审查报告</span>
        </div>
      </template>

      <div v-if="reportLoading" v-loading="reportLoading" class="rep-loading" />
      <div v-else-if="report" class="report">
        <!-- 头部：仪表盘 + 概览 -->
        <div class="rep-overview glass-card">
          <div class="rep-gauge">
            <el-progress
              type="dashboard"
              :percentage="scorePctOf(report.overall)"
              :width="150"
              :stroke-width="12"
              :color="scoreColor(report.overall)"
            />
            <div class="rep-risk">
              <div class="muted">风险等级</div>
              <el-tag :type="riskMeta(report.risk_level).tag" size="large" effect="dark">{{ riskMeta(report.risk_level).label }}</el-tag>
            </div>
          </div>
          <div class="rep-main">
            <div class="rep-title">{{ report.title || '合同审查报告' }}</div>
            <div class="muted rep-meta">
              <el-tag v-if="report.contract_type" size="small" effect="plain">{{ report.contract_type }}</el-tag>
              <span v-if="report.risk_clause_count != null">共识别 {{ report.risk_clause_count }} 处风险条款</span>
              <span v-if="report.created_at">{{ report.created_at }}</span>
            </div>
            <p v-if="report.summary" class="rep-summary">{{ report.summary }}</p>
            <el-empty v-else-if="!report.dims.has && !report.summary" description="暂无审查摘要" :image-size="70" />
          </div>
        </div>

        <!-- 三维度评分 -->
        <div v-if="report.dims.has" class="glass-card rep-block">
          <div class="sub-title"><el-icon><Odometer /></el-icon>三维度评分</div>
          <div class="dims">
            <div v-for="d in report.dims.list" :key="d.key" class="dim-row">
              <div class="dim-label">{{ d.label }}</div>
              <div class="dim-bar">
                <el-progress :percentage="d.pct" :stroke-width="12" :color="scoreColor(d.pct)" :show-text="false" />
              </div>
              <div class="dim-val">{{ d.display }}</div>
            </div>
          </div>
        </div>

        <!-- 风险条款 -->
        <div class="glass-card rep-block">
          <div class="sub-title"><el-icon><Warning /></el-icon>风险条款分析 <el-tag size="small" type="danger" effect="plain">{{ report.risk_clauses.length }} 项</el-tag></div>
          <el-empty v-if="!report.risk_clauses.length" description="未识别到明显风险条款" :image-size="70" />
          <div v-else class="clauses">
            <div v-for="(c, i) in report.risk_clauses" :key="i" class="clause">
              <div class="clause-head">
                <span class="clause-no">条款 {{ c.no }}</span>
                <el-tag size="small" type="warning" effect="dark" v-if="c.type">{{ c.type }}</el-tag>
                <el-tag size="small" :type="riskMeta(c.level).tag" effect="light" v-if="c.level">{{ riskMeta(c.level).label }}</el-tag>
              </div>
              <div class="clause-row" v-if="c.desc"><span class="lbl lbl-d">风险描述</span>{{ c.desc }}</div>
              <div class="clause-row" v-if="c.sug"><span class="lbl lbl-s">修改建议</span>{{ c.sug }}</div>
              <div class="clause-row" v-if="c.basis"><span class="lbl lbl-b">法律依据</span><span class="basis">{{ c.basis }}</span></div>
            </div>
          </div>
        </div>

        <!-- 多 Agent 对抗 -->
        <div class="glass-card rep-block">
          <div class="sub-title"><el-icon><Cpu /></el-icon>多 Agent 对抗式审查</div>

          <div class="aa-head">
            <div class="muted">主审裁决</div>
            <div v-if="report.review_check">
              <el-tag
                :type="report.review_check.verdict === 'approved' || report.review_check.verdict === '通过' ? 'success' : 'danger'"
                effect="dark"
                v-if="report.review_check.verdict"
              >
                {{ verdictLabel(report.review_check.verdict) }}
              </el-tag>
            </div>
          </div>

          <div class="aa-block" v-if="report.adverse_opinions.length">
            <div class="muted aa-label"><el-icon><ChatLineRound /></el-icon>反方异议（adverse opinions）</div>
            <div v-for="(o, i) in report.adverse_opinions" :key="i" class="aa-opinion">
              <span class="dot-red"></span>{{ o }}
            </div>
          </div>

          <div class="aa-block" v-if="report.debate_log.length">
            <div class="muted aa-label"><el-icon><ScaleToOriginal /></el-icon>辩论时间线（主审 ⇄ 反方 → 仲裁）</div>
            <div class="debate">
              <div v-for="(d, i) in report.debate_log" :key="i" class="debate-round">
                <div class="db-issue" v-if="d.issue"><span class="db-tag">争议焦点</span>{{ d.issue }}</div>
                <div class="db-line" v-if="d.major"><span class="db-tag t-major">主审观点</span>{{ d.major }}</div>
                <div class="db-line" v-if="d.defense"><span class="db-tag t-defense">反方意见</span>{{ d.defense }}</div>
                <div class="db-line" v-if="d.arbiter"><span class="db-tag t-arbiter">仲裁裁决</span>{{ d.arbiter }}</div>
              </div>
            </div>
          </div>

          <div class="aa-block" v-if="report.unresolved_issues.length">
            <div class="muted aa-label"><el-icon><WarningFilled /></el-icon>未决争议事项</div>
            <el-alert
              v-for="(u, i) in report.unresolved_issues"
              :key="i"
              :title="u"
              type="warning"
              :closable="false"
              show-icon
              class="unresolve"
            />
          </div>
          <el-empty v-if="!report.review_check && !report.adverse_opinions.length && !report.debate_log.length && !report.unresolved_issues.length" description="暂未生成对抗审查记录" :image-size="70" />
        </div>

        <!-- 优化建议 -->
        <div class="glass-card rep-block" v-if="report.suggestions.length">
          <div class="sub-title"><el-icon><MagicStick /></el-icon>智能优化建议</div>
          <ol class="sugs">
            <li v-for="(s, i) in report.suggestions" :key="i">{{ s }}</li>
          </ol>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  ChatLineRound, Cpu, Delete, Document, DocumentChecked, Download, EditPen, MagicStick, Odometer,
  RefreshLeft, ScaleToOriginal, Stamp, UploadFilled, View, Warning, WarningFilled,
} from '@element-plus/icons-vue'
import { contractApi } from '@/api/contract'

/* ---------------- 类型/枚举 ---------------- */
interface HistoryRow {
  id: number
  title?: string
  contract_type?: string | null
  status?: string
  overall_score?: number | null
  risk_level?: string | null
  risk_clause_count?: number | null
  created_at?: string | null
}

const typeOptions = [
  '劳动合同', '保密协议', '购销合同', '服务合同', '租赁合同', '借款合同',
  '技术开发合同', '委托合同', '承揽合同', '合作协议', '股权转让协议', '竞业限制协议', '其他',
]

const STATUS_META: Record<string, { label: string; tag: any }> = {
  uploaded: { label: '已上传', tag: 'info' },
  parsing: { label: '解析中', tag: 'warning' },
  parsed: { label: '待审查', tag: 'primary' },
  reviewing: { label: '审查中', tag: 'warning' },
  reviewed: { label: '已审查', tag: 'success' },
  failed: { label: '解析失败', tag: 'danger' },
}
function statusMeta(s: string | undefined) {
  return STATUS_META[s || ''] || { label: s || '未知', tag: 'info' }
}
function riskMeta(r: string | null | undefined): { label: string; tag: any } {
  const v = (r || '').toString().toLowerCase()
  if (/(critical|严重|极高|非常|高危|特别)/.test(v)) return { label: '严重风险', tag: 'danger' }
  if (/high|高/.test(v)) return { label: '高风险', tag: 'danger' }
  if (/medium|中/.test(v)) return { label: '中风险', tag: 'warning' }
  if (/low|低/.test(v)) return { label: '低风险', tag: 'success' }
  if (v) return { label: r as string, tag: 'info' }
  return { label: '未知', tag: 'info' }
}
function scoreColor(v: number | null | undefined): string {
  const n = Number(v)
  if (n >= 85) return '#46c07b'
  if (n >= 70) return '#c98500'
  if (n >= 55) return '#d95926'
  return '#e85d5d'
}
function scoreNum(r: HistoryRow): number {
  const n = Number(r.overall_score)
  return Number.isNaN(n) ? 0 : Math.max(0, Math.min(100, Math.round(n)))
}
function hasScore(r: HistoryRow): boolean {
  return r.overall_score != null && !Number.isNaN(Number(r.overall_score))
}
function scorePct(r: HistoryRow): number { return scoreNum(r) }
function fmtTime(t: string | null | undefined): string {
  if (!t) return '—'
  const s = t.replace('T', ' ').replace('Z', '')
  return s.length > 16 ? s.slice(0, 16) : s
}

/* ---------------- 数据 ---------------- */
const list = ref<HistoryRow[]>([])
const tableLoading = ref(false)
const uploading = ref(false)

const stats = computed(() => {
  const rows = list.value
  const reviewed = rows.filter((r) => r.status === 'reviewed').length
  const pending = rows.filter((r) => ['uploaded', 'parsed'].includes(r.status || '')).length
  const scored = rows.map((r) => Number(r.overall_score)).filter((n) => !Number.isNaN(n))
  const avg = scored.length ? scored.reduce((s, n) => s + n, 0) / scored.length : null
  return { total: rows.length, reviewed, pending, avg }
})

async function loadHistory() {
  tableLoading.value = true
  try {
    const d: any = await contractApi.history({})
    list.value = Array.isArray(d) ? d : (Array.isArray(d?.items) ? d.items : [])
  } catch {
    list.value = []
  } finally {
    tableLoading.value = false
  }
}

async function doUpload(opts: any) {
  const file: File = opts?.file
  if (!file) return
  uploading.value = true
  try {
    await contractApi.upload(file)
    ElMessage.success('上传成功，正在解析合同…')
    await loadHistory()
    await waitSettled()
  } catch {
    /* 错误提示已由拦截器处理 */
  } finally {
    uploading.value = false
  }
}

async function waitSettled() {
  const transitions = ['uploaded', 'parsing']
  for (let i = 0; i < 12; i++) {
    await new Promise((r) => setTimeout(r, 2000))
    await loadHistory()
    const busy = list.value.some((r) => transitions.includes(r.status || ''))
    if (!busy) break
  }
}

/* ---------------- 类型编辑 ---------------- */
const typeEditor = reactive<{ id: number | null; value: string }>({ id: null, value: '' })
function openTypeEditor(row: HistoryRow) {
  typeEditor.id = row.id
  typeEditor.value = row.contract_type || ''
}
async function confirmType(v: string | number) {
  const id = typeEditor.id
  const val = String(v || '').trim()
  typeEditor.id = null
  if (id == null || !val) return
  try {
    await contractApi.updateType(id, val)
    ElMessage.success('合同类型已更新')
    loadHistory()
  } catch { /* 拦截器已提示 */ }
}

/* ---------------- 审查流程 ---------------- */
const reviewDlg = ref(false)
const reviewSteps = ['合同全文解析与条款抽取', '合规规则库检索与比对', '多 Agent 对抗式辩论', '风险裁决与报告生成']
const reviewStep = ref(0)
const reviewProgress = computed(() => ((reviewStep.value + 1) / reviewSteps.length) * 100)
const reviewingId = ref<number | null>(null)
let reviewTimer: number | null = null

async function startReview(row: HistoryRow) {
  reviewingId.value = row.id
  reviewStep.value = 0
  reviewDlg.value = true
  reviewTimer = window.setInterval(() => {
    reviewStep.value = (reviewStep.value + 1) % reviewSteps.length
  }, 2200)
  try {
    const resp: any = await contractApi.review(row.id, row.contract_type || undefined)
    stopReviewTimer()
    reviewDlg.value = false
    reviewingId.value = null
    const normalized = normalizeReport(resp, row)
    if (normalized) {
      report.value = normalized
      reportDlg.value = true
    }
    loadHistory()
  } catch {
    stopReviewTimer()
    reviewDlg.value = false
    reviewingId.value = null
  }
}
function stopReviewTimer() {
  if (reviewTimer) { window.clearInterval(reviewTimer); reviewTimer = null }
}

/* ---------------- 报告 ---------------- */
const reportDlg = ref(false)
const reportLoading = ref(false)
const report = ref<any>(null)
const reportWidth = ref(960)

function pick(obj: any, keys: string[]) {
  if (!obj) return undefined
  for (const k of keys) {
    const v = obj[k]
    if (v !== undefined && v !== null && v !== '') return v
  }
  return undefined
}
function toList(v: any): any[] {
  if (!v) return []
  if (Array.isArray(v)) return v
  return []
}
function toText(v: any): string {
  if (v === undefined || v === null) return ''
  return typeof v === 'string' ? v : (typeof v === 'object' ? JSON.stringify(v) : String(v))
}

interface Normalized {
  title?: string
  contract_type?: string
  created_at?: string
  overall: number | null
  risk_level: string | null
  risk_clause_count: number | null
  summary: string
  dims: { has: boolean; list: { key: string; label: string; pct: number; display: string }[] }
  risk_clauses: any[]
  review_check: any
  adverse_opinions: string[]
  debate_log: any[]
  unresolved_issues: string[]
  suggestions: string[]
}

function normalizeReport(resp: any, row?: HistoryRow): Normalized {
  const r: any = resp && typeof resp === 'object' ? resp : {}
  const rec = pick(r, ['report', 'result', 'data']) && typeof pick(r, ['report', 'result', 'data']) === 'object'
    ? pick(r, ['report', 'result', 'data'])
    : r
  const overallRaw = pick(rec, ['overall_score', 'overallScore', 'score', 'total_score', 'risk_score', 'composite_score'])
  const overall = overallRaw === undefined ? null : Math.max(0, Math.min(100, Math.round(Number(overallRaw))))
  const risk_level = pick(rec, ['risk_level', 'riskLevel', 'level', 'risk_grade']) ?? null

  const dimList = ['completeness', 'compliance', 'consistency'].map((key) => {
    const val = pick(rec, [key, key === 'completeness' ? '完整性' : key === 'compliance' ? '合规性' : '一致性'])
    const num = val === undefined || val === null ? null : Math.max(0, Math.min(100, Math.round(Number(val))))
    const map: Record<string, { label: string }> = {
      completeness: { label: '条款完整性' },
      compliance: { label: '合规性' },
      consistency: { label: '一致性' },
    }
    return {
      key, label: map[key].label, pct: num ?? 0, display: num == null ? '—' : String(num),
      _has: num != null,
    }
  })
  const dims = {
    has: dimList.some((d) => d._has),
    list: dimList.map(({ key, label, pct, display }) => ({ key, label, pct, display })),
  }

  const clausesRaw = toList(pick(rec, ['risk_clauses', 'riskClauses', 'clauses', 'risks', 'risk_items', 'riskItems']))
  const risk_clauses = clausesRaw.map((c: any, i: number) => ({
    no: toText(pick(c, ['clause_no', 'clauseNo', 'no', 'clause', 'clause_num'])) || String(i + 1),
    type: toText(pick(c, ['risk_type', 'riskType', 'type', 'risk_name'])),
    level: pick(c, ['risk_level', 'riskLevel', 'level']) ?? null,
    desc: toText(pick(c, ['risk_description', 'riskDescription', 'description', 'issue', 'desc', 'content'])),
    sug: toText(pick(c, ['suggestion', 'advice', 'modify_suggestion', 'suggest', 'proposal'])),
    basis: toText(pick(c, ['legal_basis', 'legalBasis', 'law_basis', 'basis', 'reference'])),
  })).filter((c: any) => c.desc || c.type || c.sug)

  const rc = rec.review_check || rec.reviewCheck || null
  const review_check = rc && typeof rc === 'object'
    ? { verdict: toText(pick(rc, ['verdict', 'result', 'conclusion', 'decision'])) || null }
    : null

  const adverse = toList(pick(rec, ['adverse_opinions', 'adverseOpinions', 'opposing_opinions', 'objections', 'dissenting_opinions']))
    .map((o: any) => (typeof o === 'string' ? o : toText(pick(o, ['opinion', 'content', 'text'])) || toText(o)))
    .filter(Boolean)

  const debate = toList(pick(rec, ['debate_log', 'debateLog', 'debates', 'multi_agent_log', 'debate_records'])).map((d: any) => {
    const o = d && typeof d === 'object' ? d : { issue: d }
    return {
      issue: toText(pick(o, ['issue', 'topic', '焦点', '争议焦点', 'question'])),
      major: toText(pick(o, ['prosecutor', 'major', 'major_opinion', 'primary_view', 'reviewer', '主审', '主审观点', 'judge_view'])),
      defense: toText(pick(o, ['defense', 'defense_opinion', 'opponent', 'adversary', 'adverse', '反方', '反方意见', 'opposing_view'])),
      arbiter: toText(pick(o, ['arbiter', 'arbitration', 'verdict', 'final', '裁决', '仲裁裁决', 'decision', 'conclusion'])),
    }
  }).filter((d) => d.issue || d.major || d.defense || d.arbiter)

  const unresolved = toList(pick(rec, ['unresolved_issues', 'unresolvedIssues', 'open_issues', 'pending_issues']))
    .map((u: any) => (typeof u === 'string' ? u : toText(pick(u, ['issue', 'content', 'description', 'text'])) || toText(u)))
    .filter(Boolean)

  const sugs = toList(pick(rec, ['suggestions', 'optimization_suggestions', 'optimizationSuggestions', 'recommendations']))
    .map((s: any) => (typeof s === 'string' ? s : toText(pick(s, ['suggestion', 'content', 'text', 'advice'])) || toText(s)))
    .filter(Boolean)

  const clausesCountRaw = pick(rec, ['risk_clause_count', 'riskClauseCount', 'clause_count', 'risk_count'])
  const risk_clause_count = clausesCountRaw != null ? Number(clausesCountRaw) : (risk_clauses.length || null)

  return {
    title: toText(pick(rec, ['title', 'contract_title', 'name'])) || row?.title || '合同审查报告',
    contract_type: toText(pick(rec, ['contract_type', 'contractType', 'type'])) || row?.contract_type || undefined,
    created_at: toText(pick(rec, ['created_at', 'reviewed_at', 'createdAt', 'time'])),
    overall,
    risk_level: toText(risk_level) || null,
    risk_clause_count: risk_clause_count,
    summary: toText(pick(rec, ['summary', 'overview', 'review_summary', 'conclusion_text', '摘要', '结论'])),
    dims,
    risk_clauses,
    review_check,
    adverse_opinions: adverse,
    debate_log: debate,
    unresolved_issues: unresolved,
    suggestions: sugs,
  }
}

function scorePctOf(v: number | null): number { return Math.round(v ?? 0) }
function verdictLabel(v: string): string {
  const s = (v || '').toString()
  if (/disputed|争议/.test(s)) return '存在争议'
  if (/approved|通过|一致/.test(s)) return '裁决通过'
  return s
}

async function showReport(row: HistoryRow) {
  reportLoading.value = true
  reportDlg.value = true
  try {
    const resp: any = await contractApi.report(row.id)
    report.value = normalizeReport(resp, row)
  } catch {
    report.value = null
  } finally {
    reportLoading.value = false
  }
}

async function downloadOptimized(row: HistoryRow) {
  try {
    const r: any = await contractApi.optimize(row.id)
    const filename = r?.filename || `${row.title || '合同'}_优化建议.md`
    const markdown = r?.markdown || ''
    const blob = new Blob(['﻿' + markdown], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    ElMessage.success('优化文本已开始下载')
  } catch { /* 拦截器已提示 */ }
}

async function removeRow(row: HistoryRow) {
  try {
    await contractApi.remove(row.id)
    ElMessage.success('合同记录已删除')
    loadHistory()
  } catch { /* 拦截器已提示 */ }
}

/* 模板里用到的辅助函数（为了 tsc 引用保持一致） */
const min = Math.min

/* ---------------- 生命周期 ---------------- */
onBeforeUnmount(() => stopReviewTimer())

loadHistory()
</script>

<style lang="scss" scoped>
.page { display: flex; flex-direction: column; gap: 16px; }

.top-bar { display: flex; align-items: center; gap: 22px; flex-wrap: wrap; }
.quota { display: flex; align-items: center; gap: 14px; min-width: 300px; }
.quota-icon {
  width: 46px; height: 46px; border-radius: 12px; flex: none; display: flex; align-items: center; justify-content: center;
  color: var(--accent); background: rgba(201,169,110,.14); border: 1px solid rgba(201,169,110,.28);
}
.quota-title { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; font-size: 14px; }
.quota-body { font-size: 13px; }

.up { flex: 1; min-width: 340px; }
.up :deep(.el-upload), .up :deep(.el-upload-dragger) { width: 100%; }
.up :deep(.el-upload-dragger) {
  background: rgba(10,22,40,.34); border-color: var(--border); border-radius: 12px; padding: 14px 12px;
}
.up-body { padding: 6px 4px; text-align: center; }
.up-icon { color: var(--accent); }
.up-text b { font-size: 14px; color: var(--text-primary); }
.up-tip { font-size: 12px; margin-top: 6px; }
.up-body.uploading .up-icon { animation: spin 1.2s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.mini-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.mini-stat { text-align: center; padding: 14px 10px; }
.mini-num { font-size: 24px; font-weight: 700; color: var(--text-primary); font-variant-numeric: tabular-nums; }
.mini-num.gold { color: var(--accent); }
.mini-num.green { color: var(--success); }
.mini-num.blue { color: #5aa8e8; }
.mini-label { font-size: 13px; margin-top: 2px; }

.sec { display: inline-flex; align-items: center; gap: 8px; }
.row-title { display: inline-flex; align-items: center; gap: 6px; color: var(--text-primary); font-weight: 500; }
.type-cell { display: inline-flex; align-items: center; gap: 6px; cursor: pointer; }
.type-edit { color: var(--text-muted); font-size: 12px; }
.type-cell:hover .type-edit { color: var(--accent); }
.type-hint { font-size: 12px; margin-bottom: 8px; }
.score-cell .el-progress { margin: 0 auto; }
.time { font-size: 13px; }
.ops { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }

/* 审查进度对话框 */
.review-run { text-align: center; padding: 6px 0 2px; }
.run-ring { position: relative; width: 96px; height: 96px; margin: 0 auto 14px; }
.run-svg { width: 100%; height: 100%; transform: rotate(-90deg); }
.run-arc { stroke-dasharray: 201; stroke-dashoffset: 201; animation: arc 1.6s ease-in-out infinite; }
@keyframes arc {
  0% { stroke-dashoffset: 201; }
  60% { stroke-dashoffset: 0; }
  100% { stroke-dashoffset: -201; }
}
.run-center { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); color: var(--accent); }
.run-title { font-size: 17px; font-weight: 600; color: var(--text-primary); margin-bottom: 10px; }
.run-step { font-size: 13px; margin-bottom: 12px; }
.step-index {
  display: inline-block; margin-right: 6px; padding: 1px 8px; border-radius: 999px; font-size: 11px;
  background: rgba(201,169,110,.16); color: var(--accent); border: 1px solid rgba(201,169,110,.35);
}
.run-bar { width: 260px; margin: 0 auto; }

/* 报告对话框 */
.report { display: flex; flex-direction: column; gap: 14px; max-height: 78vh; overflow: auto; padding-right: 4px; }
.rep-loading { min-height: 320px; }
.rep-header { display: flex; align-items: center; gap: 10px; font-weight: 600; }
.rep-icon { display: inline-flex; color: var(--accent); }

.rep-overview { display: flex; gap: 22px; align-items: center; padding: 20px; }
.rep-gauge { display: flex; align-items: center; gap: 14px; flex: none; }
.rep-risk { text-align: center; }
.rep-risk .muted { font-size: 12px; margin-bottom: 6px; }
.rep-main { flex: 1; min-width: 0; }
.rep-title { font-size: 18px; font-weight: 700; color: var(--text-primary); margin-bottom: 6px; }
.rep-meta { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font-size: 12px; margin-bottom: 8px; }
.rep-summary { margin: 0; color: var(--text-secondary); line-height: 1.75; font-size: 13px; white-space: pre-wrap; }

.rep-block { padding: 16px 18px; }
.sub-title { font-size: 15px; font-weight: 600; color: var(--text-primary); display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.sub-title .el-icon { color: var(--accent); }

.dims { display: flex; flex-direction: column; gap: 12px; }
.dim-row { display: flex; align-items: center; gap: 14px; }
.dim-label { width: 84px; font-size: 13px; color: var(--text-secondary); flex: none; text-align: right; }
.dim-bar { flex: 1; }
.dim-val { width: 40px; font-size: 13px; color: var(--accent); font-weight: 600; flex: none; text-align: right; font-variant-numeric: tabular-nums; }

.clauses { display: flex; flex-direction: column; gap: 12px; }
.clause {
  border: 1px solid var(--border); border-left: 3px solid var(--accent); border-radius: 10px;
  background: rgba(10,22,40,.32); padding: 12px 14px;
}
.clause-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.clause-no { font-weight: 700; color: var(--accent); }
.clause-row { font-size: 13px; line-height: 1.7; display: flex; gap: 8px; align-items: flex-start; color: var(--text-secondary); margin-top: 4px; }
.lbl { flex: none; font-size: 11px; padding: 1px 8px; border-radius: 4px; margin-top: 2px; }
.lbl-d { background: rgba(232,93,93,.14); color: #f0a2a2; }
.lbl-s { background: rgba(57,135,229,.16); color: #8fc3f5; }
.lbl-b { background: rgba(201,169,110,.14); color: var(--accent); }
.basis { color: var(--text-secondary); }

.aa-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; padding: 10px 14px; border: 1px solid var(--border); border-radius: 10px; background: rgba(10,22,40,.3); }
.aa-block { margin-top: 12px; }
.aa-label { display: flex; align-items: center; gap: 6px; font-size: 12px; margin-bottom: 8px; }
.aa-opinion {
  font-size: 13px; color: var(--text-secondary); line-height: 1.7; display: flex; gap: 8px; margin-bottom: 6px;
  padding: 8px 10px; border-radius: 8px; background: rgba(232,93,93,.07); border: 1px solid rgba(232,93,93,.18);
}
.dot-red { flex: none; width: 6px; height: 6px; border-radius: 50%; background: var(--danger); margin-top: 7px; }
.debate { display: flex; flex-direction: column; gap: 10px; }
.debate-round { border-left: 2px solid rgba(201,169,110,.4); padding: 2px 0 2px 14px; margin-left: 4px; }
.db-issue { font-size: 13px; font-weight: 600; color: var(--text-primary); margin-bottom: 6px; display: flex; gap: 8px; }
.db-line { font-size: 13px; color: var(--text-secondary); line-height: 1.7; display: flex; gap: 8px; align-items: flex-start; margin-top: 4px; }
.db-tag { flex: none; font-size: 11px; padding: 1px 8px; border-radius: 999px; margin-top: 3px; border: 1px solid var(--border); color: var(--text-secondary); }
.t-major { background: rgba(57,135,229,.14); color: #8fc3f5; border-color: rgba(57,135,229,.35); }
.t-defense { background: rgba(232,93,93,.14); color: #f0a2a2; border-color: rgba(232,93,93,.35); }
.t-arbiter { background: rgba(201,169,110,.16); color: var(--accent); border-color: rgba(201,169,110,.4); }
.unresolve { margin-bottom: 6px; }

.sugs { margin: 0; padding-left: 22px; color: var(--text-secondary); }
.sugs li { line-height: 1.8; margin-bottom: 6px; font-size: 13px; }

@media (max-width: 1100px) {
  .mini-stats { grid-template-columns: repeat(2, 1fr); }
  .rep-overview { flex-direction: column; align-items: flex-start; }
}
</style>
