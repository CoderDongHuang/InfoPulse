<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { stage3Api } from '@/api/stage3'

const channels = ref<any[]>([]), active = ref('all'), range = ref('week')
const data = ref<any>({ items: [], source_warnings: [] }), loading = ref(false)
const error = ref(''), page = ref(1), busy = ref<string | null>(null)
let requestId = 0
async function load(reset = false) {
  if (reset) page.value = 1
  const id = ++requestId
  loading.value = true; error.value = ''
  try {
    const result = await stage3Api.discover({ channel: active.value, range: range.value, page: page.value, page_size: 30 })
    if (id === requestId) data.value = result
  } catch { if (id === requestId) error.value = '读取内容失败，请检查服务连接后重试。' }
  finally { if (id === requestId) loading.value = false }
}
async function select(id: string) { active.value = id; await load(true) }
async function act(id: string, type: string) {
  if (busy.value) return
  busy.value = id
  try {
    if (type === 'favorite') { await stage3Api.favorite('content', id); ElMessage.success('已收藏') }
    else { await stage3Api.feedback(id, type); await load(true) }
  } catch { ElMessage.error('操作失败，请稍后重试') }
  finally { busy.value = null }
}
async function turn(delta: number) { page.value += delta; await load() }
onMounted(async () => {
  try { channels.value = await stage3Api.channels() }
  catch { channels.value = [{ id: 'all', name: '全部' }] }
  await load()
})
</script>
<template>
  <main class="stage-page">
    <header class="page-head"><div><p>DISCOVER / REAL SIGNALS</p><h1>发现值得看的内容</h1><span>汇集公开来源，按时效、互动与关注主题排序。</span></div><div class="refresh-actions"><button type="button" :disabled="loading" @click="load(true)">刷新内容</button><select v-model="range" aria-label="时间范围" @change="load(true)"><option value="day">今日</option><option value="week">本周</option><option value="month">本月</option></select></div></header>
    <nav class="channels"><button v-for="c in channels" :key="c.id" :class="{active: active === c.id}" @click="select(c.id)">{{ c.name }}<i v-if="c.followed">已关注</i></button></nav>
    <aside v-if="data.source_warnings.length" class="rule" aria-label="来源提示"><p v-for="warning in data.source_warnings" :key="warning.source_id">{{ warning.source }}：{{ warning.message }}</p><router-link to="/sources">查看数据源状态</router-link></aside>
    <p class="rule">{{ data.ranking_rule }}</p>
    <section v-if="loading" class="empty" role="status">正在读取公开来源内容…</section>
    <section v-else-if="error" class="empty" role="alert"><p>{{ error }}</p><button @click="load()">重试</button></section>
    <section v-else-if="!data.items.length" class="empty"><strong>当前范围没有内容</strong><p>首次采集完成后点击「刷新内容」。也可切换到全部频道或本月；个人反馈可能隐藏内容。数据源中心提供同步结果。</p><router-link to="/sources">查看数据源</router-link></section>
    <div v-else class="discover-list"><article v-for="item in data.items" :key="item.id"><div class="score">{{ Math.round(item.score) }}</div><div><small>{{ item.source.name }} · {{ item.published_at?.slice(0, 10) || '来源未提供发布时间' }}</small><h2>{{ item.title }}</h2><p>{{ item.summary || '原始来源未提供正文摘要' }}</p><div class="reasons"><span v-for="r in item.recommendation_reasons" :key="r.rule">{{ r.label }}</span></div><footer><a :href="item.canonical_url" target="_blank" rel="noopener noreferrer">原文</a><button :disabled="!!busy" @click="act(item.id, 'favorite')">收藏</button><button :disabled="!!busy" @click="act(item.id, 'seen')">已看过</button><button :disabled="!!busy" @click="act(item.id, 'not_interested')">不感兴趣</button></footer></div></article></div>
    <footer v-if="!loading && !error && data.total" class="channels" aria-label="分页"><button :disabled="page === 1" @click="turn(-1)">上一页</button><span>第 {{ page }} 页 · {{ data.total }} 条（最近 500 条候选）</span><button :disabled="!data.has_more" @click="turn(1)">下一页</button></footer>
  </main>
</template>
<style scoped src="@/assets/styles/stage3.css"></style>
<style scoped>
.refresh-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
</style>
