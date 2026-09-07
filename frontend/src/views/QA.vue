<template>
  <div class="qa-page fade-in">
    <!-- 左侧：额度 + 会话管理 -->
    <aside class="qa-side glass-card">
      <div class="quota-box" :class="quotaCls">
        <div class="quota-head">
          <span class="muted">今日问答额度</span>
          <span class="quota-value">{{ quotaText }}</span>
        </div>
        <el-progress
          v-if="!unlimited"
          class="quota-bar"
          :percentage="quotaPercent"
          :show-text="false"
          :stroke-width="6"
          :color="quotaColor"
        />
        <template v-if="!unlimited">
          <div v-if="quota.remaining === 0" class="quota-tip danger">今日额度已用完，请明日再试或联系管理员</div>
          <div v-else-if="quota.remaining >= 0 && quota.remaining <= 5" class="quota-tip warn">剩余次数较少，请注意使用</div>
        </template>
        <template v-else>
          <div class="quota-tip ok">不限次数 · 畅快咨询</div>
        </template>
      </div>

      <el-button type="primary" class="new-btn" :icon="Plus" @click="newConversation">新建对话</el-button>

      <div class="side-label">
        <span class="muted">对话记录</span>
        <el-icon class="refresh-ico" :class="{ spinning: convLoading }" @click="refreshConversationList"><Refresh /></el-icon>
      </div>

      <el-scrollbar class="conv-scroll">
        <div v-if="convLoading" class="conv-loading">
          <el-skeleton :rows="4" animated />
        </div>
        <div v-else-if="!convs.length" class="conv-empty">
          <el-empty description="暂无对话记录" :image-size="60" />
        </div>
        <div v-else>
          <div
            v-for="c in convs"
            :key="c.id"
            class="conv-item"
            :class="{ active: c.id === conversationId }"
            @click="openConversation(c)"
          >
            <!-- 行内重命名 -->
            <div v-if="editingId === c.id" class="conv-edit" @click.stop>
              <el-input
                v-model="editingTitle"
                size="small"
                maxlength="200"
                placeholder="输入新标题"
                @keyup.enter="saveRename(c)"
                @keyup.esc="cancelRename"
              />
              <div class="conv-edit-btns">
                <el-button size="small" type="primary" link :icon="Check" @mousedown.prevent @click.stop="saveRename(c)">保存</el-button>
                <el-button size="small" link @mousedown.prevent @click.stop="cancelRename">取消</el-button>
              </div>
            </div>

            <template v-else>
              <el-icon class="conv-ico"><ChatDotRound /></el-icon>
              <div class="conv-info">
                <div class="conv-title" :title="c.title || '新对话'">{{ c.title || '新对话' }}</div>
                <div class="conv-meta muted">{{ c.message_count || 0 }} 条 · {{ fmtTime(c.updated_at) }}</div>
              </div>
              <div class="conv-ops" @click.stop>
                <el-icon title="重命名" @click="startRename(c)"><Edit /></el-icon>
                <el-icon class="danger" title="删除" @click="removeConversation(c)"><Delete /></el-icon>
              </div>
            </template>
          </div>
        </div>
      </el-scrollbar>
    </aside>

    <!-- 右侧：对话区 -->
    <section class="qa-main glass-card">
      <div v-if="!showWelcome" class="chat-head">
        <div class="chat-head-left">
          <el-icon class="chat-dot"><ChatDotRound /></el-icon>
          <span class="chat-title" :title="convTitle">{{ convTitle || (conversationId ? '对话' : '新对话') }}</span>
        </div>
        <div class="chat-head-right">
          <el-tooltip content="刷新当前对话" placement="bottom">
            <el-button size="small" text :icon="Refresh" :loading="loadingMsgs" @click="refreshCurrent">刷新</el-button>
          </el-tooltip>
          <el-tooltip content="清空并开始新对话" placement="bottom">
            <el-button size="small" text type="primary" :icon="Plus" @click="newConversation">新对话</el-button>
          </el-tooltip>
        </div>
      </div>

      <div class="chat-body">
        <!-- 欢迎态 -->
        <div v-if="showWelcome" class="welcome">
          <div class="w-hero">
            <svg width="72" height="72" viewBox="0 0 24 24" fill="none">
              <path d="M12 2 3 6v6c0 5 3.8 9.4 9 10 5.2-.6 9-5 9-10V6L12 2Z" fill="url(#grad)" opacity=".25" />
              <path d="M12 5.5 5.5 8.5v4.2c0 3.8 2.7 6.9 6.5 7.3 3.8-.4 6.5-3.5 6.5-7.3V8.5L12 5.5Z" fill="url(#grad)" />
              <rect x="8" y="11.2" width="8" height="1.4" rx=".7" fill="#0a1628" />
              <circle cx="9.6" cy="9.6" r="1" fill="#0a1628" />
              <circle cx="14.4" cy="9.6" r="1" fill="#0a1628" />
              <path d="M9.4 13.4h5.2" stroke="#0a1628" stroke-width="1" stroke-linecap="round" />
              <defs>
                <linearGradient id="grad" x1="3" y1="2" x2="21" y2="22">
                  <stop stop-color="#3a7abc" />
                  <stop offset="1" stop-color="#c9a96e" />
                </linearGradient>
              </defs>
            </svg>
            <h1 class="gradient-title">智法通 · 法律问答</h1>
            <p class="w-sub muted">基于现行有效法律法规的智能法律咨询，回答仅供参考，不构成正式法律意见</p>
          </div>

          <div class="sugg" v-if="suggestions.length">
            <div class="sugg-title"><span class="sugg-dot" /> 大家都在问</div>
            <div class="sugg-list">
              <button
                v-for="(s, i) in suggestions"
                :key="i"
                class="sugg-btn"
                :style="{ animationDelay: (i * 60) + 'ms' }"
                @click="askSuggestion(s)"
              >
                {{ s }}
                <el-icon><Promotion /></el-icon>
              </button>
            </div>
          </div>
          <div class="w-foot muted">可输入任意法律问题，如「试用期最长可以约定多久？」</div>
        </div>

        <!-- 空会话态 -->
        <div v-else-if="!msgs.length" class="chat-empty" v-loading="loadingMsgs">
          <el-empty v-if="!loadingMsgs" description="该对话暂无消息，输入下方问题开始咨询吧" :image-size="80" />
        </div>

        <!-- 消息列表 -->
        <el-scrollbar v-else ref="chatScroller" class="msgs-scroll" @scroll="onScroll">
          <div class="msg-list">
            <div v-for="(m, idx) in msgs" :key="m.id || ('local-' + idx)" class="msg-row" :class="m.role">
              <div class="msg-avatar" :class="m.role">
                <span>{{ m.role === 'assistant' ? '法' : '我' }}</span>
              </div>

              <div class="msg-main">
                <div class="msg-name muted">{{ m.role === 'assistant' ? '智法通' : '我' }}</div>

                <div class="bubble" :class="[m.role, { error: m.error }]">
                  <!-- 打字机正文 -->
                  <div v-if="m.role === 'assistant'" class="md" v-html="mdHtml(m.content)"></div>
                  <div v-else class="plain-text">{{ m.content }}</div>

                  <span v-if="m.streaming && m.content" class="cursor"></span>

                  <!-- 生成中的提示 -->
                  <div v-if="m.streaming && !m.content" class="typing-line">
                    <span class="muted">正在检索并生成回答</span>
                    <span class="dots"><i /><i /><i /></span>
                  </div>

                  <!-- 引用来源折叠列表 -->
                  <div v-if="m.role === 'assistant' && !m.streaming && m.citations && m.citations.length" class="cite-block">
                    <div class="cite-head" @click="toggleCite(idx)">
                      <el-icon><Reading /></el-icon>
                      引用来源（{{ m.citations.length }}）
                      <el-icon class="cite-arrow" :class="{ open: openCites[idx] }"><ArrowDown /></el-icon>
                    </div>
                    <div v-if="openCites[idx]" class="cite-list">
                      <div v-for="(c, ci) in m.citations" :key="ci" class="cite-item">
                        <span class="cite-index">{{ ci + 1 }}</span>
                        <span class="cite-name">{{ c.name || '未知法规' }}</span>
                        <span v-if="c.article" class="cite-article">第 {{ c.article }} 条</span>
                      </div>
                    </div>
                  </div>

                  <!-- 置信度 -->
                  <div v-if="m.role === 'assistant' && !m.streaming && typeof m.confidence === 'number'" class="conf-line">
                    <span class="muted">可信度</span>
                    <el-progress
                      class="conf-bar"
                      :percentage="Math.round(m.confidence * 100)"
                      :stroke-width="5"
                      :color="confColor(m.confidence)"
                    />
                    <span class="conf-num" :style="{ color: confColor(m.confidence) }">{{ Math.round(m.confidence * 100) }}%</span>
                  </div>

                  <!-- 出错信息 -->
                  <div v-if="m.error && !m.streaming" class="error-line">
                    <el-icon><WarningFilled /></el-icon>
                    <span>回答生成失败，请稍后重试</span>
                  </div>
                </div>

                <!-- 反馈（assistant 完成态） -->
                <div
                  v-if="m.role === 'assistant' && !m.streaming && m.id"
                  class="msg-actions"
                >
                  <el-tooltip content="有帮助" placement="top">
                    <el-icon
                      :class="{ liked: fbState[m.id] === 'up' }"
                      @click="giveFeedback(m, true)"
                    ><CircleCheck /></el-icon>
                  </el-tooltip>
                  <el-tooltip content="没帮助" placement="top">
                    <el-icon
                      :class="{ disliked: fbState[m.id] === 'down' }"
                      @click="giveFeedback(m, false)"
                    ><CircleClose /></el-icon>
                  </el-tooltip>
                  <span class="fb-tip muted">反馈有助于优化回答质量</span>
                </div>
              </div>
            </div>
          </div>
        </el-scrollbar>
      </div>

      <!-- 输入区 -->
      <div class="input-area">
        <div class="input-box">
          <textarea
            ref="inputRef"
            v-model="input"
            class="qa-ta"
            rows="1"
            maxlength="2000"
            :disabled="quotaBlocked"
            :placeholder="inputPlaceholder"
            @keydown="onKeydown"
            @input="autoGrow"
          ></textarea>
          <div class="input-foot">
            <span class="foot-hint muted">{{ inputHint }}</span>
            <div class="foot-right">
              <span class="count muted" :class="{ over: input.length >= 2000 }">{{ input.length }}/2000</span>
              <el-button
                type="primary"
                class="send-btn"
                :loading="sending"
                :disabled="!input.trim() || sending || quotaBlocked"
                @click="send"
              >
                <el-icon v-if="!sending"><Promotion /></el-icon>
                <span>发送</span>
              </el-button>
            </div>
          </div>
        </div>
        <div v-if="quotaBlocked" class="quota-blocked-bar">今日问答额度已用完，可于明日 0 点后继续使用</div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowDown, ChatDotRound, Check, CircleCheck, CircleClose, Delete, Edit, Plus,
  Promotion, Reading, Refresh, WarningFilled,
} from '@element-plus/icons-vue'
import { qaApi } from '@/api/qa'
import { renderMarkdown } from '@/utils/markdown'

