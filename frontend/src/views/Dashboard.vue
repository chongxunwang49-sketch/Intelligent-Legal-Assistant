<template>
  <div class="page dashboard fade-in">
    <!-- 问候区 -->
    <div class="glass-card hero">
      <div class="hero-left">
        <h2 class="greeting-title gradient-title">{{ greeting }}，{{ displayName || '尊敬的用户' }}</h2>
        <div class="muted sub">
          {{ roleLabel }} · {{ todayLabel }} · 欢迎回到智法通企业级智能法律顾问平台
        </div>
      </div>
      <div class="hero-date muted">
        <el-icon><Calendar /></el-icon>
        <span>{{ todayLabel }}</span>
      </div>
    </div>

    <!-- 统计卡 -->
    <div class="stat-grid">
      <div v-for="card in overviewCards" :key="card.key" class="glass-card stat-card fade-in">
        <div class="stat-icon" :style="{ color: card.color, background: card.bg }">
          <el-icon :size="22"><component :is="card.icon" /></el-icon>
        </div>
        <div class="stat-body">
          <div class="stat-value">{{ overviewVal[card.key] }}</div>
          <div class="muted stat-label">{{ card.label }}</div>
        </div>
      </div>
    </div>

    <!-- 图表区：趋势折线 + 领域环形 -->
    <div class="chart-row">
      <div class="glass-card chart-card">
        <div class="section-title between">
          <span class="sec"><el-icon><DataLine /></el-icon>咨询趋势</span>
          <div class="days-switch">
            <button
              v-for="d in daysOptions"
              :key="d.value"
              :class="{ active: trendDays === d.value }"
              @click="switchTrend(d.value)"
            >{{ d.label }}</button>
          </div>
        </div>
        <div v-loading="trendLoading" class="chart-box">
          <div v-if="trendHas" ref="trendRef" class="chart-inner" />
          <el-empty v-else description="暂无趋势数据" :image-size="80" />
        </div>
      </div>

      <div class="glass-card chart-card">
        <div class="section-title"><el-icon><PieChart /></el-icon>咨询领域分布</div>
        <div v-loading="domainLoading" class="chart-box">
          <div v-if="domainHas" ref="domainRef" class="chart-inner" />
          <el-empty v-else description="暂无领域数据" :image-size="80" />
        </div>
      </div>
    </div>

    <!-- 知识图谱 + 时间旅行 -->
    <div class="glass-card kg-card">
      <div class="section-title between">
        <span class="sec"><el-icon><Connection /></el-icon>法规知识图谱
          <el-tag v-if="kgStatus" size="small" :type="kgOk ? 'success' : 'info'" class="kg-tag">{{ kgStatus }}</el-tag>
        </span>
        <div class="sec-actions">
          <el-button size="small" :icon="RefreshRight" @click="rebuildGraph">重建图谱</el-button>
        </div>
      </div>

      <div v-if="kgOk && graphNodes.length" class="kg-main">
        <div class="graph-zone">
          <div ref="graphRef" v-loading="graphLoading" class="graph-canvas" />
        </div>
        <div class="graph-stats muted" v-if="graphStatsShow">
          <div class="gs-title"><el-icon><DataBoard /></el-icon>图谱统计</div>
          <div class="gs-line"><span>可检索文档</span><b>{{ graphStatsShow.available ?? '—' }}</b></div>
          <div class="gs-line"><span>图谱节点</span><b>{{ graphStatsShow.total ?? '—' }}</b></div>
          <div v-for="(label, i) in graphByLabel" :key="i" class="gs-line"><span class="dot" :style="{ background: labelColor(i) }"></span><span>{{ label.name }}</span><b>{{ label.count }}</b></div>
        </div>
      </div>
      <el-empty
        v-else
        description="图谱暂不可用"
        :image-size="90"
      >
        <el-button v-if="graphLoading" type="primary" :icon="RefreshRight" loading disabled>构建中…</el-button>
      </el-empty>

      <!-- 时间旅行：按日期查看生效法规 -->
      <el-divider class="kg-divider"><span class="tt-title"><el-icon><Clock /></el-icon> 时间旅行 · 回溯历史时点的有效法规</span></el-divider>
      <div class="time-travel">
        <div class="tt-bar">
          <el-date-picker
            v-model="lawDate"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择时点日期"
            :clearable="false"
            style="width: 180px"
          />
          <el-input
            v-model="lawKeyword"
            placeholder="法规关键词(可选)"
            clearable
            style="width: 220px"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-button type="primary" :icon="Search" :loading="lawLoading" @click="searchLaws">查询时点法规</el-button>
        </div>

        <div v-if="laws.length" class="law-list">
          <div v-for="(law, i) in laws" :key="i" class="law-item">
            <div class="law-title">
              <el-tag size="small" class="law-ver">{{ law.version || 'v1' }}</el-tag>
              <span class="law-name">{{ law.title }}</span>
            </div>
            <div class="muted law-meta">
              <span v-if="law.effective_date"><el-icon><Clock /></el-icon>生效 {{ law.effective_date }}</span>
              <span v-if="law.abolished_date" class="abol"><el-icon><Stamp /></el-icon>废止 {{ law.abolished_date }}</span>
              <span v-else class="abol-active">现行有效</span>
            </div>
          </div>
        </div>
        <div v-else-if="!lawLoading && lawSearched" class="law-empty muted">该时点未查询到有效法规，可调整日期或关键词</div>
      </div>
    </div>

    <!-- 最近活动 -->
    <div class="glass-card">
      <div class="section-title"><el-icon><Odometer /></el-icon>最近活动</div>
      <div v-loading="recentLoading">
        <el-empty v-if="!recentItems.length" description="暂无最近活动" :image-size="80" />
        <div v-else class="recent-list">
          <div v-for="(item, i) in recentItems" :key="i" class="recent-item">
            <div class="recent-icon" :class="item.type || 'default'">
              <el-icon><component :is="recentIcon(item.type)" /></el-icon>
            </div>
            <div class="recent-main">
              <div class="recent-title">{{ item.title }}<el-tag size="small" class="recent-tag" :type="typeTag(item.type)">{{ typeLabel(item.type) }}</el-tag></div>
              <div class="muted recent-detail">{{ item.detail }}</div>
            </div>
            <div class="muted recent-time">{{ item.time }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import {
  Calendar, ChatDotRound, Clock, Connection, DataBoard, DataLine, DocumentChecked, FolderOpened,
  Odometer, PieChart, RefreshRight, Search, Stamp, User,
} from '@element-plus/icons-vue'
import { dashboardApi } from '@/api/dashboard'
import { useUserStore } from '@/stores/user'

/* ---------------- 基础工具与常量 ---------------- */
type Component = any

/** 校验通过的深色类别色板（蓝→橙→青→金→紫红→绿→紫→红），适配深色海蓝表面 */
const CATS = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767']
const GOLD = '#c9a96e'
const TOOLTIP: any = {
  backgroundColor: 'rgba(15,31,56,.92)',
  borderColor: 'rgba(201,169,110,.4)',
  borderWidth: 1,
  textStyle: { color: '#e8edf5', fontSize: 12 },
  extraCssText: 'box-shadow:0 6px 18px rgba(0,0,0,.4);border-radius:8px;',
}

function asList(resp: any): any[] {
  if (Array.isArray(resp)) return resp
  if (resp && Array.isArray(resp.items)) return resp.items
  return []
}
function pad(n: number) { return n < 10 ? '0' + n : '' + n }
function fmtDate(d: Date) { return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` }

const user = useUserStore()
const todayLabel = fmtDate(new Date())
const displayName = computed(() => user.userInfo?.username || '')
const roleLabel = computed(() => (user.isAdmin ? '超级管理员' : user.isLawyer ? '法务负责人' : '普通用户'))
const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 12) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

/* ---------------- 统计卡（数字滚动） ---------------- */
const overviewCards = [
  { key: 'today_queries', label: '今日法律咨询', icon: ChatDotRound, color: GOLD, bg: 'rgba(201,169,110,.14)' },
  { key: 'today_contract_reviews', label: '今日合同审查', icon: DocumentChecked, color: '#3987e5', bg: 'rgba(57,135,229,.16)' },
  { key: 'knowledge_documents', label: '知识库文档', icon: FolderOpened, color: '#46c07b', bg: 'rgba(70,192,123,.14)' },
  { key: 'total_users', label: '平台总用户', icon: User, color: '#9d8ce0', bg: 'rgba(157,140,224,.16)' },
]
const overviewVal = reactive<Record<string, string>>({
  today_queries: '0', today_contract_reviews: '0', knowledge_documents: '0', total_users: '0',
})

function fmt(n: number) { return (n || 0).toLocaleString('zh-CN') }

function animateNumber(key: string, to: number) {
  const from = Number((overviewVal[key] || '0').replace(/,/g, '')) || 0
  if (from === to) { overviewVal[key] = fmt(to); return }
  const dur = 900
  let start: number | null = null
  const step = (ts: number) => {
    if (start === null) start = ts
    const p = Math.min(1, (ts - start) / dur)
    const eased = 1 - Math.pow(1 - p, 3)
    const cur = Math.round(from + (to - from) * eased)
    overviewVal[key] = fmt(cur)
    if (p < 1) requestAnimationFrame(step)
  }
  requestAnimationFrame(step)
}

async function loadOverview() {
  try {
    const d: any = await dashboardApi.overview()
    animateNumber('today_queries', Number(d?.today_queries) || 0)
    animateNumber('today_contract_reviews', Number(d?.today_contract_reviews) || 0)
    animateNumber('knowledge_documents', Number(d?.knowledge_documents) || 0)
    animateNumber('total_users', Number(d?.total_users) || 0)
  } catch { /* 静默 */ }
}

/* ---------------- 趋势折线 ---------------- */
const daysOptions = [
  { label: '近 7 天', value: 7 },
  { label: '近 30 天', value: 30 },
  { label: '近 90 天', value: 90 },
]
const trendDays = ref(30)
const trendLoading = ref(false)
const trendItems = ref<any[]>([])
const trendHas = computed(() => trendItems.value.length > 0)
const trendRef = ref<HTMLDivElement>()
const trendChart = ref<echarts.ECharts | null>(null)

let instances: echarts.ECharts[] = []
function ensureChart(el: HTMLElement, holder: { value: echarts.ECharts | null }) {
  if (holder.value) return holder.value
  const c = echarts.init(el)
  holder.value = c
  instances.push(c)
  return c
}
function onResize() { instances.forEach((c) => c.resize()) }

async function switchTrend(days: number) {
  trendDays.value = days
  trendLoading.value = true
  try {
    const d: any = await dashboardApi.trends({ days })
    trendItems.value = asList(d)
  } catch {
    trendItems.value = []
  } finally {
    trendLoading.value = false
  }
  await nextTick()
  renderTrend()
}

function renderTrend() {
  const el = trendRef.value
  if (!el || !trendHas.value) return
  const chart = ensureChart(el, trendChart)
  const dates = trendItems.value.map((i) => i.date ?? i.date_time ?? '')
  const counts = trendItems.value.map((i) => Number(i.count) || 0)
  const step = Math.max(1, Math.ceil(dates.length / 12))
  chart.setOption({
    tooltip: { ...TOOLTIP, trigger: 'axis' },
    grid: { left: 8, right: 16, top: 18, bottom: 4, containLabel: true },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: false,
      axisLine: { lineStyle: { color: 'rgba(140,160,190,.28)' } },
      axisTick: { show: false },
      axisLabel: { color: '#8c9ab5', interval: index => index % step === 0 },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: { lineStyle: { color: 'rgba(140,160,190,.1)' } },
      axisLabel: { color: '#8c9ab5' },
    },
    series: [
      {
        name: '咨询量',
        type: 'line',
        smooth: true,
        showSymbol: false,
        symbol: 'circle',
        symbolSize: 9,
        data: counts,
        lineStyle: { width: 2, color: GOLD },
        itemStyle: { color: GOLD },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(201,169,110,.32)' },
              { offset: 1, color: 'rgba(201,169,110,.02)' },
            ],
          },
        },
      },
    ],
  } as any)
}

/* ---------------- 领域分布（环形饼图） ---------------- */
const domainLoading = ref(false)
const domainItems = ref<any[]>([])
const domainHas = computed(() => domainItems.value.length > 0)
const domainRef = ref<HTMLDivElement>()
const domainChart = ref<echarts.ECharts | null>(null)

async function loadDomains() {
  domainLoading.value = true
  try {
    const d: any = await dashboardApi.domains()
    domainItems.value = asList(d)
  } catch {
    domainItems.value = []
  } finally {
    domainLoading.value = false
  }
  await nextTick()
  renderDomain()
}

function renderDomain() {
  const el = domainRef.value
  if (!el || !domainHas.value) return
  const chart = ensureChart(el, domainChart)
  const items = domainItems.value.slice(0, 7)
  const rest = domainItems.value.slice(7)
  const extra = rest.length
    ? { name: '其他', value: rest.reduce((s: number, i) => s + (Number(i.value) || 0), 0) }
    : null
  const data = extra ? [...items, extra].map((i: any, idx: number) => ({ name: i.name, value: Number(i.value) || 0, itemStyle: { color: CATS[idx % CATS.length] } }))
    : items.map((i: any, idx: number) => ({ name: i.name, value: Number(i.value) || 0, itemStyle: { color: CATS[idx % CATS.length] } }))
  const total = data.reduce((s: number, i) => s + (Number(i.value) || 0), 0)
  chart.setOption({
    tooltip: { ...TOOLTIP, trigger: 'item', formatter: (p: any) => `${p.marker}${p.name}<br/>咨询量：<b>${p.value}</b>（${p.percent}%）` },
    color: CATS,
    legend: {
      type: 'scroll',
      orient: 'vertical',
      right: 6,
      top: 'middle',
      icon: 'circle',
      itemWidth: 9,
      itemHeight: 9,
      textStyle: { color: '#8c9ab5', fontSize: 12 },
    },
    series: [
      {
        type: 'pie',
        radius: ['46%', '68%'],
        center: ['36%', '50%'],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: 'rgba(10,22,40,.9)', borderWidth: 2 },
        label: { show: false },
        emphasis: {
          scaleSize: 6,
          label: { show: true, color: '#e8edf5', fontSize: 13, fontWeight: 600, formatter: '{b}\n{d}%' },
        },
        data,
      },
    ],
    title: {
      text: (total || 0).toLocaleString('zh-CN'),
      subtext: '咨询总量',
      left: '36%',
      top: '38%',
      textAlign: 'center',
      textStyle: { color: GOLD, fontSize: 24, fontWeight: 700 },
      subtextStyle: { color: '#8c9ab5', fontSize: 12 },
    },
  } as any)
}

/* ---------------- 知识图谱 ---------------- */
const graphLoading = ref(false)
const graphNodes = ref<any[]>([])
const graphLinks = ref<any[]>([])
const graphCats = ref<any[]>([])
const graphSource = ref('')
const graphRef = ref<HTMLDivElement>()
const graphChart = ref<echarts.ECharts | null>(null)
const graphStats = ref<any>(null)
const kgOk = computed(() => graphSource.value === 'neo4j' && graphNodes.value.length > 0)
const kgStatus = computed(() => {
  if (!graphSource.value) return '图谱暂不可用'
  return graphSource.value === 'neo4j' ? '图谱数据已就绪' : '图谱数据源异常'
})
const graphStatsShow = computed(() => (graphStats.value && typeof graphStats.value === 'object' ? graphStats.value : null))
const graphByLabel = computed(() => {
  const st = graphStats.value
  if (!st || !st.by_label) return []
  if (Array.isArray(st.by_label)) return st.by_label.map((x: any) => ({ name: x.label ?? x.name ?? x.category ?? '', count: x.count ?? x.value ?? 0 }))
  return Object.entries(st.by_label).map(([k, v]) => ({ name: k, count: Number(v) || 0 }))
})
function labelColor(idx: number) { return CATS[idx % CATS.length] }

function catIndex(node: any): number {
  const cat = node.category
  if (typeof cat === 'number') return cat
  const i = graphCats.value.findIndex((c) => c.name === cat || String(c.name) === String(cat))
  return i >= 0 ? i : 0
}

async function loadGraph() {
  graphLoading.value = true
  try {
    const d: any = await dashboardApi.graphKnowledge()
    graphSource.value = d?.source || ''
    graphNodes.value = asList(d && d.nodes ? { items: d.nodes } : [])
    graphLinks.value = asList(d && d.links ? { items: d.links } : [])
    graphCats.value = Array.isArray(d?.categories)
      ? d.categories.map((c: any) => (c && typeof c === 'object' ? c : { name: String(c ?? '') }))
      : []
  } catch {
    graphSource.value = ''
    graphNodes.value = []
    graphLinks.value = []
    graphCats.value = []
  } finally {
    graphLoading.value = false
  }
  loadGraphStats()
  await nextTick()
  renderGraph()
}

async function loadGraphStats() {
  try {
    graphStats.value = await dashboardApi.graphStats()
  } catch {
    graphStats.value = null
  }
}

function renderGraph() {
  const el = graphRef.value
  if (!el || !kgOk.value) return
  const prev = graphChart.value
  if (prev) {
    instances = instances.filter((c) => c !== prev)
    prev.dispose()
  }
  const chart = echarts.init(el)
  graphChart.value = chart
  instances.push(chart)

  const cats = graphCats.value.map((c: any, i: number) => ({
    name: c.name ?? `类别${i + 1}`,
    itemStyle: { color: CATS[i % CATS.length] },
  }))

  const nodeColor = (n: any) => CATS[catIndex(n) % CATS.length]

  const nodes = graphNodes.value.map((n: any) => {
    const deg = Number(n.degree) || 0
    const base = Number(n.symbolSize) > 0 ? Number(n.symbolSize) : 14 + Math.min(deg * 1.4, 30)
    const idx = catIndex(n)
    return {
      id: String(n.id),
      name: n.name || String(n.id),
      category: idx,
      symbolSize: Math.max(16, Math.min(base, 64)),
      itemStyle: { color: nodeColor(n), borderColor: GOLD, borderWidth: 1.6, shadowBlur: 12, shadowColor: 'rgba(201,169,110,.35)' },
      label: { show: true, color: '#e3e9f4', fontSize: 11 },
    }
  })
  const links = graphLinks.value.map((l: any) => ({
    source: String(l.source),
    target: String(l.target),
    relation: l.relation || '',
    label: { show: graphLinks.value.length <= 80, formatter: l.relation || '', fontSize: 9, color: 'rgba(165,178,200,.9)' },
    lineStyle: { color: 'rgba(140,160,190,.4)', opacity: 0.55, curveness: 0.12, width: 1 },
  }))

  const names = [...new Set(nodes.map((n: any) => cats[n.category] ? cats[n.category].name : ''))].filter(Boolean)
  chart.setOption({
    tooltip: {
      ...TOOLTIP,
      formatter: (p: any) => {
        if (p.dataType === 'edge') return `${p.data.relation || '关联'}<br/>${p.data.source} → ${p.data.target}`
        const n = p.data || {}
        return `<b>${n.name || ''}</b><br/>类别：${n.category != null ? (cats[n.category]?.name || '') : '—'}<br/>关联度：${n.degree ?? '—'}`
      },
    },
    legend: names.length > 1 ? {
      data: names,
      orient: 'horizontal',
      bottom: 0,
      icon: 'circle',
      itemWidth: 9,
      itemHeight: 9,
      textStyle: { color: '#8c9ab5', fontSize: 11 },
    } : undefined,
    series: [
      {
        type: 'graph',
        layout: 'force',
        roam: true,
        draggable: true,
        data: nodes,
        links,
        categories: cats,
        force: { repulsion: 320, gravity: 0.12, edgeLength: [70, 150], layoutAnimation: false },
        emphasis: { focus: 'adjacency', lineStyle: { width: 2.4, color: GOLD, opacity: 0.95 } },
        scaleLimit: { min: 0.4, max: 4 },
      },
    ],
  } as any)
}

async function rebuildGraph() {
  try {
    const r: any = await dashboardApi.graphRebuild()
    ElMessage.success(typeof r === 'string' ? r : r?.message || '图谱重建请求已提交')
    loadGraph()
  } catch {
    /* 失败静默忽略 */
  }
}

/* ---------------- 时间旅行 ---------------- */
const lawDate = ref(fmtDate(new Date()))
const lawKeyword = ref('')
const laws = ref<any[]>([])
const lawLoading = ref(false)
const lawSearched = ref(false)

function asLaws(resp: any): any[] {
  if (Array.isArray(resp)) return resp
  for (const k of ['items', 'laws', 'versions', 'law_versions']) {
    if (resp && Array.isArray(resp[k])) return resp[k]
  }
  return []
}
async function searchLaws() {
  if (!lawDate.value) return
  lawLoading.value = true
  lawSearched.value = false
  try {
    const resp: any = await dashboardApi.lawVersions({ at_date: lawDate.value, keyword: lawKeyword.value || undefined })
    laws.value = asLaws(resp)
  } catch {
    laws.value = []
  } finally {
    lawLoading.value = false
    lawSearched.value = true
  }
}

/* ---------------- 最近活动 ---------------- */
const recentLoading = ref(false)
const recentItems = ref<any[]>([])
function typeLabel(t: string) {
  if (t === 'qa') return '法律问答'
  if (t === 'contract') return '合同审查'
  return '系统'
}
function typeTag(t: string): any {
  if (t === 'qa') return 'primary'
  if (t === 'contract') return 'warning'
  return 'info'
}
function recentIcon(t: string): Component {
  if (t === 'qa') return ChatDotRound
  if (t === 'contract') return DocumentChecked
  return Odometer
}
async function loadRecent() {
  recentLoading.value = true
  try {
    const d: any = await dashboardApi.recent()
    recentItems.value = asList(d)
  } catch {
    recentItems.value = []
  } finally {
    recentLoading.value = false
  }
}

/* ---------------- 生命周期 ---------------- */
onMounted(() => {
  window.addEventListener('resize', onResize)
  loadOverview()
  loadDomains()
  switchTrend(trendDays.value)
  loadGraph()
  loadRecent()
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  instances.forEach((c) => c.dispose())
  instances = []
})
</script>

<style lang="scss" scoped>
.page { display: flex; flex-direction: column; gap: 16px; }

.hero {
  display: flex; justify-content: space-between; align-items: center; gap: 16px;
  padding: 20px 22px;
  background:
    radial-gradient(600px 140px at 12% 0%, rgba(201,169,110,.10), transparent 70%),
    radial-gradient(700px 160px at 92% 100%, rgba(57,135,229,.12), transparent 70%),
    var(--card);
}
.greeting-title { font-size: 22px; font-weight: 700; margin: 0 0 6px; }
.sub { font-size: 13px; letter-spacing: .3px; }
.hero-date { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; padding: 6px 12px; border: 1px solid var(--border); border-radius: 999px; }

.stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.stat-card { display: flex; align-items: center; gap: 14px; padding: 18px; }
.stat-icon {
  width: 46px; height: 46px; border-radius: 12px; display: flex; align-items: center; justify-content: center; flex: none;
  border: 1px solid rgba(201,169,110,.25);
}
.stat-value {
  font-size: 26px; font-weight: 700; color: var(--text-primary); line-height: 1.1; font-variant-numeric: tabular-nums;
}
.stat-label { font-size: 13px; margin-top: 4px; }
.stat-card:hover .stat-value { color: var(--accent); transition: color .2s; }

.chart-row { display: grid; grid-template-columns: 1.6fr 1fr; gap: 16px; }
.sec { display: inline-flex; align-items: center; gap: 8px; }
.days-switch {
  display: inline-flex; gap: 2px; padding: 2px; border: 1px solid var(--border); border-radius: 8px; background: rgba(10,22,40,.4);
}
.days-switch button {
  border: none; background: transparent; color: var(--text-secondary); padding: 3px 10px; border-radius: 6px;
  cursor: pointer; font-size: 12px; transition: all .2s;
}
.days-switch button.active { background: linear-gradient(135deg, var(--primary-light), var(--primary-lighter)); color: #fff; }
.chart-box { position: relative; }
.chart-inner { width: 100%; height: 300px; }

.kg-card { padding-bottom: 14px; }
.kg-tag { margin-left: 8px; }
.kg-main { display: grid; grid-template-columns: 1fr 240px; gap: 18px; margin-top: 4px; }
.graph-zone { min-height: 420px; }
.graph-canvas { width: 100%; height: 420px; }
.graph-stats {
  border-left: 1px solid var(--border); padding-left: 18px; font-size: 13px; display: flex; flex-direction: column; gap: 10px;
}
.gs-title { display: inline-flex; align-items: center; gap: 6px; color: var(--text-primary); font-weight: 600; margin-bottom: 2px; }
.gs-line { display: flex; align-items: center; gap: 8px; justify-content: space-between; }
.gs-line .dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }
.gs-line b { color: var(--accent); font-weight: 600; font-variant-numeric: tabular-nums; }
.kg-divider { border-color: var(--border); margin: 18px 0 14px; }
.tt-title { color: var(--text-primary); font-size: 13px; display: inline-flex; align-items: center; gap: 6px; }

.time-travel .tt-bar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.law-list { margin-top: 14px; display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.law-item {
  border: 1px solid var(--border); border-left: 3px solid var(--accent); border-radius: 10px;
  padding: 10px 14px; background: rgba(10,22,40,.32);
}
.law-title { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.law-ver { background: rgba(201,169,110,.16); border-color: rgba(201,169,110,.4); color: var(--accent); }
.law-name { font-weight: 600; color: var(--text-primary); }
.law-meta { display: flex; gap: 14px; align-items: center; font-size: 12px; }
.law-meta .el-icon { margin-right: 4px; vertical-align: -2px; }
.abol { color: var(--danger); }
.abol-active { color: var(--success); }
.law-empty { margin-top: 14px; text-align: center; padding: 18px; }

.recent-list { display: flex; flex-direction: column; }
.recent-item { display: flex; gap: 14px; align-items: flex-start; padding: 12px 4px; border-bottom: 1px solid rgba(26,58,92,.35); }
.recent-item:last-child { border-bottom: none; }
.recent-icon {
  width: 38px; height: 38px; border-radius: 10px; flex: none; display: flex; align-items: center; justify-content: center; font-size: 18px;
}
.recent-icon.qa { color: #3987e5; background: rgba(57,135,229,.14); }
.recent-icon.contract { color: var(--accent); background: rgba(201,169,110,.14); }
.recent-icon.default { color: var(--text-secondary); background: rgba(140,154,181,.12); }
.recent-main { flex: 1; min-width: 0; }
.recent-title { font-weight: 600; color: var(--text-primary); display: flex; align-items: center; gap: 8px; }
.recent-tag { font-size: 11px; }
.recent-detail { font-size: 13px; margin-top: 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.recent-time { font-size: 12px; flex: none; white-space: nowrap; }

@media (max-width: 1280px) {
  .chart-row { grid-template-columns: 1fr; }
  .kg-main { grid-template-columns: 1fr; }
  .graph-stats { border-left: none; border-top: 1px solid var(--border); padding: 12px 0 0; flex-direction: row; flex-wrap: wrap; }
}
@media (max-width: 900px) {
  .stat-grid { grid-template-columns: repeat(2, 1fr); }
  .law-list { grid-template-columns: 1fr; }
}
</style>
