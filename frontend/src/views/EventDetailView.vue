<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { intelligenceApi, type IntelligenceEvent } from "@/api/intelligence";
import { stage3Api } from "@/api/stage3";
import LoadingState from "@/components/common/LoadingState.vue";
const route = useRoute(),
  router = useRouter(),
  id = String(route.params.id),
  event = ref<IntelligenceEvent | null>(null),
  loading = ref(true),
  tab = ref("overview"),
  timeline = ref<any[]>([]),
  sources = ref<any[]>([]),
  audits = ref<any[]>([]),
  editOpen = ref(false);
const edit = reactive({
  title: "",
  category: "",
  status: "detected",
  risk_notes: "",
});
async function load() {
  loading.value = true;
  try {
    event.value = await intelligenceApi.event(id);
    void stage3Api.recordView("event", id, event.value.title);
    Object.assign(edit, {
      title: event.value.title,
      category: event.value.category,
      status: event.value.status,
      risk_notes: event.value.risk_notes || "",
    });
    const [t, s, a] = await Promise.all([
      intelligenceApi.timeline(id),
      intelligenceApi.eventSources(id),
      intelligenceApi.audits(id),
    ]);
    timeline.value = t.items;
    sources.value = s.items;
    audits.value = a;
  } finally {
    loading.value = false;
  }
}
async function save() {
  event.value = await intelligenceApi.updateEvent(id, { ...edit });
  editOpen.value = false;
  ElMessage.success("事件已更新并写入审计日志");
  await load();
}
function date(value: string | null) {
  return value
    ? new Intl.DateTimeFormat("zh-CN", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(value))
    : "未知";
}
onMounted(load);
</script>
<template>
  <div class="detail-page">
    <LoadingState v-if="loading" label="正在读取事件档案" /><template
      v-else-if="event"
      ><header class="event-head page-shell">
        <button class="back" @click="router.push('/events')">
          <el-icon><ArrowLeft /></el-icon>事件中心
        </button>
        <div class="title-row">
          <div>
            <p>
              <span>{{ event.status }}</span
              >{{ event.category }} · 更新于 {{ date(event.updated_at) }}
            </p>
            <h1>{{ event.title }}</h1>
          </div>
          <div class="event-actions">
            <button class="edit" @click="router.push({ path: '/analysis', query: { event_id: id } })">
              <el-icon><MagicStick /></el-icon>AI 分析
            </button>
            <button class="edit" @click="router.push({ path: '/agent', query: { event_id: id } })">
              <el-icon><ChatDotRound /></el-icon>询问 Agent
            </button>
            <button class="edit" @click="router.push({ path: '/reports', query: { event_id: id } })">
              <el-icon><Document /></el-icon>创建报告
            </button>
            <button class="edit" @click="editOpen = true">
              <el-icon><EditPen /></el-icon>编辑事件
            </button>
          </div>
        </div>
        <div class="metric-row">
          <div>
            <span>热度</span><strong>{{ Math.round(event.heat_score) }}</strong>
          </div>
          <div>
            <span>风险</span><strong>{{ Math.round(event.risk_score) }}</strong>
          </div>
          <div>
            <span>可信度</span
            ><strong>{{ Math.round(event.confidence) }}%</strong>
          </div>
          <div>
            <span>真实来源</span><strong>{{ event.source_count }}</strong>
          </div>
          <div>
            <span>内容数量</span><strong>{{ event.content_count }}</strong>
          </div>
        </div>
      </header>
      <main class="page-shell">
        <nav class="tabs">
          <button
            :class="{ active: tab === 'overview' }"
            @click="tab = 'overview'"
          >
            概览</button
          ><button
            :class="{ active: tab === 'timeline' }"
            @click="tab = 'timeline'"
          >
            时间线</button
          ><button
            :class="{ active: tab === 'sources' }"
            @click="tab = 'sources'"
          >
            来源</button
          ><button :class="{ active: tab === 'audit' }" @click="tab = 'audit'">
            审计记录
          </button>
        </nav>
        <section v-if="tab === 'overview'" class="overview">
          <article>
            <p class="eyebrow">EVENT SUMMARY</p>
            <h2>事件摘要</h2>
            <p>{{ event.summary || "暂无摘要。" }}</p>
            <h3>风险备注</h3>
            <p>{{ event.risk_notes || "尚未添加人工风险备注。" }}</p>
          </article>
          <aside>
            <h2>相关实体</h2>
            <div class="entities">
              <span v-for="entity in event.entities" :key="entity.name"
                >{{ entity.name }} <b>{{ entity.mention_count }}</b></span
              >
            </div>
            <dl>
              <div>
                <dt>开始时间</dt>
                <dd>{{ date(event.started_at) }}</dd>
              </div>
              <div>
                <dt>最后活动</dt>
                <dd>{{ date(event.last_activity_at) }}</dd>
              </div>
              <div>
                <dt>人工保护</dt>
                <dd>{{ event.manual_locked ? "已锁定" : "自动事件" }}</dd>
              </div>
            </dl>
          </aside>
        </section>
        <section v-if="tab === 'timeline'" class="timeline">
          <article v-for="item in timeline" :key="item.content_id">
            <time>{{ date(item.time) }}</time
            ><i></i>
            <div>
              <span>{{ item.source }}<b v-if="item.is_primary">主来源</b></span>
              <h3>{{ item.title }}</h3>
              <p>{{ item.summary }}</p>
              <a :href="item.url" target="_blank">查看原文</a>
            </div>
          </article>
        </section>
        <section v-if="tab === 'sources'" class="source-list">
          <article v-for="item in sources" :key="item.id">
            <span>{{ item.source }}</span>
            <div>
              <h3>{{ item.title }}</h3>
              <time
                >{{ date(item.published_at) }} · 相关度
                {{ Math.round(item.relevance * 100) }}%</time
              >
            </div>
            <a :href="item.url" target="_blank"
              ><el-icon><TopRight /></el-icon
            ></a>
          </article>
        </section>
        <section v-if="tab === 'audit'" class="audit-list">
          <article v-for="item in audits" :key="item.id">
            <span>{{ item.action }}</span
            ><time>{{ date(item.created_at) }}</time>
            <p>操作者 {{ item.user_id }}</p>
            <details>
              <summary>查看变更字段</summary>
              <pre>{{
                JSON.stringify(
                  { before: item.before, after: item.after },
                  null,
                  2,
                )
              }}</pre>
            </details>
          </article>
        </section>
      </main></template
    >
    <div v-if="editOpen" class="overlay" @click.self="editOpen = false">
      <form class="modal" @submit.prevent="save">
        <h2>编辑事件</h2>
        <label>标题<input v-model="edit.title" required /></label
        ><label>分类<input v-model="edit.category" required /></label
        ><label
          >状态<select v-model="edit.status">
            <option value="detected">已发现</option>
            <option value="rising">升温</option>
            <option value="responded">已回应</option>
            <option value="closed">已结束</option>
          </select></label
        ><label
          >风险备注<textarea v-model="edit.risk_notes" rows="5"></textarea>
        </label>
        <footer>
          <button type="button" @click="editOpen = false">取消</button
          ><button class="primary">保存修改</button>
        </footer>
      </form>
    </div>
  </div>