interface Citation {
  name?: string
  article?: string
}

interface ChatMsg {
  id?: number | null
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  confidence?: number | null
  streaming?: boolean
  error?: boolean
}

interface ConvItem {
  id: number
  title: string
  message_count: number
  created_at?: string
  updated_at?: string
}

/* ---------------- 状态 ---------------- */
const msgs = ref<ChatMsg[]>([])
const convs = ref<ConvItem[]>([])
const conversationId = ref<number | null>(null)
const convTitle = ref('')
const input = ref('')
const sending = ref(false)
const convLoading = ref(false)
const loadingMsgs = ref(false)
const suggestions = ref<string[]>([])
const inputRef = ref<HTMLTextAreaElement | null>(null)
const chatScroller = ref<any>(null)
const stickBottom = ref(true)
const openCites = reactive<Record<number, boolean>>({})
const fbState = reactive<Record<number, 'up' | 'down'>>({})

const quota = ref<{ used: number; remaining: number; limit: number }>({ used: 0, remaining: -2, limit: 50 })

/* 重命名 */
const editingId = ref<number | null>(null)
const editingTitle = ref('')

/* ---------------- 计算 ---------------- */
const unlimited = computed(() => quota.value.remaining === -1)
const quotaKnown = computed(() => quota.value.remaining >= 0)

