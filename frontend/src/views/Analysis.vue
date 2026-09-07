<template>
  <div class="page analysis fade-in">
    <!-- 筛选栏 -->
    <div class="glass-card filter-bar between center">
      <div class="filter-left">
        <span class="filter-label"><el-icon><DataAnalysis /></el-icon>统计时间范围</span>
        <div class="days-switch">
          <button
            v-for="d in daysOptions"
            :key="d.value"
            :class="{ active: days === d.value }"
            @click="switchDays(d.value)"
          >{{ d.label }}</button>
        </div>
      </div>
      <div class="muted" style="font-size: 12px">数据来源于咨询问答 / 合同审查会话的脱敏统计</div>
    </div>

    <!-- 行1：热点类别 + 高频引用法规 -->
    <div class="chart-row">
      <div class="glass-card chart-card">
        <div class="section-title"><el-icon><Histogram /></el-icon>热点咨询类别</div>
        <div v-loading="loading.topics" class="chart-box">
          <div v-if="hotHas" ref="topicRef" class="chart-inner" />
          <el-empty v-else description="暂无热点数据" :image-size="80" />
        </div>
      </div>
      <div class="glass-card chart-card">
        <div class="section-title"><el-icon><Reading /></el-icon>高频引用法规</div>
        <div v-loading="loading.citations" class="chart-box">
          <div v-if="citationHas" ref="citationRef" class="chart-inner" />
          <el-empty v-else description="暂无引用数据" :image-size="80" />
        </div>
      </div>
    </div>

    <!-- 行2：咨询趋势 -->
    <div class="glass-card chart-card">
      <div class="section-title"><el-icon><TrendCharts /></el-icon>咨询 / 审查趋势（按日）</div>
      <div v-loading="loading.trends" class="chart-box">
        <div v-if="trendHas" ref="trendRef" class="chart-inner chart-inner--lg" />
        <el-empty v-else description="暂无趋势数据" :image-size="80" />
      </div>
    </div>

    <!-- 行3：用户聚类气泡 -->
    <div class="glass-card chart-card">
      <div class="section-title between">
        <span class="sec"><el-icon><Coordinate /></el-icon>用户活跃聚类</span>
        <span class="muted note">横轴 = 提问次数，纵轴 = 平均响应时延(ms)，气泡大小 = 领域多样性</span>
      </div>
      <div v-loading="loading.clusters" class="chart-box">
        <div v-if="clusterHas" ref="clusterRef" class="chart-inner chart-inner--md" />
        <el-empty v-else description="暂无聚类数据" :image-size="80" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import * as echarts from 'echarts'
import { Coordinate, DataAnalysis, Histogram, Reading, TrendCharts } from '@element-plus/icons-vue'
import { analysisApi } from '@/api/analysis'

const GOLD = '#c9a96e'
const BLUE = '#3987e5'
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
function pct(v: any): string {
  const n = Number(v)
  if (Number.isNaN(n)) return '—'
  return `${(n * 100).toFixed(1)}%`
}
function fmtNum(v: any): string {
  const n = Number(v)
  return Number.isNaN(n) ? '0' : n.toLocaleString('zh-CN')
}

const daysOptions = [
  { label: '近 7 天', value: 7 },
  { label: '近 30 天', value: 30 },
  { label: '近 90 天', value: 90 },
]
const days = ref(30)
const loading = reactive({ topics: false, citations: false, trends: false, clusters: false })

const hotItems = ref<any[]>([])
const citationItems = ref<any[]>([])
const trendItems = ref<any[]>([])
const clusterItems = ref<any[]>([])

const hotHas = computed(() => hotItems.value.length > 0)
const citationHas = computed(() => citationItems.value.length > 0)
const trendHas = computed(() => trendItems.value.length > 0)
const clusterHas = computed(() => clusterItems.value.length > 0)

const topicRef = ref<HTMLDivElement>()
const citationRef = ref<HTMLDivElement>()
const trendRef = ref<HTMLDivElement>()
const clusterRef = ref<HTMLDivElement>()

const topicChart = ref<echarts.ECharts | null>(null)
const citationChart = ref<echarts.ECharts | null>(null)
const trendChart = ref<echarts.ECharts | null>(null)
const clusterChart = ref<echarts.ECharts | null>(null)

