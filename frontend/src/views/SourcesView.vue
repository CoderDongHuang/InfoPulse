<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { sourceApi, type DataSource, type SyncRun } from '@/api/sources'
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingState from '@/components/common/LoadingState.vue'

const sources = ref<DataSource[]>([])
const loading = ref(true)
const busy = ref<Record<string, string>>({})
const logSource = ref<DataSource | null>(null)
const runs = ref<SyncRun[]>([])
const logsLoading = ref(false)
const rssOpen = ref(false)
const rssSaving = ref(false)
const rssChecking = ref(false)
const rssCheck = ref('')
const rssForm = reactive({ name: '', feed_url: '', sync_interval_minutes: 60 })
const healthyCount = computed(() => sources.value.filter(item => item.health_status === 'healthy').length)
const errorCount = computed(() => sources.value.filter(item => item.health_status === 'error').length)
const rssCount = computed(() => sources.value.filter(item => item.source_type === 'rss').length)

function dateTime(value: string | null) {
  return value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value)) : '尚未同步'
}
function intervalLabel(minutes: number) {
  if (minutes >= 1440) return `${Math.round(minutes / 1440)} 天`
  if (minutes >= 60) return `${Math.round(minutes / 60)} 小时`
  return `${minutes} 分钟`
}
async function loadSources() {
  loading.value = true
  try { sources.value = await sourceApi.list() } catch { sources.value = [] } finally { loading.value = false }
}
async function testConnection(source: DataSource) {
  busy.value[source.id] = 'test'
  try {
    const result = await sourceApi.test(source.id)
    ElMessage[result.status === 'healthy' ? 'success' : 'error'](result.message)
    await loadSources()
  } finally { delete busy.value[source.id] }
}
async function syncNow(source: DataSource) {
  busy.value[source.id] = 'sync'
  try {
    const run = await sourceApi.sync(source.id)
    if (run.status === 'succeeded') ElMessage.success(`同步完成：新增 ${run.created_count}，更新 ${run.updated_count}，跳过 ${run.skipped_count}`)
    else ElMessage.error(run.error_summary || '同步失败')
    await loadSources()
  } finally { delete busy.value[source.id] }
}
async function toggleSource(source: DataSource) {
  busy.value[source.id] = 'toggle'
  try { Object.assign(source, await sourceApi.update(source.id, { enabled: !source.enabled })) }
  finally { delete busy.value[source.id] }
}
async function openLogs(source: DataSource) {
  logSource.value = source; logsLoading.value = true
  try { runs.value = await sourceApi.runs(source.id) } finally { logsLoading.value = false }
}
async function checkRss() {
  if (!rssForm.feed_url) return
  rssChecking.value = true; rssCheck.value = ''
  try {
    const result = await sourceApi.validateRss(rssForm.feed_url)
    rssCheck.value = result.status === 'healthy' ? `连接成功，读取到 ${result.item_count} 条样本` : result.message
  } finally { rssChecking.value = false }
}
async function addRss() {
  if (!rssForm.name.trim() || !rssForm.feed_url.trim()) return
  rssSaving.value = true
  try {
    await sourceApi.addRss({ ...rssForm, name: rssForm.name.trim(), feed_url: rssForm.feed_url.trim() })
    rssOpen.value = false; Object.assign(rssForm, { name: '', feed_url: '', sync_interval_minutes: 60 }); rssCheck.value = ''
    ElMessage.success('RSS 来源已添加'); await loadSources()
  } finally { rssSaving.value = false }
}
async function removeRss(source: DataSource) {
  if (!window.confirm(`确认删除 RSS 来源“${source.name}”？`)) return
  await sourceApi.remove(source.id); ElMessage.success('RSS 来源已删除'); await loadSources()
}
onMounted(loadSources)
</script>

