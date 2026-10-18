<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { stage3Api, type WorkspaceData } from '@/api/stage3'

const router = useRouter()
const loading = ref(false)
const error = ref('')
const actionError = ref('')
const actionNotice = ref('')
const pending = ref<string | null>(null)
const data = ref<WorkspaceData | null>(null)

async function load() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try { data.value = await stage3Api.workspace() }
  catch { error.value = '工作台加载失败，请检查连接后重试。' }
  finally { loading.value = false }
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

onMounted(load)
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
          <div class="section-title"><div><small>DAILY BRIEF</small><h2>今日建议</h2></div><span>{{ data.recommendations.length }} 条</span></div>
          <div v-if="!data.recommendations.length" class="empty"><strong>暂无真实建议</strong><p>建议来自最近一周已采集的内容。首次采集完成后可点击「刷新工作台」；个人反馈也可能隐藏内容。</p><button type="button" @click="router.push('/sources')">查看数据来源</button></div>
          <article v-for="(item, i) in data.recommendations" :key="item.id" class="recommend">
            <b>{{ String(i + 1).padStart(2, '0') }}</b>
            <div><h3>{{ item.title }}</h3><p>{{ item.summary || '原始内容暂无摘要' }}</p>
              <ul><li v-for="reason in item.recommendation_reasons" :key="reason.rule">{{ reason.label }}</li></ul>
              <footer><a :href="item.canonical_url" target="_blank" rel="noopener noreferrer">查看原文 ↗</a><button type="button" :disabled="!!pending" @click="act(item.id, 'favorite')">收藏</button><button type="button" :disabled="!!pending" @click="act(item.id, 'ignore')">不感兴趣</button></footer>
            </div>
          </article>
        </section>
        <aside>
          <section><div class="section-title"><h2>今日关注</h2><router-link to="/watchlist">管理</router-link></div><div v-if="!data.attention.length" class="mini-empty">尚未关注主题</div><button v-for="topic in data.attention" :key="topic.id" class="row" type="button" @click="router.push({ path: '/search', query: { q: topic.name } })"><span>{{ topic.name }}</span><b>{{ topic.count }}</b></button></section>
          <section><div class="section-title"><h2>最近报告</h2><router-link to="/reports">全部</router-link></div><div v-if="!data.recent_reports.length" class="mini-empty">尚未创建报告</div><router-link v-for="report in data.recent_reports" :key="report.id" class="row recent-report" :to="`/reports/${report.id}`"><span>{{ report.title }}</span><small>{{ report.status }}</small></router-link></section>
          <section><div class="section-title"><h2>我的收藏</h2></div><div v-if="!data.favorites.length" class="mini-empty">暂无收藏</div><div v-for="item in data.favorites" :key="`${item.target_type}:${item.target_id}`" class="row"><span>{{ item.target_type }}</span><small>{{ item.target_id.slice(0, 8) }}</small></div></section>
          <section><div class="section-title"><h2>最近浏览</h2></div><div v-if="!data.recent_views.length" class="mini-empty">暂无浏览记录</div><div v-for="item in data.recent_views" :key="`${item.target_type}:${item.target_id}`" class="row"><span>{{ item.title || item.target_type }}</span></div></section>
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
</style>
