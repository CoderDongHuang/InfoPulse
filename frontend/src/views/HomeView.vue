<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import { stage3Api, type WorkspaceData } from '@/api/stage3'
import { useWatchlistStore } from '@/stores/watchlist'
import { recordRecentView, RECENT_VIEW_RECORDED } from '@/utils/recentViews'

const router = useRouter()
const watchlist = useWatchlistStore()
const loading = ref(false)
const error = ref('')
const actionError = ref('')
const actionNotice = ref('')
const pending = ref<string | null>(null)
const data = ref<WorkspaceData | null>(null)
const reloadRequested = ref(false)

async function load() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try { data.value = await stage3Api.workspace() }
  catch { error.value = '工作台加载失败，请检查连接后重试。' }
  finally {
    loading.value = false
    if (reloadRequested.value) { reloadRequested.value = false; await load() }
  }
}

async function act(id: string, action: 'favorite' | 'ignore') {
  if (pending.value) return
  pending.value = id
  actionError.value = ''
  actionNotice.value = ''
  try {
    if (action === 'favorite') await stage3Api.favorite('content', id)
    else await stage3Api.feedback(id, 'not_interested')
    actionNotice.value = action === 'favorite' ? '已收藏' : '已记录反馈'
    await load()
  } catch { actionError.value = '操作失败，未确认保存，请重试。' }
  finally { pending.value = null }
}

function refreshVisible() {
  if (document.visibilityState !== 'visible') return
  if (loading.value) reloadRequested.value = true
  else void load()
}
function statusLabel(status: string) { return ({ draft: '草稿', published: '已发布', completed: '已完成', archived: '已归档' } as Record<string, string>)[status] || status }
onMounted(() => {
  void load()
  window.addEventListener('focus', refreshVisible)
  window.addEventListener(RECENT_VIEW_RECORDED, refreshVisible)
  document.addEventListener('visibilitychange', refreshVisible)
})
onBeforeUnmount(() => {
  window.removeEventListener('focus', refreshVisible)
  window.removeEventListener(RECENT_VIEW_RECORDED, refreshVisible)
  document.removeEventListener('visibilitychange', refreshVisible)
})
</script>