<template>
  <div class="sources-page">
    <header class="sources-head page-shell">
      <div><p class="eyebrow">DATA OPERATIONS</p><h1>数据源中心</h1><span>管理真实外部数据的连接、同步与健康状态。</span></div>
      <button class="primary" type="button" @click="rssOpen = true"><el-icon><Plus /></el-icon>添加 RSS</button>
    </header>
    <main class="page-shell source-content">
      <section class="metrics" aria-label="数据源状态摘要">
        <div><span>全部来源</span><strong>{{ sources.length }}</strong></div><div><span>连接正常</span><strong class="success">{{ healthyCount }}</strong></div>
        <div><span>连接异常</span><strong class="danger">{{ errorCount }}</strong></div><div><span>自定义 RSS</span><strong>{{ rssCount }}</strong></div>
      </section>
      <section class="source-table">
        <header><div><h2>来源与同步</h2><p>官方 API 与用户添加的公开订阅源</p></div><button type="button" title="刷新列表" @click="loadSources"><el-icon><Refresh /></el-icon></button></header>
        <LoadingState v-if="loading" label="正在读取数据源" />
        <EmptyState v-else-if="!sources.length" title="暂无数据源" description="添加 RSS 或检查后端迁移是否已执行。" />
        <div v-else class="table-scroll"><table><thead><tr><th>来源</th><th>健康状态</th><th>同步周期</th><th>最后成功</th><th>启用</th><th>操作</th></tr></thead><tbody>
          <tr v-for="source in sources" :key="source.id">
            <td><div class="source-name"><span :class="`source-logo ${source.key.split('-')[0]}`">{{ source.name.slice(0, 1) }}</span><div><strong>{{ source.name }}</strong><a :href="source.base_url" target="_blank" rel="noreferrer">{{ source.source_type === 'rss' ? 'RSS' : '官方 API' }}<el-icon><TopRight /></el-icon></a></div></div></td>
            <td><span class="health" :class="source.health_status"><i></i>{{ source.health_status === 'healthy' ? '正常' : source.health_status === 'error' ? '异常' : '待检测' }}</span><small v-if="source.last_error" class="last-error" :title="source.last_error">{{ source.last_error }}</small></td>
            <td>{{ intervalLabel(source.sync_interval_minutes) }}</td><td>{{ dateTime(source.last_success_at) }}</td>
            <td><button class="switch" :class="{ on: source.enabled }" type="button" :disabled="!!busy[source.id]" :aria-label="source.enabled ? '停用来源' : '启用来源'" @click="toggleSource(source)"><i></i></button></td>
            <td><div class="row-actions"><button type="button" :disabled="!!busy[source.id]" @click="testConnection(source)">{{ busy[source.id] === 'test' ? '检测中' : '测试连接' }}</button><button type="button" class="sync" :disabled="!!busy[source.id] || !source.enabled" @click="syncNow(source)">{{ busy[source.id] === 'sync' ? '同步中' : '立即同步' }}</button><button type="button" title="同步记录" @click="openLogs(source)"><el-icon><Clock /></el-icon></button><button v-if="source.source_type === 'rss'" class="delete" type="button" title="删除 RSS" @click="removeRss(source)"><el-icon><Delete /></el-icon></button></div></td>
          </tr>
        </tbody></table></div>
      </section>
    </main>

    <div v-if="logSource" class="overlay" @click.self="logSource = null"><aside class="log-drawer"><header><div><p>SYNC RUNS</p><h2>{{ logSource.name }} 同步记录</h2></div><button type="button" aria-label="关闭" @click="logSource = null">×</button></header><LoadingState v-if="logsLoading" label="正在读取同步记录" /><EmptyState v-else-if="!runs.length" title="暂无同步记录" description="执行一次立即同步后，运行结果会显示在这里。" /><ol v-else><li v-for="run in runs" :key="run.id"><span class="run-status" :class="run.status">{{ run.status === 'succeeded' ? '成功' : run.status === 'failed' ? '失败' : '运行中' }}</span><time>{{ dateTime(run.started_at) }}</time><div><b>抓取 {{ run.fetched_count }}</b><span>新增 {{ run.created_count }}</span><span>更新 {{ run.updated_count }}</span><span>跳过 {{ run.skipped_count }}</span></div><p v-if="run.error_summary">{{ run.error_summary }}</p><small v-if="run.diagnostic_id">诊断 ID：{{ run.diagnostic_id }}</small></li></ol></aside></div>
    <div v-if="rssOpen" class="overlay modal-layer" @click.self="rssOpen = false"><form class="rss-modal" @submit.prevent="addRss"><header><div><p>NEW SOURCE</p><h2>添加 RSS 订阅源</h2></div><button type="button" aria-label="关闭" @click="rssOpen = false">×</button></header><label>来源名称<input v-model="rssForm.name" maxlength="120" placeholder="例如：OpenAI Blog" required /></label><label>Feed 地址<div class="url-row"><input v-model="rssForm.feed_url" type="url" placeholder="https://example.com/feed.xml" required /><button type="button" :disabled="rssChecking || !rssForm.feed_url" @click="checkRss">{{ rssChecking ? '检测中' : '验证' }}</button></div></label><p v-if="rssCheck" class="rss-check">{{ rssCheck }}</p><label>同步周期<select v-model.number="rssForm.sync_interval_minutes"><option :value="30">30 分钟</option><option :value="60">1 小时</option><option :value="360">6 小时</option><option :value="1440">每天</option></select></label><footer><button type="button" @click="rssOpen = false">取消</button><button class="primary" type="submit" :disabled="rssSaving">{{ rssSaving ? '添加中' : '添加来源' }}</button></footer></form></div>
  </div>