</template>
<style scoped>
.detail-page {
  min-height: 100vh;
  background: #f3f6f5;
}
.event-head {
  padding-top: 28px;
  padding-bottom: 0;
  border-bottom: 1px solid #d4ded9;
  background: #fff;
}
.back {
  padding: 0;
  border: 0;
  display: flex;
  gap: 6px;
  color: #5e756d;
  background: transparent;
}
.title-row {
  margin-top: 25px;
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: start;
}
.title-row p {
  margin: 0;
  color: #71847d;
  font-size: 10px;
}
.title-row p span {
  margin-right: 8px;
  padding: 3px 6px;
  color: #16776e;
  background: #e5f3f0;
}
.title-row h1 {
  max-width: 900px;
  margin: 10px 0 25px;
  font-size: 34px;
  line-height: 1.25;
}
.edit {
  height: 40px;
  padding: 0 14px;
  border: 1px solid #cbd6d2;
  border-radius: 4px;
  background: white;
}
.event-actions { display: flex; gap: 8px; }
.metric-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  border-top: 1px solid #dce4e1;
}
.metric-row div {
  padding: 16px 20px;
  border-left: 1px solid #e0e6e3;
}
.metric-row div:first-child {
  border-left: 0;
}
.metric-row span {
  display: block;
  color: #7b8c86;
  font-size: 9px;
}
.metric-row strong {
  font:
    650 24px Georgia,
    serif;
}
.tabs {
  height: 50px;
  display: flex;
  gap: 4px;
  border-bottom: 1px solid #d5dedb;
}
.tabs button {
  padding: 0 15px;
  border: 0;
  border-bottom: 2px solid transparent;
  color: #667a73;
  background: transparent;
}
.tabs button.active {
  border-color: #167f76;
  color: #126e66;
  font-weight: 750;
}
.overview {
  display: grid;
  grid-template-columns: 1.5fr 0.7fr;
  gap: 14px;
}
.overview article,
.overview aside {
  padding: 24px;
  border: 1px solid #d5dfdb;
  border-radius: 7px;
  background: #fff;
}
.overview h2 {
  margin: 0 0 15px;
}
.overview article > p {
  color: #586d66;
  line-height: 1.8;
}
.overview h3 {
  margin-top: 30px;
}
.entities {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}
.entities span {
  padding: 6px 8px;
  border: 1px solid #d3ded9;
  border-radius: 4px;
  color: #426158;
  font-size: 10px;
}
.entities b {
  margin-left: 5px;
  color: #168078;
}
.overview dl {
  margin-top: 22px;
}
.overview dl div {
  padding: 10px 0;
  border-top: 1px solid #e1e7e4;
  display: flex;
  justify-content: space-between;
  font-size: 11px;
}
.overview dd {
  margin: 0;
}
.timeline {
  max-width: 900px;
  padding: 12px 0;
}
.timeline article {
  display: grid;
  grid-template-columns: 130px 12px 1fr;
  gap: 14px;
}
.timeline time {
  padding-top: 4px;
  color: #758781;
  font-size: 10px;
  text-align: right;
}
.timeline i {
  position: relative;
  width: 8px;
  height: 8px;
  margin-top: 5px;
  border-radius: 50%;
  background: #168078;
}
.timeline i:after {
  content: "";
  position: absolute;
  left: 3px;
  top: 12px;
  width: 1px;
  height: calc(100% + 100px);
  background: #cad7d2;
}
.timeline article > div {
  margin-bottom: 14px;
  padding: 16px;
  border: 1px solid #d6e0dc;
  border-radius: 6px;
  background: white;
}
.timeline span {
  color: #17776e;
  font-size: 9px;
}
.timeline span b {
  margin-left: 8px;
}
.timeline h3 {
  margin: 7px 0;
}
.timeline p {
  color: #647870;
  font-size: 11px;
}
.timeline a {
  color: #16776e;
  font-size: 10px;
}
.source-list,
.audit-list {
  display: grid;
  gap: 8px;
}
.source-list article {
  padding: 16px;
  display: grid;
  grid-template-columns: 110px 1fr 30px;
  align-items: center;
  border: 1px solid #d5dfdb;
  border-radius: 6px;
  background: white;
}
.source-list > article > span {
  color: #16776e;
  font-size: 10px;
}
.source-list h3 {
  margin: 0 0 5px;
}
.source-list time {
  color: #7d8d87;
  font-size: 9px;
}
.audit-list article {
  padding: 18px;
  border: 1px solid #d5dfdb;
  border-radius: 6px;
  background: white;
}
.audit-list article > span {
  color: #16776e;
  font-weight: 750;
}
.audit-list time {
  margin-left: 12px;
  color: #7f8f89;
  font-size: 9px;
}
.audit-list p {
  font-size: 10px;
}
.audit-list pre {
  max-height: 300px;
  overflow: auto;
  padding: 12px;
  background: #f2f5f4;
  font-size: 9px;
}
.overlay {
  position: fixed;
  inset: 0;
  z-index: 500;
  display: grid;
  place-items: center;
  background: rgba(10, 25, 20, 0.4);
}
.modal {
  width: min(520px, calc(100vw - 28px));
  padding: 24px;
  border-radius: 7px;
  background: white;
}
.modal h2 {
  margin-top: 0;
}
.modal label {
  margin-top: 13px;
  display: grid;
  gap: 6px;
  font-size: 11px;
}
.modal input,
.modal select,
.modal textarea {
  padding: 9px;
  border: 1px solid #cad6d1;
  border-radius: 4px;
}
.modal footer {
  margin-top: 22px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.modal footer button {
  height: 38px;
  padding: 0 14px;
  border: 1px solid #cad6d1;
  border-radius: 4px;
  background: white;
}
.modal footer .primary {
  border-color: #167f76;
  color: white;
  background: #167f76;
}
@media (max-width: 760px) {
  .title-row {
    flex-direction: column;
  }
  .metric-row {
    grid-template-columns: repeat(2, 1fr);
  }
  .metric-row div {
    border-top: 1px solid #e0e6e3;
  }
  .overview {
    grid-template-columns: 1fr;
  }
  .timeline article {
    grid-template-columns: 82px 10px 1fr;
  }
  .source-list article {
    grid-template-columns: 1fr 30px;
  }
  .source-list > article > span {
    grid-column: 1/-1;
  }
}
</style>