const quotaText = computed(() => {
  if (unlimited.value) return '不限'
  if (!quotaKnown.value) return '…'
  const limit = quota.value.limit > 0 ? quota.value.limit : 50
  return `剩余 ${quota.value.remaining}/${limit}`
})

const quotaPercent = computed(() => {
  if (unlimited.value || !quotaKnown.value) return 100
  const limit = quota.value.limit > 0 ? quota.value.limit : 50
  return Math.max(0, Math.min(100, Math.round((quota.value.remaining / limit) * 100)))
})

const quotaColor = computed(() => {
  if (!quotaKnown.value) return 'var(--primary-lighter)'
  if (quota.value.remaining === 0) return 'var(--danger)'
  if (quota.value.remaining <= 5) return 'var(--warning)'
  return 'var(--accent)'
})

const quotaCls = computed(() => {
  if (!quotaKnown.value || unlimited.value) return ''
  if (quota.value.remaining === 0) return 'is-danger'
  if (quota.value.remaining <= 5) return 'is-warn'
  return 'is-ok'
})

const quotaBlocked = computed(() => !unlimited.value && quota.value.remaining === 0)

const showWelcome = computed(() => conversationId.value === null && !msgs.value.length && !sending.value)

const inputHint = computed(() => {
  if (quotaBlocked.value) return '今日额度已用完'
  if (sending.value) return 'AI 正在生成回答，请稍候…'
  return 'Enter 发送 · Shift + Enter 换行'
})