</template>

<style scoped>
.sources-page{min-height:calc(100vh - 56px);background:#f3f6f5}.sources-head{padding-top:36px;padding-bottom:24px;display:flex;align-items:end;justify-content:space-between;border-bottom:1px solid #d6dfdc}.sources-head h1{margin:0;font-size:34px}.sources-head span{display:block;margin-top:7px;color:#70817c;font-size:13px}.primary{border-color:#167f76!important;color:#fff!important;background:#167f76!important}.sources-head button{min-height:42px;padding:0 16px;border:0;border-radius:5px;display:flex;align-items:center;gap:7px;cursor:pointer}.source-content{padding-top:18px}.metrics{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid #d5dfdb;border-radius:7px;background:#fff}.metrics div{padding:18px 22px;border-left:1px solid #e0e6e3}.metrics div:first-child{border-left:0}.metrics span{display:block;color:#7a8b85;font-size:11px}.metrics strong{display:block;margin-top:4px;font:650 27px/1.2 Georgia,serif}.metrics .success{color:#16805f}.metrics .danger{color:#ca514b}
.source-table{margin-top:16px;border:1px solid #d5dfdb;border-radius:7px;background:#fff;overflow:hidden}.source-table>header{min-height:76px;padding:0 20px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #dce4e1}.source-table h2{margin:0;font-size:18px}.source-table header p{margin:3px 0 0;color:#85938e;font-size:11px}.source-table>header button{width:34px;height:34px;border:1px solid #d2dcd8;border-radius:4px;background:#fff;cursor:pointer}.table-scroll{overflow-x:auto}table{width:100%;min-width:980px;border-collapse:collapse}th{padding:11px 16px;color:#7e8e88;background:#f7f9f8;font-size:10px;text-align:left}th:last-child{text-align:right}td{padding:14px 16px;border-top:1px solid #e7ecea;color:#435750;font-size:12px}.source-name{display:flex;align-items:center;gap:11px}.source-name strong{display:block;color:#16231f;font-size:13px}.source-name a{margin-top:4px;display:flex;align-items:center;gap:3px;color:#608078;font-size:9px}.source-logo{width:34px;height:34px;border-radius:5px;display:grid;place-items:center;color:#fff;background:#24352f;font-weight:800}.source-logo.github{background:#24292f}.source-logo.devto{background:#3b49df}.source-logo.arxiv{background:#b31b1b}.source-logo.rss{background:#d97821}.health{display:flex;align-items:center;gap:6px;font-size:11px}.health i{width:7px;height:7px;border-radius:50%;background:#9aa8a3}.health.healthy i{background:#1e9c70}.health.error i{background:#dc5e57}.last-error{display:block;max-width:180px;margin-top:4px;overflow:hidden;color:#b2504a;white-space:nowrap;text-overflow:ellipsis}.switch{width:34px;height:19px;padding:2px;border:0;border-radius:10px;background:#c6cfcc;cursor:pointer}.switch i{display:block;width:15px;height:15px;border-radius:50%;background:#fff;transition:transform 160ms ease}.switch.on{background:#218d82}.switch.on i{transform:translateX(15px)}.row-actions{display:flex;justify-content:flex-end;gap:6px}.row-actions button{min-height:30px;padding:0 9px;border:1px solid #d2dcd8;border-radius:4px;color:#486159;background:#fff;cursor:pointer}.row-actions .sync{border-color:#278f84;color:#14766d}.row-actions .delete{padding:0 7px;color:#c94e48}.row-actions button:disabled{opacity:.5;cursor:wait}
.overlay{position:fixed;inset:0;z-index:500;display:flex;justify-content:flex-end;background:rgba(12,25,21,.36);backdrop-filter:blur(2px)}.log-drawer{width:min(520px,92vw);height:100%;padding:24px;overflow-y:auto;background:#fff;box-shadow:-20px 0 50px rgba(15,35,28,.18)}.log-drawer header,.rss-modal header{display:flex;justify-content:space-between;align-items:start;border-bottom:1px solid #dce4e1;padding-bottom:18px}.log-drawer header p,.rss-modal header p{margin:0;color:#168079;font:700 9px/1 monospace}.log-drawer h2,.rss-modal h2{margin:6px 0 0;font-size:21px}.log-drawer header button,.rss-modal header button{border:0;background:transparent;font-size:25px;cursor:pointer}.log-drawer ol{margin:20px 0 0;padding:0;list-style:none}.log-drawer li{padding:16px 0;border-bottom:1px solid #e4eae7}.log-drawer time{margin-left:10px;color:#81908b;font-size:10px}.run-status{padding:3px 6px;border-radius:3px;color:#966012;background:#fff4d8;font-size:9px}.run-status.succeeded{color:#147254;background:#e4f7ef}.run-status.failed{color:#ac413c;background:#fdecea}.log-drawer li div{margin-top:12px;display:flex;flex-wrap:wrap;gap:12px;font-size:11px}.log-drawer li p{color:#b34c46;font-size:11px}.log-drawer li small{color:#86958f;font-family:monospace}
.modal-layer{align-items:center;justify-content:center}.rss-modal{width:min(520px,calc(100vw - 28px));padding:24px;border-radius:7px;background:#fff;box-shadow:0 24px 70px rgba(10,30,23,.25)}.rss-modal label{margin-top:18px;display:grid;gap:7px;color:#42554f;font-size:11px;font-weight:700}.rss-modal input,.rss-modal select{width:100%;height:42px;padding:0 11px;border:1px solid #ccd7d3;border-radius:4px;background:#fff}.url-row{display:grid;grid-template-columns:1fr auto;gap:7px}.url-row button{padding:0 12px;border:1px solid #248d82;border-radius:4px;color:#16766d;background:#eef8f6;cursor:pointer}.rss-check{margin:8px 0 0;color:#24796f;font-size:11px}.rss-modal footer{margin-top:24px;padding-top:16px;border-top:1px solid #e0e6e3;display:flex;justify-content:flex-end;gap:8px}.rss-modal footer button{min-height:38px;padding:0 15px;border:1px solid #ccd7d3;border-radius:4px;background:#fff;cursor:pointer}@media(max-width:760px){.sources-head{align-items:flex-start;flex-direction:column;gap:18px}.metrics{grid-template-columns:1fr 1fr}.metrics div:nth-child(3){border-top:1px solid #e0e6e3;border-left:0}.metrics div:nth-child(4){border-top:1px solid #e0e6e3}.source-content{width:100%}.source-table{border-left:0;border-right:0;border-radius:0}}
</style>