let instances: echarts.ECharts[] = []
function ensureChart(el: HTMLElement, holder: { value: echarts.ECharts | null }) {
  if (holder.value) return holder.value
  const c = echarts.init(el)
  holder.value = c
  instances.push(c)
  return c
}
function onResize() { instances.forEach((c) => c.resize()) }

/* ---------- 数据加载 ---------- */
async function loadTopics() {
  loading.topics = true
  try {
    const d: any = await analysisApi.hotTopics({ days: days.value })
    hotItems.value = asList(d)
  } catch {
    hotItems.value = []
  } finally {
    loading.topics = false
  }
  await nextTick()
  renderTopics()
}
async function loadCitations() {
  loading.citations = true
  try {
    const d: any = await analysisApi.citations({ days: days.value })
    citationItems.value = asList(d)
  } catch {
    citationItems.value = []
  } finally {
    loading.citations = false
  }
  await nextTick()
  renderCitations()
}
async function loadTrend() {
  loading.trends = true
  try {
    const d: any = await analysisApi.trends({ days: days.value, granularity: 'day' })
    trendItems.value = asList(d)
  } catch {
    trendItems.value = []
  } finally {
    loading.trends = false
  }
  await nextTick()
  renderTrend()
}
async function loadClusters() {
  loading.clusters = true
  try {
    const d: any = await analysisApi.clusters({ days: days.value })
    clusterItems.value = asList(d)
  } catch {
    clusterItems.value = []
  } finally {
    loading.clusters = false
  }
  await nextTick()
  renderClusters()
}

function switchDays(v: number) {
  if (days.value === v) return
  days.value = v
  loadTopics(); loadCitations(); loadTrend(); loadClusters()
}

/* ---------- 图1：热点类别柱状（Top1 金色高亮） ---------- */
function renderTopics() {
  const el = topicRef.value
  if (!el || !hotHas.value) return
  const chart = ensureChart(el, topicChart)
  const cats = hotItems.value.map((i) => i.category ?? i.name ?? '未知类别')
  const counts = hotItems.value.map((i) => Number(i.count) || 0)
  const topIdx = counts.indexOf(Math.max(...counts))
  const data = counts.map((v, i) => ({
    value: v,
    itemStyle: i === topIdx ? { color: GOLD, shadowBlur: 10, shadowColor: 'rgba(201,169,110,.45)' } : { color: BLUE },
  }))
  const total = counts.reduce((s, n) => s + n, 0)
  chart.setOption({
    tooltip: {
      ...TOOLTIP,
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        const p = Array.isArray(params) ? params[0] : params
        const idx = p.dataIndex
        const it: any = hotItems.value[idx] || {}
        const ratio = total ? ((Number(it.count) || 0) / total) : 0
        const samples = Array.isArray(it.samples) ? it.samples.slice(0, 3) : []
        let html = `<div style="font-weight:600">${it.category || p.name}</div>`
        html += `<div>咨询量：<b>${fmtNum(it.count)}</b> · 占比 ${pct(ratio)}</div>`
        if (samples.length) html += `<div style="color:#8c9ab5;max-width:240px;line-height:1.6;margin-top:2px">样例：${samples.join('；')}</div>`
        return html
      },
    },
    grid: { left: 8, right: 16, top: 16, bottom: 40, containLabel: true },
    xAxis: {
      type: 'category',
      data: cats,
      axisLine: { lineStyle: { color: 'rgba(140,160,190,.28)' } },
      axisTick: { show: false },
      axisLabel: { color: '#8c9ab5', interval: 0, rotate: cats.length > 6 ? 28 : 0, width: 88, overflow: 'truncate' },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: { lineStyle: { color: 'rgba(140,160,190,.1)' } },
      axisLabel: { color: '#8c9ab5' },
    },
    series: [{ type: 'bar', data, barMaxWidth: 22, itemStyle: { borderRadius: [4, 4, 0, 0] }, label: { show: false } }],
  } as any)
}