const inputPlaceholder = computed(() =>
  quotaBlocked.value ? '今日问答额度已用完，请明日再来咨询' : '请输入您的法律问题，例如：公司违法解除劳动合同如何赔偿？'
)

/* ---------------- 生命周期 ---------------- */
onMounted(() => {
  loadQuota()
  loadConversationList()
  loadSuggestions()
})

/* ---------------- 工具 ---------------- */
function mdHtml(text: string): string {
  return renderMarkdown(text || '')
}

function confColor(v: number): string {
  if (v >= 0.8) return 'var(--success)'
  if (v >= 0.6) return 'var(--accent)'
  return 'var(--warning)'
}

function fmtTime(s?: string): string {
  if (!s) return ''
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return String(s).slice(0, 16)
  const now = new Date()
  const sameDay = d.toDateString() === now.toDateString()
  const hh = `${d.getHours()}`.padStart(2, '0')
  const mm = `${d.getMinutes()}`.padStart(2, '0')
  if (sameDay) return `${hh}:${mm}`
  return `${d.getMonth() + 1}-${d.getDate()} ${hh}:${mm}`
}

function scrollToBottom() {
  nextTick(() => {
    const sc = chatScroller.value
    if (sc && sc.wrapRef) sc.setScrollTop(sc.wrapRef.scrollHeight)
  })
}

function onScroll() {
  const sc = chatScroller.value
  if (!sc || !sc.wrapRef) return
  const el = sc.wrapRef as HTMLElement
  stickBottom.value = el.scrollHeight - el.clientHeight - el.scrollTop < 90
}

function toggleCite(idx: number) {
  openCites[idx] = !openCites[idx]
}

function autoGrow() {
  const ta = inputRef.value
  if (!ta) return
  ta.style.height = 'auto'
  ta.style.height = Math.min(ta.scrollHeight, 132) + 'px'
}

function resetInputHeight() {
  nextTick(() => {
    const ta = inputRef.value
    if (ta) ta.style.height = 'auto'
  })
}

function focusInput() {
  nextTick(() => {
    const ta = inputRef.value
    if (ta) ta.focus()
  })
}

/* ---------------- 额度 / 会话 ---------------- */
async function loadQuota() {
  try {
    const res = (await qaApi.quota()) as any
    quota.value = {
      used: Number(res.used ?? 0),
      remaining: Number(res.remaining ?? -2),
      limit: Number(res.limit ?? 50),
    }
  } catch {
    /* 交给拦截器提示 */
  }
}

async function loadConversationList() {
  convLoading.value = true
  try {
    const res = (await qaApi.conversations({ page: 1, page_size: 50 })) as any
    const items = res?.items || (Array.isArray(res) ? res : [])
    convs.value = (items || []).map((it: any) => ({
      id: it.id,
      title: it.title || '',
      message_count: it.message_count ?? 0,
      created_at: it.created_at,
      updated_at: it.updated_at,
    }))
  } catch {
    /* 拦截器已提示 */
  } finally {
    convLoading.value = false
  }
}

async function loadSuggestions() {
  try {
    const res = (await qaApi.suggestions()) as any
    suggestions.value = res?.items || []
  } catch {
    suggestions.value = []
  }
}