<template>
  <div class="stage-page workspace-page">
    <header class="page-head">
      <div><p>个人工作台 / {{ data?.date || 'TODAY' }}</p><h1>今天，从重要信号开始</h1><span>连接你的关注、研究与行动。只展示有来源的真实数据。</span></div>
      <div class="refresh-actions"><button type="button" :disabled="loading" @click="load">刷新工作台</button><button type="button" @click="router.push('/discover')">发现新情报 →</button></div>
    </header>
    <section v-if="loading" class="empty" role="status">正在读取真实情报数据…</section>
    <section v-else-if="error" class="empty" role="alert"><p>{{ error }}</p><button type="button" @click="load">重试加载</button></section>
    <template v-else-if="data">
      <section v-if="data.source_warnings.length" class="warning"><strong>数据覆盖提醒</strong><span>{{ data.source_warnings[0]?.message }}</span><button type="button" @click="router.push('/sources')">管理数据源</button></section>
      <p v-if="actionError" role="alert">{{ actionError }}</p>
      <p v-if="actionNotice" role="status">{{ actionNotice }}</p>
      <div class="workspace-grid">
        <section class="main-column">
          <div class="section-title"><div><small>FOLLOWING</small><h2>我的关注动态</h2></div><router-link to="/watchlist">管理关注</router-link></div>
          <p v-if="watchlist.legacy.length" class="mini-empty">有旧版浏览器关注尚未同步。<router-link to="/watchlist">前往确认并导入</router-link></p>
          <div v-if="!data.followed_items.length" class="mini-empty">{{ data.attention.length || data.followed_channels.length ? '暂未找到匹配的已采集文章，可检索其他关键词或等待来源更新。' : '关注主题或频道后，相关文章会集中出现在这里。' }}</div>
          <p v-if="data.attention.length || data.followed_channels.length" class="following-hint">从最近采集的 500 条内容匹配，显示最新 12 条；主题计数按文章去重。</p>
          <article v-for="item in data.followed_items" :key="item.id" class="followed-card"><h3><a :href="item.canonical_url" target="_blank" rel="noopener noreferrer" @click="recordRecentView('content', item.id)">{{ item.title }}</a></h3><p>{{ item.summary || '原始内容暂无摘要' }}</p><small v-for="reason in item.recommendation_reasons" :key="reason.rule + reason.label">{{ reason.label }}</small></article>
          <div class="section-title"><div><small>DAILY BRIEF</small><h2>今日建议</h2></div><span>{{ data.recommendations.length }} 条</span></div>
          <div v-if="!data.recommendations.length" class="empty"><strong>暂无真实建议</strong><p>建议来自最近一周已采集的内容。首次采集完成后可点击「刷新工作台」；个人反馈也可能隐藏内容。</p><button type="button" @click="router.push('/sources')">查看数据来源</button></div>
          <article v-for="(item, i) in data.recommendations" :key="item.id" class="recommend">
            <b>{{ String(i + 1).padStart(2, '0') }}</b>
            <div><h3>{{ item.title }}</h3><p>{{ item.summary || '原始内容暂无摘要' }}</p>
              <ul><li v-for="reason in item.recommendation_reasons" :key="reason.rule">{{ reason.label }}</li></ul>
              <footer><a :href="item.canonical_url" target="_blank" rel="noopener noreferrer" @click="recordRecentView('content', item.id)">查看原文 ↗</a><button type="button" :disabled="!!pending" @click="act(item.id, 'favorite')">收藏</button><button type="button" :disabled="!!pending" @click="act(item.id, 'ignore')">不感兴趣</button></footer>
            </div>
          </article>
        </section>
        <aside>
          <section><div class="section-title"><h2>今日关注</h2><router-link to="/watchlist">管理</router-link></div><div v-if="!data.attention.length" class="mini-empty">尚未关注主题</div><button v-for="topic in data.attention" :key="topic.id" class="row" type="button" @click="router.push({ path: '/search', query: { q: topic.name } })"><span>{{ topic.name }}</span><b>{{ topic.count }}</b></button></section>
          <section v-if="data.followed_channels.length"><div class="section-title"><h2>关注频道</h2></div><router-link v-for="channel in data.followed_channels" :key="channel.id" class="row" :to="{ path: '/discover', query: { channel: channel.id } }">{{ channel.name }}</router-link></section>
          <section><div class="section-title"><h2>最近报告</h2><div><router-link to="/reports">报告中心</router-link> · <router-link to="/history">内容档案</router-link></div></div><div v-if="!data.recent_reports.length" class="mini-empty">尚未创建报告或完成内容分析</div><router-link v-for="report in data.recent_reports" :key="`${report.kind}:${report.id}`" class="row recent-report" :to="report.path"><span>{{ report.title }}</span><small>{{ statusLabel(report.status) }}</small></router-link></section>
          <section><div class="section-title"><h2>我的收藏</h2><small>最近 8 条</small></div><div v-if="!data.favorites.length" class="mini-empty">暂无收藏</div><article v-for="item in data.favorites" :key="`${item.target_type}:${item.target_id}`" class="saved-item"><a v-if="item.available && item.canonical_url" :href="item.canonical_url" target="_blank" rel="noopener noreferrer" @click="recordRecentView('content', item.target_id)">{{ item.title }}</a><router-link v-else-if="item.available && item.path" :to="item.path">{{ item.title }}</router-link><strong v-else>{{ item.title }}</strong><small>{{ item.source_name }}</small><p v-if="item.summary">{{ item.summary }}</p></article></section>
          <section><div class="section-title"><h2>最近浏览</h2><small>最近 8 条</small></div><div v-if="!data.recent_views.length" class="mini-empty">暂无浏览记录，打开文章、事件或报告后会自动记录。</div><article v-for="item in data.recent_views" :key="`${item.target_type}:${item.target_id}`" class="saved-item"><a v-if="item.available && item.canonical_url" :href="item.canonical_url" target="_blank" rel="noopener noreferrer" @click="recordRecentView('content', item.target_id)">{{ item.title }}</a><router-link v-else-if="item.available && item.path" :to="item.path">{{ item.title }}</router-link><span v-else>{{ item.title }}</span><small>{{ item.source_name }} · {{ new Date(item.viewed_at).toLocaleString('zh-CN') }}</small></article></section>
        </aside>
      </div>
    </template>
  </div>
</template>
<style scoped src="@/assets/styles/stage3.css"></style>
<style scoped>
.row { gap: 12px; overflow-wrap: anywhere; }
.refresh-actions { display: flex; gap: 10px; flex-wrap: wrap; }
.section-title a { color: var(--color-primary); font-size: 12px; }
button:disabled { opacity: .55; cursor: wait; }
.saved-item{padding:14px 0;border-bottom:1px solid var(--border-color,#e2e8f0);overflow-wrap:anywhere}.saved-item>a,.saved-item>strong{display:block;font-size:14px;line-height:1.6;font-weight:600;color:var(--text-primary)}.saved-item>small{display:block;color:var(--text-secondary);margin:5px 0}.saved-item>p{font-size:12px;line-height:1.7;color:var(--text-secondary);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.followed-card{padding:18px 0;border-bottom:1px solid #e2e8f0}.followed-card h3{margin:0 0 8px;font-size:16px}.followed-card a{color:var(--text-primary)}.followed-card p,.following-hint{font-size:12px;line-height:1.8;color:var(--text-secondary)}.followed-card small{display:inline-block;margin-right:12px;color:var(--color-primary)}
</style>
