<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessageBox } from "element-plus";
import { knowledgeApi } from "@/api/knowledge";
const bases = ref<any[]>([]),
  activeId = ref(""),
  docs = ref<any[]>([]),
  selected = ref<any>(),
  cap = ref<any>({}),
  busy = ref(false),
  query = ref(""),
  results = ref<any[]>([]);
const active = computed(() => bases.value.find((x) => x.id === activeId.value));
const labels: any = {
  queued: "排队中",
  processing: "索引中",
  ready: "可检索",
  failed: "解析失败",
};
async function loadBases() {
  bases.value = await knowledgeApi.bases();
  if (!activeId.value && bases.value.length) activeId.value = bases.value[0].id;
  if (activeId.value) await loadDocs();
}
async function loadDocs() {
  docs.value = await knowledgeApi.documents(activeId.value);
  selected.value = null;
  results.value = [];
}
async function createBase() {
  const x = await ElMessageBox.prompt("知识库名称", "新建知识库", {
    inputPattern: /\S+/,
    inputErrorMessage: "请输入名称",
  });
  await knowledgeApi.create({ name: x.value, description: "" });
  await loadBases();
}
async function deleteBase() {
  if (!active.value) return;
  const x = await ElMessageBox.prompt(
    `输入“${active.value.name}”确认。文件和向量将一并删除。`,
    "删除知识库",
    {
      confirmButtonText: "删除知识库",
      inputValidator: (v) => v === active.value.name || "名称不匹配",
      type: "warning",
    },
  );
  if (x.value === active.value.name) {
    await knowledgeApi.remove(activeId.value);
    activeId.value = "";
    await loadBases();
  }
}
async function upload(e: Event) {
  const files = Array.from((e.target as HTMLInputElement).files || []);
  if (!files.length) return;
  busy.value = true;
  try {
    await knowledgeApi.upload(activeId.value, files);
    await loadDocs();
  } finally {
    busy.value = false;
  }
}
async function importWeb() {
  const x = await ElMessageBox.prompt(
    "内网地址会被安全策略拒绝。",
    "导入公开网页",
    { inputPattern: /^https?:\/\//i, inputErrorMessage: "请输入完整 URL" },
  );
  busy.value = true;
  try {
    await knowledgeApi.importWeb(activeId.value, x.value);
    await loadDocs();
  } finally {
    busy.value = false;
  }
}
async function openDoc(x: any) {
  selected.value = await knowledgeApi.document(x.id);
  results.value = [];
}
async function retry(x: any) {
  await knowledgeApi.reindex(x.id);
  await loadDocs();
}
async function removeDoc(x: any) {
  await ElMessageBox.confirm(
    "删除后 Agent 与检索将立即停止召回。",
    "删除文档",
    { confirmButtonText: "删除文档", type: "warning" },
  );
  await knowledgeApi.removeDocument(x.id);
  await loadDocs();
}
async function testSearch() {
  if (query.value.trim())
    results.value = (
      await knowledgeApi.search(activeId.value, query.value)
    ).results;
  selected.value = null;
}
onMounted(async () => {
  cap.value = await knowledgeApi.capabilities();
  await loadBases();
});
</script>
<template>
  <main>
    <header class="page-head">
      <div>
        <small>PRIVATE KNOWLEDGE</small>
        <h1>知识库</h1>
        <p>管理私有资料、索引状态与可追溯检索。</p>
      </div>
      <button class="primary" @click="createBase">
        <el-icon><Plus /></el-icon>新建知识库
      </button>
    </header>
    <div class="workspace">
      <aside class="bases">
        <b>知识库</b
        ><button
          v-for="b in bases"
          :key="b.id"
          :class="{ active: b.id === activeId }"
          @click="
            activeId = b.id;
            loadDocs();
          "
        >
          <el-icon><FolderOpened /></el-icon
          ><span
            ><strong>{{ b.name }}</strong
            ><small>{{ b.description || "私有空间" }}</small></span
          >
        </button>
        <p v-if="!bases.length">还没有知识库</p>
      </aside>
      <section class="documents">
        <header>
          <div>
            <h2>{{ active?.name || "选择知识库" }}</h2>
            <small v-if="active"
              >{{ docs.length }} 个文档 · 单文件 {{ cap.max_file_mb }} MB</small
            >
          </div>
          <div v-if="active" class="actions">
            <label
              ><el-icon><Upload /></el-icon>上传<input
                type="file"
                multiple
                accept=".pdf,.docx,.md,.txt"
                :disabled="busy"
                @change="upload" /></label
            ><button @click="importWeb">
              <el-icon><Link /></el-icon>网页</button
            ><button title="删除知识库" @click="deleteBase">
              <el-icon><Delete /></el-icon>
            </button>
          </div>
        </header>
        <div v-if="active && !docs.length" class="empty">
          <el-icon><Document /></el-icon>
          <p>上传 PDF、DOCX、Markdown、TXT 或导入网页</p>
        </div>
        <article v-for="d in docs" :key="d.id" class="doc" @click="openDoc(d)">
          <el-icon><Document /></el-icon>
          <div>
            <strong>{{ d.filename }}</strong
            ><small
              >{{ d.source_type === "web" ? "网页导入" : "本地上传" }} ·
              {{ Math.ceil(d.byte_size / 1024) }} KB</small
            >
          </div>
          <span :class="d.status">{{ labels[d.status] }}</span
          ><button
            v-if="d.status === 'failed'"
            title="重试解析"
            @click.stop="retry(d)"
          >
            <el-icon><RefreshRight /></el-icon></button
          ><button title="删除文档" @click.stop="removeDoc(d)">
            <el-icon><Delete /></el-icon>
          </button>
        </article>
      </section>
      <aside class="inspector">
        <header>
          <strong>{{ selected ? "文档预览" : "检索测试" }}</strong
          ><button v-if="selected" @click="selected = null">返回检索</button>
        </header>
        <template v-if="selected"
          ><h3>{{ selected.filename }}</h3>
          <div v-for="r in selected.runs" :key="r.id" class="run">
            <b>{{ labels[r.status] || r.status }}</b
            ><progress :value="r.progress" max="100" /><small
              v-if="r.error_message"
              >{{ r.error_message }} · {{ r.diagnostic_id }}</small
            >
          </div>
          <section v-for="c in selected.chunks" :key="c.id" class="chunk">
            <small
              >{{ c.page ? `第 ${c.page} 页` : "" }}
              {{ c.paragraph ? `第 ${c.paragraph} 段` : "" }}</small
            >
            <p>{{ c.content }}</p>
          </section></template
        ><template v-else
          ><p>输入问题，检查混合检索实际召回的私有证据。</p>
          <div class="search">
            <input
              v-model="query"
              placeholder="输入检索问题"
              @keydown.enter="testSearch"
            /><button @click="testSearch">
              <el-icon><Search /></el-icon>
            </button>
          </div>
          <p v-if="!results.length" class="empty">没有检索结果</p>
          <article v-for="r in results" :key="r.chunk_id" class="result">
            <header>
              <span>私有知识</span><b>{{ r.filename }}</b
              ><em>{{ Math.round(r.score * 100) }}%</em>
            </header>
            <p>{{ r.quote }}</p>
            <small
              >{{ r.page ? `第 ${r.page} 页` : "" }}
              {{ r.paragraph ? `第 ${r.paragraph} 段` : "" }}</small
            >
          </article></template
        >
      </aside>
    </div>
  </main>
</template>
<style scoped>
main {
  padding: 30px;
  min-height: 100vh;
  background: #f5f7f8;
  color: #18201d;
}
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: end;
  margin-bottom: 20px;
}
.page-head small {
  color: #28746c;
  font-weight: 800;
}
.page-head h1 {
  margin: 4px 0;
  font-size: 28px;
}
.page-head p {
  margin: 0;
  color: #6b7571;
}
.primary,
.actions button,
.actions label {
  height: 38px;
  border: 1px solid #ccd6d2;
  border-radius: 6px;
  padding: 0 12px;
  background: #fff;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  cursor: pointer;
}
.primary {
  background: #176f67;
  color: #fff;
  border: 0;
}
.workspace {
  display: grid;
  grid-template-columns: 210px minmax(360px, 1fr) minmax(300px, 38%);
  min-height: 680px;
  background: #fff;
  border: 1px solid #dce3e0;
}
.bases,
.documents {
  border-right: 1px solid #e1e7e4;
}
.bases {
  padding: 15px;
}
.bases > b {
  display: block;
  margin: 7px;
  color: #69736f;
}
.bases > button {
  width: 100%;
  border: 0;
  background: none;
  padding: 11px 9px;
  display: flex;
  gap: 9px;
  text-align: left;
  border-radius: 5px;
}
.bases > button.active {
  background: #eaf4f1;
  color: #126a62;
}
.bases button span {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.bases small,
.documents small {
  color: #78817e;
}
.documents > header {
  min-height: 72px;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e1e7e4;
}
.documents h2 {
  margin: 0;
}
.actions {
  display: flex;
  gap: 6px;
}
.actions input {
  display: none;
}
.doc {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr) auto 28px 28px;
  gap: 8px;
  align-items: center;
  padding: 13px;
  border-bottom: 1px solid #edf0ef;
  cursor: pointer;
}
.doc div {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.doc strong {
  overflow: hidden;
  text-overflow: ellipsis;
}
.doc > span {
  font-size: 11px;
  padding: 4px;
  background: #eef1f0;
}
.doc > .ready {
  color: #177367;
  background: #e3f3ee;
}
.doc > .failed {
  color: #b93d35;
  background: #fae9e7;
}
.doc button,
.inspector > header button {
  border: 0;
  background: none;
  cursor: pointer;
}
.inspector {
  padding: 18px;
  overflow: auto;
}
.inspector > header {
  display: flex;
  justify-content: space-between;
  padding-bottom: 12px;
  border-bottom: 1px solid #e1e7e4;
}
.run {
  display: grid;
  gap: 5px;
  padding: 10px;
  background: #f6f8f7;
}
.chunk,
.result {
  padding: 12px 0;
  border-bottom: 1px solid #e5eae8;
}
.chunk p,
.result p {
  white-space: pre-wrap;
  line-height: 1.55;
  font-size: 13px;
}
.search {
  display: grid;
  grid-template-columns: 1fr 40px;
}
.search input {
  height: 40px;
  border: 1px solid #ccd5d2;
  padding: 0 10px;
}
.search button {
  border: 0;
  background: #176f67;
  color: white;
}
.result header {
  display: flex;
  gap: 7px;
}
.result header span {
  font-size: 10px;
  color: #176f67;
  background: #e6f4f0;
  padding: 3px;
}
.result em {
  margin-left: auto;
}
.empty {
  padding: 50px 15px;
  text-align: center;
  color: #78817e;
}
@media (max-width: 1050px) {
  .workspace {
    grid-template-columns: 190px 1fr;
  }
  .inspector {
    grid-column: 1/-1;
    border-top: 1px solid #ddd;
  }
}
@media (max-width: 720px) {
  main {
    padding: 78px 12px 20px;
  }
  .page-head p {
    display: none;
  }
  .workspace {
    display: block;
  }
  .bases {
    display: flex;
    overflow: auto;
    border-bottom: 1px solid #ddd;
  }
  .bases > b {
    display: none;
  }
  .bases > button {
    min-width: 150px;
  }
  .documents > header {
    align-items: start;
  }
  .actions {
    flex-wrap: wrap;
  }
  .doc {
    grid-template-columns: 26px minmax(0, 1fr) auto 28px;
  }
  .inspector {
    min-height: 400px;
  }
}
</style>