function convById(id: number): ConvItem | undefined {
  return convs.value.find((c) => c.id === id)
}

function openConversation(c: ConvItem) {
  if (sending.value) {
    ElMessage.warning('AI 正在生成回答，请稍候再切换')
    return
  }
  if (conversationId.value === c.id && msgs.value.length) return
  editingId.value = null
  conversationId.value = c.id
  convTitle.value = c.title || ''
  msgs.value = []
  stickBottom.value = true
  loadingMsgs.value = true
  qaApi
    .messages(c.id)
    .then((res: any) => {
      const items = res?.items || (Array.isArray(res) ? res : [])
      msgs.value = (items || []).map((it: any): ChatMsg => ({
        id: it.id,
        role: it.role === 'user' ? 'user' : 'assistant',
        content: it.content ?? '',
        citations: Array.isArray(it.citations) ? it.citations : [],
        confidence: typeof it.confidence === 'number' ? it.confidence : null,
        streaming: false,
        error: false,
      }))
      scrollToBottom()
    })
    .catch(() => {})
    .finally(() => {
      loadingMsgs.value = false
    })
}

async function refreshCurrent() {
  if (!conversationId.value) return
  const c = convById(conversationId.value)
  if (c) await openConversation(c)
}

function refreshConversationList() {
  return loadConversationList()
}

function newConversation() {
  if (sending.value) {
    ElMessage.warning('AI 正在生成回答，请稍候')
    return
  }
  editingId.value = null
  conversationId.value = null
  convTitle.value = ''
  msgs.value = []
  stickBottom.value = true
  input.value = ''
  resetInputHeight()
  focusInput()
}

/* 重命名 */
function startRename(c: ConvItem) {
  editingId.value = c.id
  editingTitle.value = c.title || ''
}

async function saveRename(c: ConvItem) {
  const t = editingTitle.value.trim()
  if (!t) {
    ElMessage.warning('标题不能为空')
    return
  }
  editingId.value = null
  try {
    await qaApi.renameConversation(c.id, t)
    c.title = t
    if (conversationId.value === c.id) convTitle.value = t
    ElMessage.success('已重命名')
  } catch {
    /* 拦截器已提示 */
  }
}

function cancelRename() {
  editingId.value = null
}