/* ---------- 图2：引用统计条形 ---------- */
function renderCitations() {
  const el = citationRef.value
  if (!el || !citationHas.value) return
  const chart = ensureChart(el, citationChart)
  const items = citationItems.value.slice(0, 10).reverse()
  const titles = items.map((i) => i.title ?? i.name ?? '未知法规')
  const counts = items.map((i) => Number(i.citation_count) || 0)
  const max = Math.max(...counts, 1)
  chart.setOption({
    tooltip: {
      ...TOOLTIP,
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        const p = Array.isArray(params) ? params[0] : params
        const it: any = items[p.dataIndex] || {}
        let html = `<div style="font-weight:600;max-width:280px">${it.title || ''}</div>`
        html += `<div>被引用：<b>${fmtNum(it.citation_count)}</b> 次</div>`
        html += `<div>正面倾向：<b style="color:${Number(it.positive_rate) >= 0.5 ? '#46c07b' : '#e6a23c'}">${pct(it.positive_rate)}</b></div>`
        return html
      },
    },
    grid: { left: 8, right: 36, top: 12, bottom: 8, containLabel: true },
    xAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: { lineStyle: { color: 'rgba(140,160,190,.1)' } },
      axisLabel: { color: '#8c9ab5' },
    },
    yAxis: {
      type: 'category',
      data: titles,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#8c9ab5', width: 150, overflow: 'truncate' },
    },
    series: [{
      type: 'bar',
      data: counts,
      barMaxWidth: 14,
      showBackground: true,
      backgroundStyle: { color: 'rgba(255,255,255,.04)', borderRadius: 7 },
      itemStyle: {
        borderRadius: 7,
        color: {
          type: 'linear', x: 0, y: 0, x2: 1, y2: 0,
          colorStops: [
            { offset: 0, color: '#3987e5' },
            { offset: 1, color: '#6aa9ef' },
          ],
        },
      },
      label: { show: true, position: 'right', color: '#c6cfe0', fontSize: 11 },
    }],
    dataZoom: items.length > 8 ? [{ type: 'inside', yAxisIndex: 0 }] : [],
  } as any)
}

/* ---------- 图3：咨询/审查趋势折线 ---------- */
function renderTrend() {
  const el = trendRef.value
  if (!el || !trendHas.value) return
  const chart = ensureChart(el, trendChart)
  const dates = trendItems.value.map((i) => i.date ?? i.date_time ?? '')
  const counts = trendItems.value.map((i) => Number(i.count) || 0)
  const step = Math.max(1, Math.ceil(dates.length / 14))
  chart.setOption({
    tooltip: { ...TOOLTIP, trigger: 'axis' },
    grid: { left: 8, right: 16, top: 18, bottom: 6, containLabel: true },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: false,
      axisLine: { lineStyle: { color: 'rgba(140,160,190,.28)' } },
      axisTick: { show: false },
      axisLabel: { color: '#8c9ab5', interval: (idx: number) => idx % step === 0 },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: { lineStyle: { color: 'rgba(140,160,190,.1)' } },
      axisLabel: { color: '#8c9ab5' },
    },
    series: [{
      name: '会话量',
      type: 'line',
      smooth: true,
      showSymbol: false,
      symbol: 'circle',
      symbolSize: 8,
      data: counts,
      lineStyle: { width: 2, color: BLUE },
      itemStyle: { color: BLUE },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(57,135,229,.30)' },
            { offset: 1, color: 'rgba(57,135,229,.02)' },
          ],
        },
      },
    }],
  } as any)
}

