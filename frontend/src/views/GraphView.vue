<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { graphApi } from "@/api/graph";
const route = useRoute(),
  router = useRouter(),
  id = String(route.params.id),
  event = ref<any>(),
  graph = ref<any>({ nodes: [], edges: [] }),
  prop = ref<any>({ nodes: [], edges: [], status: "loading" }),
  quality = ref<any>(),
  similar = ref<any[]>([]),
  audits = ref<any[]>([]),
  tab = ref("network"),
  selected = ref<any>(),
  busy = ref(false);
const tabs = [
  ["network", "实体网络"],
  ["timeline", "传播时间线"],
  ["sankey", "Sankey"],
  ["table", "表格视图"],
  ["quality", "质量与审计"],
];
const entityTypes: any = {
  person: "人物",
  company: "企业",
  organization: "组织",
  product: "产品",
  project: "项目",
  location: "地点",
  industry: "行业",
  policy: "政策",
  event: "事件",
};
const positions = computed(() =>
  graph.value.nodes.map((n: any, i: number) => {
    const angle = (i / Math.max(graph.value.nodes.length, 1)) * Math.PI * 2;
    const radius = graph.value.nodes.length > 12 ? (i % 2 ? 150 : 105) : 125;
    return {
      ...n,
      x: 230 + Math.cos(angle) * radius,
      y: 190 + Math.sin(angle) * radius,
    };
  }),
);
const pos = computed(() =>
  Object.fromEntries(positions.value.map((n: any) => [n.id, n])),
);
const pnodes = computed(() =>
  Object.fromEntries(prop.value.nodes.map((n: any) => [n.id, n])),
);
const platformGroups = computed(() => {
  const map: any = {};
  for (const n of prop.value.nodes) (map[n.platform] ??= []).push(n);
  return Object.entries(map);
});
async function load() {
  busy.value = true;
  try {
    event.value = await graphApi.event(id);
    graph.value = await graphApi.graph(id);
    prop.value = await graphApi.propagation(id);
    similar.value = (await graphApi.similar(id)).items;
    quality.value = await graphApi.quality(id);
    audits.value = await graphApi.audits(id);
  } finally {
    busy.value = false;
  }
}
async function rebuild() {
  busy.value = true;
  try {
    graph.value = await graphApi.buildGraph(id);
    prop.value = await graphApi.buildPropagation(id);
    quality.value = await graphApi.quality(id);
    audits.value = await graphApi.audits(id);
    ElMessage.success(
      prop.value.status === "ready"
        ? "图谱与传播路径已更新"
        : "图谱已更新，传播证据不足，未生成路径",
    );
  } finally {
    busy.value = false;
  }
}
async function addEntity() {
  const name = await ElMessageBox.prompt("实体名称", "人工添加实体", {
    inputPattern: /\S+/,
    inputErrorMessage: "请输入名称",
  });
  const kind = await ElMessageBox.prompt(
    "类型：person/company/organization/product/project/location/industry/policy/event",
    "实体类型",
    { inputValue: "organization" },
  );
  const aliases = await ElMessageBox.prompt("可选，多个别名使用逗号分隔", "实体别名", { inputValue: "" });
  await graphApi.addEntity(id, {
    name: name.value,
    entity_type: kind.value,
    aliases: aliases.value.split(/[,，]/).map((x) => x.trim()).filter(Boolean),
    role: "mentioned",
    evidence_content_ids: [],
  });
  await load();
}
async function merge() {
  if (graph.value.nodes.length < 2) return;
  const source = await ElMessageBox.prompt("输入待合并实体名称", "合并实体");
  const target = await ElMessageBox.prompt("输入保留实体名称", "合并实体");
  const a = graph.value.nodes.find((x: any) => x.name === source.value),
    b = graph.value.nodes.find((x: any) => x.name === target.value);
  if (!a || !b) {
    ElMessage.error("未找到实体");
    return;
  }
  await graphApi.mergeEntity(id, {
    source_entity_id: a.id,
    target_entity_id: b.id,
  });
  await load();
}
async function addRelation() {
  if (graph.value.nodes.length < 2) return;
  const source = await ElMessageBox.prompt("输入起点实体名称", "添加实体关系");
  const target = await ElMessageBox.prompt("输入终点实体名称", "添加实体关系");
  const relation = await ElMessageBox.prompt("例如：发布、投资、隶属、关联政策", "关系类型");
  const a = graph.value.nodes.find((x: any) => x.name === source.value);
  const b = graph.value.nodes.find((x: any) => x.name === target.value);
  if (!a || !b) { ElMessage.error("未找到实体"); return; }
  const evidence = [...new Set<string>([...(a.evidence_content_ids || []), ...(b.evidence_content_ids || [])])];
  if (!evidence.length) { ElMessage.error("实体没有当前事件证据，拒绝创建关系"); return; }
  await graphApi.addRelation(id, { from_entity_id: a.id, to_entity_id: b.id, relation_type: relation.value, evidence_content_ids: evidence, confidence: 1 });
  await load();
}
async function verifyEdge(edge: any) {
  await graphApi.correctEdge(id, edge.id, { is_verified: true, confidence: 1 });
  await load();
  ElMessage.success("传播关系已人工确认并写入审计日志");
}
function date(v: string) {
  return v
    ? new Intl.DateTimeFormat("zh-CN", {
        dateStyle: "short",
        timeStyle: "short",
      }).format(new Date(v))
    : "时间未知";
}
onMounted(load);
</script>
<template>
  <main class="graph-page">
    <header class="titlebar">
      <button class="back" @click="router.push(`/events/${id}`)">
        <el-icon><ArrowLeft /></el-icon>事件详情
      </button>
      <div>
        <small>KNOWLEDGE GRAPH</small>
        <h1>{{ event?.title || "知识图谱与传播路径" }}</h1>
        <p>所有验证关系均保留来源证据；推断关系明确显示置信度。</p>
      </div>
      <div class="actions">
        <button @click="addEntity">
          <el-icon><Plus /></el-icon>添加实体</button
        ><button @click="merge">合并实体</button
        ><button @click="addRelation">添加关系</button
        ><button class="primary" :disabled="busy" @click="rebuild">
          <el-icon><Refresh /></el-icon>重新构建
        </button>
      </div>
    </header>
    <section class="metrics">
      <div>
        <span>实体</span><strong>{{ graph.nodes.length }}</strong>
      </div>
      <div>
        <span>实体关系</span><strong>{{ graph.edges.length }}</strong>
      </div>
      <div>
        <span>传播节点</span><strong>{{ prop.nodes.length }}</strong>
      </div>
      <div>
        <span>证据覆盖率</span
        ><strong
          >{{ Math.round((quality?.evidence_coverage || 0) * 100) }}%</strong
        >
      </div>
      <div>
        <span>已验证关系</span
        ><strong
          >{{ Math.round((quality?.verified_ratio || 0) * 100) }}%</strong
        >
      </div>
    </section>
    <div v-if="prop.status === 'insufficient_evidence'" class="refusal">
      <el-icon><Warning /></el-icon>
      <div>
        <strong>未生成跨平台传播路径</strong>
        <p>{{ prop.reason }}</p>
      </div>
    </div>
    <nav class="tabs">
      <button
        v-for="t in tabs"
        :key="t[0]"
        :class="{ active: tab === t[0] }"
        @click="tab = t[0]"
      >
        {{ t[1] }}
      </button>
    </nav>
    <section v-if="tab === 'network'" class="network-layout">
      <div class="canvas">
        <svg viewBox="0 0 460 380" role="img" aria-label="事件实体关系网络">
          <line
            v-for="e in graph.edges"
            :key="e.id"
            :x1="pos[e.from]?.x"
            :y1="pos[e.from]?.y"
            :x2="pos[e.to]?.x"
            :y2="pos[e.to]?.y"
            :class="{ inferred: !e.is_verified }"
            @click="selected = e"
          />
          <g
            v-for="n in positions"
            :key="n.id"
            :transform="`translate(${n.x},${n.y})`"
            tabindex="0"
            @click="selected = n"
          >
            <circle :r="Math.min(27, 15 + n.mention_count)" />
            <text y="4">{{ n.name.slice(0, 10) }}</text>
          </g>
        </svg>
        <p v-if="!graph.nodes.length" class="empty">
          暂无实体，点击“重新构建”从事件真实内容中抽取。
        </p>
      </div>
      <aside>
        <h3>实体与关系</h3>
        <template v-if="selected"
          ><strong>{{ selected.name || selected.relation_type }}</strong>
          <p v-if="selected.entity_type">
            {{ entityTypes[selected.entity_type] || selected.entity_type }} ·
            提及 {{ selected.mention_count }} 次
          </p>
          <p>置信度 {{ Math.round((selected.confidence || 0) * 100) }}%</p>
          <small v-if="selected.evidence_content_ids"
            >{{ selected.evidence_content_ids.length }} 条内容证据</small
          ></template
        >
        <p v-else>选择节点或关系查看证据。</p>
        <h3>相似事件</h3>
        <button
          v-for="x in similar"
          :key="x.id"
          class="similar"
          @click="router.push(`/events/${x.id}/graph`)"
        >
          <span>{{ x.title }}</span
          ><small
            >{{ Math.round(x.similarity * 100) }}% ·
            {{ x.shared_entity_count }} 个共享实体</small
          >
        </button>
      </aside>
    </section>
    <section v-else-if="tab === 'timeline'" class="timeline">
      <article v-for="(n, i) in prop.nodes" :key="n.id">
              <span>{{ Number(i) + 1 }}</span>
        <div>
          <small>{{ date(n.occurred_at) }} · {{ n.platform }}</small>
          <h3>{{ n.title }}</h3>
          <p>影响力 {{ n.influence_score }} · {{ n.node_type }}</p>
          <a :href="n.url" target="_blank">打开来源</a>
        </div>
      </article>
      <p v-if="!prop.nodes.length" class="empty">暂无传播节点。</p>
    </section>
    <section v-else-if="tab === 'sankey'" class="sankey">
      <div
        v-for="([platform, nodes], i) in platformGroups"
        :key="String(platform)"
        class="platform"
      >
        <header>
          <strong>{{ platform }}</strong
          ><small>{{ (nodes as any[]).length }} 个节点</small>
        </header>
        <button v-for="n in nodes as any[]" :key="n.id" @click="selected = n">
          <span>{{ n.title }}</span
          ><i
            :style="{ width: `${Math.max(8, n.influence_score)}%` }"
          /></button
        ><el-icon v-if="i < platformGroups.length - 1"><Right /></el-icon>
      </div>
      <p v-if="prop.status !== 'ready'" class="empty">
        证据不足，不展示可能误导的流向连接。
      </p>
    </section>
    <section v-else-if="tab === 'table'" class="tables">
      <h2>实体关系表</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>起点</th>
              <th>关系</th>
              <th>终点</th>
              <th>置信度</th>
              <th>证据</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="e in graph.edges" :key="e.id">
              <td>{{ pos[e.from]?.name }}</td>
              <td>{{ e.relation_type }}</td>
              <td>{{ pos[e.to]?.name }}</td>
              <td>{{ Math.round(e.confidence * 100) }}%</td>
              <td>{{ e.evidence_content_ids.length }} 条</td>
              <td>{{ e.is_verified ? "已验证" : "推断" }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <h2>传播关系表</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>来源</th>
              <th>目标</th>
              <th>关系</th>
              <th>置信度</th>
              <th>逐条证据</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="e in prop.edges" :key="e.id">
              <td>{{ pnodes[e.from]?.platform }}</td>
              <td>{{ pnodes[e.to]?.platform }}</td>
              <td>{{ e.relation_type }}</td>
              <td>{{ Math.round(e.confidence * 100) }}%</td>
              <td>
                <button class="evidence" @click="selected = e">
                  {{ e.evidence_quote.slice(0, 80) }}
                </button>
              </td>
              <td>
                <button v-if="!e.is_verified" @click="verifyEdge(e)">
                  人工确认</button
                ><span v-else>已验证</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
    <section v-else class="quality">
      <div class="quality-grid">
        <article>
          <span>实体识别可信度</span
          ><strong
            >{{ Math.round((quality?.entity_precision || 0) * 100) }}%</strong
          ><progress :value="quality?.entity_precision || 0" max="1" />
        </article>
        <article>
          <span>关系证据覆盖率</span
          ><strong
            >{{ Math.round((quality?.evidence_coverage || 0) * 100) }}%</strong
          ><progress :value="quality?.evidence_coverage || 0" max="1" />
        </article>
        <article>
          <span>人工/证据验证率</span
          ><strong
            >{{ Math.round((quality?.verified_ratio || 0) * 100) }}%</strong
          ><progress :value="quality?.verified_ratio || 0" max="1" />
        </article>
        <article>
          <span>待处理实体</span
          ><strong>{{ quality?.unresolved_count || 0 }}</strong>
        </article>
      </div>
      <h2>人工治理审计</h2>
      <article v-for="a in audits" :key="a.id" class="audit">
        <span>{{ a.action }}</span
        ><small>{{ date(a.created_at) }}</small>
      </article>
    </section>
    <el-drawer v-model="selected" title="证据详情" size="min(480px,92%)"
      ><template v-if="selected"
        ><h3>
          {{ selected.name || selected.title || selected.relation_type }}
        </h3>
        <blockquote v-if="selected.evidence_quote">
          {{ selected.evidence_quote }}
        </blockquote>
        <p>置信度 {{ Math.round((selected.confidence || 0) * 100) }}%</p>
        <p>
          {{ selected.is_verified ? "已验证关系" : "未验证推断" }}
        </p></template
      ></el-drawer
    >
  </main>
</template>
<style scoped>
.graph-page {
  min-height: 100vh;
  padding: 28px;
  background: #f5f7f8;
  color: #17211d;
}
.titlebar {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 20px;
  align-items: end;
}
.back,
.actions button,
.tabs button {
  border: 1px solid #ccd6d2;
  background: #fff;
  border-radius: 5px;
  min-height: 36px;
  padding: 0 12px;
  cursor: pointer;
}
.titlebar small {
  color: #16766d;
  font-weight: 800;
}
.titlebar h1 {
  margin: 4px 0;
  font-size: 25px;
}
.titlebar p {
  margin: 0;
  color: #6f7975;
}
.actions {
  display: flex;
  gap: 7px;
}
.actions .primary {
  color: white;
  background: #176f67;
}
.metrics {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  margin: 22px 0;
  background: #fff;
  border: 1px solid #dce3e0;
}
.metrics div {
  padding: 15px;
  border-right: 1px solid #e4e9e7;
}
.metrics span {
  display: block;
  color: #74807b;
  font-size: 11px;
}
.metrics strong {
  font-size: 24px;
}
.refusal {
  display: flex;
  gap: 12px;
  padding: 13px 16px;
  color: #8a5b0b;
  background: #fff4d8;
  border: 1px solid #eed89f;
}
.refusal p {
  margin: 3px 0;
}
.tabs {
  display: flex;
  margin: 18px 0;
  border-bottom: 1px solid #d4ddda;
}
.tabs button {
  border: 0;
  background: none;
  border-radius: 0;
}
.tabs button.active {
  color: #176f67;
  border-bottom: 2px solid #176f67;
}
.network-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  background: #fff;
  border: 1px solid #dce3e0;
}
.canvas {
  min-height: 560px;
  display: grid;
  place-items: center;
  background-image:
    linear-gradient(#edf1ef 1px, transparent 1px),
    linear-gradient(90deg, #edf1ef 1px, transparent 1px);
  background-size: 28px 28px;
}
.canvas svg {
  width: min(100%, 720px);
  height: auto;
}
.canvas line {
  stroke: #73a89f;
  stroke-width: 2;
  cursor: pointer;
}
.canvas line.inferred {
  stroke-dasharray: 6;
  stroke: #d49a50;
}
.canvas g {
  cursor: pointer;
}
.canvas circle {
  fill: #e1f1ed;
  stroke: #176f67;
  stroke-width: 2;
}
.canvas text {
  text-anchor: middle;
  font-size: 9px;
  fill: #153d37;
}
.network-layout aside {
  padding: 18px;
  border-left: 1px solid #dce3e0;
}
.similar {
  width: 100%;
  display: flex;
  flex-direction: column;
  text-align: left;
  padding: 9px;
  border: 0;
  border-bottom: 1px solid #e2e7e5;
  background: none;
}
.timeline {
  max-width: 850px;
  margin: auto;
}
.timeline article {
  display: grid;
  grid-template-columns: 42px 1fr;
  gap: 12px;
}
.timeline article > span {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: white;
  background: #176f67;
}
.timeline article > div {
  padding: 0 0 22px 16px;
  border-left: 1px solid #b8cbc5;
}
.timeline h3 {
  margin: 5px 0;
}
.sankey {
  min-height: 520px;
  display: flex;
  align-items: center;
  gap: 42px;
  overflow: auto;
  padding: 30px;
  background: #fff;
}
.platform {
  min-width: 210px;
  position: relative;
}
.platform header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}
.platform button {
  width: 100%;
  display: grid;
  margin: 8px 0;
  padding: 10px;
  border: 1px solid #d5dfdc;
  background: #fff;
  text-align: left;
}
.platform button i {
  height: 4px;
  margin-top: 7px;
  background: #43a395;
}
.platform > .el-icon {
  position: absolute;
  right: -31px;
  top: 50%;
  color: #60978e;
}
.tables,
.quality {
  background: #fff;
  padding: 20px;
  border: 1px solid #dce3e0;
}
.table-wrap {
  overflow: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  min-width: 720px;
}
th,
td {
  padding: 10px;
  text-align: left;
  border-bottom: 1px solid #e1e7e4;
  font-size: 12px;
}
.evidence {
  max-width: 360px;
  border: 0;
  background: none;
  text-align: left;
  color: #176f67;
}
.quality-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.quality-grid article {
  padding: 15px;
  background: #f5f8f7;
}
.quality-grid strong {
  display: block;
  font-size: 25px;
}
.quality-grid progress {
  width: 100%;
}
.audit {
  display: flex;
  justify-content: space-between;
  padding: 11px;
  border-bottom: 1px solid #e2e7e5;
}
.empty {
  color: #7a8580;
  text-align: center;
}
blockquote {
  padding: 14px;
  border-left: 3px solid #176f67;
  background: #edf5f3;
}
@media (max-width: 900px) {
  .titlebar {
    grid-template-columns: 1fr;
  }
  .back {
    width: max-content;
  }
  .actions {
    flex-wrap: wrap;
  }
  .metrics {
    grid-template-columns: repeat(2, 1fr);
  }
  .network-layout {
    display: block;
  }
  .network-layout aside {
    border-left: 0;
    border-top: 1px solid #ddd;
  }
  .quality-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 720px) {
  .graph-page {
    padding: 76px 12px 20px;
  }
  .titlebar p {
    display: none;
  }
  .metrics {
    grid-template-columns: repeat(2, 1fr);
  }
  .tabs {
    overflow: auto;
  }
  .tabs button {
    white-space: nowrap;
  }
  .canvas {
    min-height: 410px;
  }
  .sankey {
    min-height: 420px;
  }
  .quality-grid {
    grid-template-columns: 1fr;
  }
}
</style>