async function removeConversation(c: ConvItem) {
  try {
    await ElMessageBox.confirm(`确定删除对话「${c.title || '未命名'}」吗？删除后不可恢复。`, '删除对话', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await qaApi.deleteConversation(c.id)
    ElMessage.success('对话已删除')
    if (conversationId.value === c.id) {
      conversationId.value = null
      convTitle.value = ''
      msgs.value = []
    }
    await loadConversationList()
  } catch {
    /* 拦截器已提示 */
  }
}

/* 反馈 */
async function giveFeedback(m: ChatMsg, positive: boolean) {
  if (!m.id || m.streaming) return
  try {
    await qaApi.feedback({ message_id: m.id, is_positive: positive })
    fbState[m.id] = positive ? 'up' : 'down'
    ElMessage.success('感谢您的反馈')
  } catch {
    /* 拦截器已提示 */
  }
}

/* 推荐问题 */
function askSuggestion(s: string) {
  input.value = s
  autoGrow()
  send()
}

/* ---------------- 发送 ---------------- */
function onKeydown(e: KeyboardEvent) {
  if ((e as any).isComposing) return
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

async function send() {
  const text = input.value.trim()
  if (!text) return
  if (sending.value) return
  if (quotaBlocked.value) {
    ElMessage.warning('今日问答额度已用完，请明日再试')
    return
  }

  const cid = conversationId.value

  input.value = ''
  resetInputHeight()

  msgs.value.push({ id: null, role: 'user', content: text })
  const ai: ChatMsg = { id: null, role: 'assistant', content: '', citations: [], confidence: null, streaming: true, error: false }
  msgs.value.push(ai)
  sending.value = true
  stickBottom.value = true
  scrollToBottom()

  let streamEnded = false
  // 后端是否已真正为本轮创建/推进了会话（有 meta/content/done 事件即视为已创建）
  let started = false

  const finishError = (errMsg?: string) => {
    if (streamEnded) return
    streamEnded = true
    ai.streaming = false
    ai.error = true
    if (!ai.content.trim()) ai.content = '抱歉，本次回答生成失败，请稍后重试。'
    if (errMsg) ElMessage.error(errMsg)
  }

  try {
    await qaApi.askStream({ question: text, conversation_id: cid }, (ev) => {
      const d = ev.data || {}
      if (ev.type === 'meta') {
        started = true
        if (d.conversation_id) conversationId.value = d.conversation_id
      } else if (ev.type === 'content') {
        started = true
        const delta = typeof d.delta === 'string' ? d.delta : ''
        if (delta) {
          ai.content += delta
          if (stickBottom.value) scrollToBottom()
        }
      } else if (ev.type === 'done') {
        started = true
        streamEnded = true
        if (d.conversation_id) conversationId.value = d.conversation_id
        ai.streaming = false
        if (Array.isArray(d.citations)) ai.citations = d.citations
        if (typeof d.confidence === 'number') ai.confidence = d.confidence
        if (!ai.content.trim() && typeof d.answer === 'string') ai.content = d.answer
        if (stickBottom.value) scrollToBottom()
      } else if (ev.type === 'error') {
        const msg = String(d.message || '')
        const quotaMsg = msg.includes('额度') || msg.includes('429')
        ai.streaming = false
        ai.error = true
        if (!ai.content.trim()) {
          ai.content = quotaMsg ? '今日问答额度已用完，请明日再试或联系管理员。' : '抱歉，本次回答生成失败，请稍后重试。'
        }
        if (quotaMsg) ElMessage.warning(msg || '今日问答额度已用完')
        else finishError(msg || '回答生成失败')
      }
    })
  } catch {
    finishError('网络连接异常，回答中断，请重试')
  } finally {
    if (ai.streaming) {
      ai.streaming = false
      ai.error = true
      if (!ai.content.trim()) ai.content = '回答生成中断，请重试。'
    }
    sending.value = false
    loadQuota()
    if (!conversationId.value) {
      // 只有后端真正创建/推进过会话才去列表里认领会话 id（额度不足/网络中断前置错误时保持“未选中”）
      if (started) await syncNewConversation(text)
    } else {
      await loadConversationList()
      const cur = convById(conversationId.value)
      if (cur) convTitle.value = cur.title || convTitle.value
    }
    scrollToBottom()
  }
}

async function syncNewConversation(firstQuestion: string) {
  await loadConversationList()
  const first = convs.value[0]
  if (first) {
    conversationId.value = first.id
    convTitle.value = first.title || firstQuestion.slice(0, 20)
  }
}
</script>

<style lang="scss" scoped>
.qa-page {
  height: calc(100vh - var(--header-height) - 36px);
  min-height: 440px;
  display: flex;
  gap: 14px;
  overflow: hidden;
}

/* ============ 左侧栏 ============ */
.qa-side {
  flex: 0 0 300px;
  width: 300px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow: hidden;
  padding: 16px 14px;
}

.quota-box {
  padding: 12px 14px;
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(201, 169, 110, 0.10), rgba(26, 58, 92, 0.15));
  border: 1px solid var(--border);
  &.is-warn { border-color: rgba(230, 162, 60, 0.6); background: rgba(230, 162, 60, 0.12); }
  &.is-danger { border-color: rgba(232, 93, 93, 0.65); background: rgba(232, 93, 93, 0.14); }
}

.quota-head { display: flex; justify-content: space-between; align-items: center; font-size: 13px; margin-bottom: 8px; }
.quota-value { font-weight: 700; color: var(--accent); font-size: 14px; }
.quota-bar { width: 100%; margin-bottom: 6px; }
.quota-tip { font-size: 12px; line-height: 1.5; }
.quota-tip.ok { color: var(--success); }
.quota-tip.warn { color: var(--warning); }
.quota-tip.danger { color: var(--danger); }

.new-btn { width: 100%; margin-bottom: 2px; }

.side-label { display: flex; align-items: center; justify-content: space-between; font-size: 13px; padding: 0 2px; }
.refresh-ico { cursor: pointer; color: var(--text-secondary); font-size: 15px; }
.refresh-ico:hover { color: var(--accent); }
.refresh-ico.spinning { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.conv-scroll { flex: 1; min-height: 0; margin-top: 4px; }
.conv-loading { padding: 8px 4px; }
.conv-empty { padding: 6px 0; }

.conv-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  margin-bottom: 4px;
  border-radius: 10px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: background 0.2s, border-color 0.2s;
  &:hover { background: rgba(255, 255, 255, 0.05); }
  &.active {
    background: rgba(201, 169, 110, 0.12);
    border-color: rgba(201, 169, 110, 0.35);
    .conv-title { color: var(--accent); }
  }
}

.conv-ico { color: var(--text-secondary); flex: none; }
.conv-item.active .conv-ico { color: var(--accent); }

.conv-info { flex: 1; min-width: 0; }
.conv-title { font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.conv-meta { font-size: 11px; margin-top: 2px; }

.conv-ops { display: none; gap: 6px; flex: none; align-items: center; font-size: 15px; }
.conv-item:hover .conv-ops { display: flex; }
.conv-ops .el-icon { cursor: pointer; color: var(--text-secondary); }
.conv-ops .el-icon:hover { color: var(--accent); }
.conv-ops .el-icon.danger:hover { color: var(--danger); }

.conv-edit { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; }
.conv-edit-btns { display: flex; justify-content: flex-end; }

/* ============ 右侧对话区 ============ */
.qa-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-head {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px 18px 10px;
  border-bottom: 1px solid var(--border);
}
.chat-head-left { display: flex; align-items: center; gap: 8px; min-width: 0; }
.chat-dot { color: var(--accent); font-size: 18px; }
.chat-title { font-size: 15px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.chat-head-right { flex: none; display: flex; }

.chat-body { flex: 1; min-height: 0; display: flex; flex-direction: column; }

/* 欢迎态 */
.welcome {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 22px;
  padding: 20px 24px;
  overflow-y: auto;
}
.w-hero { text-align: center; }
.w-hero h1 { font-size: 26px; margin: 12px 0 8px; letter-spacing: 2px; }
.w-sub { font-size: 13px; margin: 0; }

.sugg { width: 100%; max-width: 640px; }
.sugg-title { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-secondary); margin-bottom: 12px; }
.sugg-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 8px var(--accent); }
.sugg-list { display: flex; flex-wrap: wrap; gap: 10px; }
.sugg-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: rgba(18, 35, 60, 0.5);
  color: var(--text-primary);
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
  animation: fadeIn 0.4s ease both;
  .el-icon { font-size: 13px; opacity: 0; transition: opacity 0.2s; }
  &:hover {
    border-color: rgba(201, 169, 110, 0.6);
    background: rgba(201, 169, 110, 0.10);
    transform: translateY(-1px);
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.25);
    .el-icon { opacity: 1; color: var(--accent); }
  }
}
.w-foot { font-size: 12px; }

