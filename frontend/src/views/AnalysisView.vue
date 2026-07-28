<script setup lang="ts">
import { onBeforeUnmount, ref } from "vue";
import { useRoute } from "vue-router";
import { ElMessage } from "element-plus";
import { analysisApi } from "@/api/analyses";
const route = useRoute(),
  eventId = ref(String(route.query.event_id || "")),
  type = ref("summary"),
  running = ref(false),
  streamed = ref(""),
  result = ref<any>(null),
  error = ref(""),
  citation = ref<any>(null);
let connection: any;
const templates = [
  ["summary", "摘要"],
  ["viewpoints", "观点"],
  ["controversies", "争议"],
  ["causes", "原因"],
  ["impact", "影响"],
  ["risk", "风险"],
  ["forecast", "预测"],
  ["advice", "建议"],
];
function run() {
  if (!eventId.value) {
    ElMessage.warning("请先选择有真实来源的事件");
    return;
  }
  running.value = true;
  result.value = null;
  streamed.value = "";
  error.value = "";
  connection = analysisApi.stream(
    { analysis_type: type.value, event_ids: [eventId.value], content_ids: [] },
    {
      onChunk: (x: string) => (streamed.value += x),
      onResult: (x: any) => {
        result.value = x;
        running.value = false;
      },
      onError: (x: string) => {
        error.value = x;
        running.value = false;
      },
    },
  );
}
function stop() {
  connection?.close();
  running.value = false;
}
async function regenerate() {
  result.value = await analysisApi.regenerate(result.value.id);
  streamed.value = result.value.summary;
}
onBeforeUnmount(stop);
</script>
<template>
  <main class="analysis-page">
    <header>
      <p>AI ANALYSIS / EVIDENCE FIRST</p>
      <h1>可追溯 AI 分析</h1>
      <span>每条事实结论必须绑定真实来源；没有证据时系统拒绝生成。</span>
    </header>
    <section class="setup">
      <label
        >事件 ID<input v-model="eventId" placeholder="从事件详情进入可自动填写"
      /></label>
      <div class="templates">
        <button
          v-for="t in templates"
          :key="t[0]"
          :class="{ active: type === t[0] }"
          @click="type = t[0]"
        >
          {{ t[1] }}
        </button>
      </div>
      <button class="run" :disabled="running" @click="run">
        {{ running ? "分析中" : "开始分析" }}</button
      ><button v-if="running" @click="stop">停止</button>
    </section>
    <section v-if="error" class="empty">
      <strong>未生成结论</strong>
      <p>{{ error }}</p>
    </section>
    <section v-if="running || streamed" class="stream">
      <small>STREAMING OUTPUT</small>
      <p>{{ streamed || "正在核验来源与引用…" }}</p>
    </section>
    <template v-if="result"
      ><section class="meta">
        <div>
          <span>置信度</span><b>{{ Math.round(result.confidence) }}%</b>
        </div>
        <div>
          <span>证据覆盖率</span
          ><b>{{ Math.round(result.evidence_coverage) }}%</b>
        </div>
        <div>
          <span>模型</span><b>{{ result.model.name }}</b>
        </div>
        <div>
          <span>版本</span><b>v{{ result.version }}</b>
        </div>
        <div>
          <span>生成时间</span
          ><b>{{ new Date(result.generated_at).toLocaleString() }}</b>
        </div>
      </section>
      <section class="claims">
        <article v-for="(claim, i) in result.result.claims" :key="i">
          <header>
            <span>结论 {{ Number(i) + 1 }}</span
            ><em v-if="claim.inference">推断 / 存在不确定性</em>
          </header>
          <p>{{ claim.claim }}</p>
          <small v-if="claim.uncertainty">{{ claim.uncertainty }}</small>
          <footer>
            <button
              v-for="c in result.citations.filter(
                (x: any) => x.claim_index === i,
              )"
              :key="c.id"
              @click="citation = c"
            >
              [{{ result.citations.indexOf(c) + 1 }}] {{ c.source }}
            </button>
          </footer>
        </article>
      </section>
      <button class="regen" @click="regenerate">
        重新生成并保留当前版本
      </button></template
    ><el-drawer v-model="citation" title="来源引用" size="min(480px, 92%)"
      ><template v-if="citation"
        ><h3>{{ citation.title }}</h3>
        <p class="quote">{{ citation.quote }}</p>
        <p>{{ citation.source }} · {{ citation.published_at }}</p>
        <a :href="citation.url" target="_blank">打开真实原文</a></template
      ></el-drawer
    >
  </main>
</template>
<style scoped>
.analysis-page {
  min-height: 100vh;
  padding: 40px clamp(18px, 5vw, 72px);
  background: #f2f5f4;
  color: #17231f;
}
.analysis-page > header {
  padding-bottom: 26px;
  border-bottom: 1px solid #cbd6d2;
}
.analysis-page > header p {
  color: #188178;
  font: 700 10px monospace;
}
.analysis-page h1 {
  margin: 8px 0;
  font:
    650 42px Georgia,
    serif;
}
.analysis-page > header span {
  color: #687a74;
}
.setup {
  padding: 18px 0;
  display: flex;
  gap: 8px;
  align-items: end;
  flex-wrap: wrap;
}
.setup label {
  display: grid;
  gap: 6px;
  flex: 1;
  min-width: 240px;
}
.setup input {
  height: 40px;
  padding: 0 10px;
}
.templates {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
}
.templates button,
.setup > button,
.regen {
  height: 40px;
  padding: 0 12px;
  border: 1px solid #c7d2ce;
  background: white;
}
.templates button.active,
.setup .run {
  color: white;
  background: #18302a;
}
.stream,
.empty {
  padding: 28px;
  border: 1px solid #cfdbd6;
  background: white;
}
.stream p {
  font:
    600 21px/1.7 Georgia,
    serif;
}
.meta {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  margin-top: 16px;
  background: white;
}
.meta div {
  padding: 16px;
  border: 1px solid #dce4e1;
}
.meta span,
.meta b {
  display: block;
}
.claims {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}
.claims article {
  padding: 22px;
  border: 1px solid #ced9d5;
  background: white;
}
.claims header {
  display: flex;
  justify-content: space-between;
  color: #197d74;
}
.claims em,
.claims small {
  color: #9a6513;
}
.claims p {
  font-size: 17px;
  line-height: 1.7;
}
.claims footer button {
  margin-right: 6px;
  border: 0;
  color: #176f68;
  background: #e7f3f0;
}
.quote {
  padding: 16px;
  border-left: 3px solid #168078;
  background: #edf5f3;
}
@media (max-width: 760px) {
  .analysis-page {
    padding: 24px 15px;
  }
  .meta {
    grid-template-columns: 1fr 1fr;
  }
  .claims header {
    flex-direction: column;
  }
}
</style>