/* ---------- 图4：用户聚类气泡 ---------- */
function renderClusters() {
  const el = clusterRef.value
  if (!el || !clusterHas.value) return
  const chart = ensureChart(el, clusterChart)
  const data = clusterItems.value.map((u, i) => ({
    name: u.username ?? `用户${i + 1}`,
    value: [
      Number(u.query_count) || 0,
      Number(u.avg_latency_ms) || 0,
      Number(u.domain_diversity) || 0,
    ],
    query_count: u.query_count,
    avg_latency_ms: u.avg_latency_ms,
    domain_diversity: u.domain_diversity,
    username: u.username,
  }))
  const maxX = Math.max(...data.map((d) => d.value[0]), 1)
  const maxY = Math.max(...data.map((d) => d.value[1]), 1)
  chart.setOption({
    tooltip: {
      ...TOOLTIP,
      formatter: (p: any) => {
        const d = p.data || {}
        return `<b>${d.username || d.name}</b><br/>提问次数：<b>${fmtNum(d.query_count)}</b><br/>领域多样性：<b>${Number(d.domain_diversity) || 0}</b><br/>平均响应：<b>${fmtNum(d.avg_latency_ms)} ms</b>`
      },
    },
    grid: { left: 10, right: 24, top: 20, bottom: 8, containLabel: true },
    xAxis: {
      name: '提问次数',
      nameTextStyle: { color: '#8c9ab5' },
      type: 'value',
      min: 0,
      max: (v: any) => Math.ceil(v.max * 1.15) || 10,
      axisLine: { lineStyle: { color: 'rgba(140,160,190,.28)' } },
      axisLabel: { color: '#8c9ab5' },
      splitLine: { lineStyle: { color: 'rgba(140,160,190,.1)' } },
    },
    yAxis: {
      name: '平均响应(ms)',
      nameTextStyle: { color: '#8c9ab5' },
      type: 'value',
      min: 0,
      max: (v: any) => Math.ceil(v.max * 1.2) || 100,
      axisLine: { lineStyle: { color: 'rgba(140,160,190,.28)' } },
      axisLabel: { color: '#8c9ab5' },
      splitLine: { lineStyle: { color: 'rgba(140,160,190,.1)' } },
    },
    series: [{
      name: '用户',
      type: 'scatter',
      data,
      symbolSize: (val: any) => Math.max(12, Math.min(60, 10 + (Number(val[2]) || 0) * 26)),
      itemStyle: {
        color: {
          type: 'radial',
          x: 0.4, y: 0.3, r: 1,
          colorStops: [
            { offset: 0, color: 'rgba(201,169,110,.95)' },
            { offset: 0.5, color: 'rgba(201,169,110,.6)' },
            { offset: 1, color: 'rgba(57,135,229,.45)' },
          ],
        },
        shadowBlur: 8,
        shadowColor: 'rgba(201,169,110,.25)',
      },
      label: { show: true, position: 'top', formatter: (p: any) => p.data.username ?? p.name, color: '#c6cfe0', fontSize: 10 },
      emphasis: { scale: 1.4 },
    }],
    // 提示基准区间（供快速解读）
    graphic: [
      {
        type: 'group', left: 12, bottom: 8,
        children: [
          { type: 'text', style: { text: `共 ${data.length} 个活跃用户`, fill: '#8c9ab5', font: '12px sans-serif' } },
          { type: 'text', style: { text: `  ·  区间：提问 0–${fmtNum(maxX)} / 时延 0–${fmtNum(maxY)} ms`, fill: '#5f6f8c', font: '12px sans-serif' } },
        ],
      },
    ],
  } as any)
}

/* ---------- 生命周期 ---------- */
onMounted(() => {
  window.addEventListener('resize', onResize)
  loadTopics(); loadCitations(); loadTrend(); loadClusters()
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  instances.forEach((c) => c.dispose())
  instances = []
})
</script>

<style lang="scss" scoped>
.page { display: flex; flex-direction: column; gap: 16px; }

.filter-bar { padding: 12px 16px; flex-wrap: wrap; gap: 10px; }
.filter-left { display: inline-flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.filter-label { display: inline-flex; align-items: center; gap: 8px; color: var(--text-primary); font-weight: 600; font-size: 14px; }
.days-switch {
  display: inline-flex; gap: 2px; padding: 2px; border: 1px solid var(--border); border-radius: 8px; background: rgba(10,22,40,.4);
}
.days-switch button {
  border: none; background: transparent; color: var(--text-secondary); padding: 4px 12px; border-radius: 6px;
  cursor: pointer; font-size: 12px; transition: all .2s;
}
.days-switch button.active { background: linear-gradient(135deg, var(--primary-light), var(--primary-lighter)); color: #fff; }

.chart-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.chart-card { display: flex; flex-direction: column; }
.section-title { display: flex; align-items: center; gap: 8px; }
.sec { display: inline-flex; align-items: center; gap: 8px; }
.note { font-size: 12px; font-weight: 400; }
.chart-box { flex: 1; position: relative; }
.chart-inner { width: 100%; height: 320px; }
.chart-inner--md { height: 360px; }
.chart-inner--lg { height: 300px; }

@media (max-width: 1280px) {
  .chart-row { grid-template-columns: 1fr; }
}
</style>