.chat-empty { flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center; }

/* 消息列表 */
.msgs-scroll { flex: 1; min-height: 0; }
.msg-list { padding: 18px 18px 8px; }
.msg-row { display: flex; gap: 10px; margin-bottom: 18px; }
.msg-row.user { flex-direction: row-reverse; }

.msg-avatar {
  flex: none;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 700;
  color: #0a1628;
  &.assistant {
    background: linear-gradient(135deg, #f0dcb0, var(--accent));
    box-shadow: 0 0 12px rgba(201, 169, 110, 0.35);
  }
  &.user {
    background: linear-gradient(135deg, var(--primary-light), var(--primary-lighter));
    color: #fff;
  }
}

.msg-main { max-width: 76%; display: flex; flex-direction: column; gap: 5px; }
.msg-row.user .msg-main { align-items: flex-end; }
.msg-name { font-size: 12px; }

.bubble {
  padding: 11px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.7;
  word-break: break-word;
  &.assistant {
    background: rgba(18, 35, 60, 0.62);
    border: 1px solid var(--border);
    border-top-left-radius: 4px;
  }
  &.user {
    background: linear-gradient(135deg, var(--primary-light), var(--primary-lighter));
    border-top-right-radius: 4px;
    color: #fff;
  }
  &.error { border-color: rgba(232, 93, 93, 0.6); }
}

.plain-text { white-space: pre-wrap; }

/* markdown / 法条引用金色高亮（v-html 内容经 :deep 命中） */
.md {
  :deep(p) { margin: 0 0 8px; }
  :deep(ul),
  :deep(ol) { margin: 6px 0; padding-left: 20px; }
  :deep(h1),
  :deep(h2),
  :deep(h3) { margin: 10px 0 6px; font-size: 15px; line-height: 1.5; }
  :deep(hr) { border: none; border-top: 1px dashed var(--border); margin: 10px 0; }
  :deep(blockquote) { margin: 6px 0; padding: 4px 12px; border-left: 3px solid var(--accent); color: var(--text-secondary); }
  :deep(code) { background: rgba(255, 255, 255, 0.07); padding: 1px 5px; border-radius: 4px; font-size: 13px; }
  :deep(.law-citation) {
    color: var(--accent);
    font-weight: 600;
    background: rgba(201, 169, 110, 0.10);
    border-bottom: 1px solid rgba(201, 169, 110, 0.55);
    padding: 0 2px;
    border-radius: 3px;
  }
}

.cursor {
  display: inline-block;
  width: 2px;
  height: 15px;
  margin-left: 2px;
  vertical-align: -2px;
  background: var(--accent);
  animation: blink 0.9s steps(1) infinite;
}
@keyframes blink { 50% { opacity: 0; } }

.typing-line { display: flex; align-items: center; gap: 8px; font-size: 13px; height: 20px; }
.dots { display: inline-flex; gap: 4px; }
.dots i {
  width: 5px; height: 5px; border-radius: 50%;
  background: var(--accent);
  animation: dot 1.2s infinite ease-in-out;
  &:nth-child(2) { animation-delay: 0.2s; }
  &:nth-child(3) { animation-delay: 0.4s; }
}
@keyframes dot { 0%, 100% { opacity: 0.25; transform: scale(0.8); } 50% { opacity: 1; transform: scale(1); } }

/* 引用折叠 */
.cite-block {
  margin-top: 10px;
  border-top: 1px dashed var(--border);
  padding-top: 8px;
}
.cite-head {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--accent);
  cursor: pointer;
  user-select: none;
}
.cite-arrow { font-size: 12px; transition: transform 0.2s; &.open { transform: rotate(180deg); } }
.cite-list { margin-top: 8px; display: flex; flex-direction: column; gap: 6px; }
.cite-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-secondary);
  padding: 5px 8px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 6px;
}
.cite-index {
  flex: none;
  width: 18px; height: 18px;
  border-radius: 5px;
  background: rgba(201, 169, 110, 0.18);
  color: var(--accent);
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 11px;
}
.cite-name { color: var(--text-primary); }
.cite-article { color: var(--accent); }

/* 置信度 */
.conf-line { display: flex; align-items: center; gap: 8px; margin-top: 10px; font-size: 12px; }
.conf-bar { flex: 1; min-width: 80px; max-width: 140px; }
.conf-num { font-weight: 700; font-size: 12px; }

.error-line { display: flex; align-items: center; gap: 6px; margin-top: 8px; color: var(--danger); font-size: 13px; }

/* 反馈 */
.msg-actions { display: flex; align-items: center; gap: 12px; padding: 0 4px; font-size: 16px; }
.msg-actions .el-icon { cursor: pointer; color: var(--text-muted); transition: color 0.2s, transform 0.2s; }
.msg-actions .el-icon:hover { color: var(--accent); transform: scale(1.12); }
.msg-actions .el-icon.liked { color: var(--success); }
.msg-actions .el-icon.disliked { color: var(--danger); }
.fb-tip { font-size: 11px; }

/* ============ 输入区 ============ */
.input-area { flex: none; padding: 10px 16px 16px; }
.input-box {
  background: rgba(10, 22, 40, 0.55);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 10px 12px 8px;
  transition: border-color 0.2s;
  &:focus-within { border-color: rgba(201, 169, 110, 0.6); box-shadow: 0 0 0 3px rgba(201, 169, 110, 0.08); }
}
.qa-ta {
  width: 100%;
  border: none;
  outline: none;
  resize: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.7;
  font-family: inherit;
  min-height: 22px;
  max-height: 132px;
  &::placeholder { color: var(--text-muted); }
  &:disabled { cursor: not-allowed; }
}
.input-foot { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 4px; }
.foot-hint { font-size: 12px; }
.foot-right { display: flex; align-items: center; gap: 10px; }
.count { font-size: 12px; &.over { color: var(--danger); } }
.send-btn { margin: 0; }
.quota-blocked-bar {
  margin-top: 8px;
  padding: 8px 12px;
  border-radius: 10px;
  background: rgba(232, 93, 93, 0.12);
  border: 1px solid rgba(232, 93, 93, 0.4);
  color: var(--danger);
  font-size: 12px;
}
</style>
