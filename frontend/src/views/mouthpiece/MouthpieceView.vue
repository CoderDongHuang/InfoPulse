<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { workflowApi } from '@/api/workflows'
import { copyToClipboard } from '@/utils/clipboard'

const loading = ref(false)
const route = useRoute()
const form = reactive({ source_text: '', scene: 'social', tone: 'humorous', intensity: 60, length: 'medium' })
const result = ref<any>(null)
const scenes = [{ value: 'social', label: '社交动态' }, { value: 'workplace', label: '职场表达' }, { value: 'review', label: '观点评论' }, { value: 'announcement', label: '公开声明' }]
const tones = [{ value: 'sharp', label: '犀利' }, { value: 'humorous', label: '幽默' }, { value: 'gentle', label: '温柔' }, { value: 'rational', label: '理性' }]
const count = computed(() => form.source_text.length)

async function generate() {
  if (form.source_text.trim().length < 8) return ElMessage.warning('多写一点，至少 8 个字')
  loading.value = true
  try { result.value = await workflowApi.generateMouthpiece(form) }
  finally { loading.value = false }
}

async function copy(text: string) {
  await copyToClipboard(text, '文案')
}
onMounted(() => { if (typeof route.query.q === 'string') form.source_text = route.query.q.slice(0, 3000) })
</script>

<template>
  <div class="writing-page">
    <header class="studio-head page-shell">
      <div><p>AI WRITING STUDIO / 02</p><h1>把情绪写得<br>有分寸，也有传播力。</h1></div>
      <div class="head-stamp">DRAFT<br>TO<br>POST</div>
    </header>

    <main class="writing-grid page-shell">
      <section class="editor-pane">
        <div class="control-row">
          <label>发布场景<select v-model="form.scene"><option v-for="item in scenes" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
          <label>篇幅<select v-model="form.length"><option value="short">短句</option><option value="medium">标准</option><option value="long">长文</option></select></label>
        </div>
        <label class="source-editor"><span>你真正想说的话</span><textarea v-model="form.source_text" maxlength="3000" placeholder="先按自己的方式说，不用组织语言。事实、情绪和立场都可以放进来。"></textarea><small>{{ count }} / 3000</small></label>
        <div class="tone-control"><span>表达风格</span><div><button v-for="item in tones" :key="item.value" type="button" :class="{ active: form.tone === item.value }" @click="form.tone = item.value">{{ item.label }}</button></div></div>
        <div class="intensity"><span>情绪强度</span><el-slider v-model="form.intensity" :show-tooltip="false"/><strong>{{ form.intensity }}</strong></div>
        <button class="generate-button" type="button" :disabled="loading" @click="generate"><span>{{ loading ? '正在重写' : '生成可发布文案' }}</span><el-icon><MagicStick /></el-icon></button>
      </section>

      <section class="preview-pane">
        <div class="paper" :class="{ empty: !result }">
          <div class="paper-meta"><span>INFOPULSE COPY DESK</span><span>{{ form.tone.toUpperCase() }} / {{ form.intensity }}</span></div>
          <template v-if="result">
            <h2>{{ result.title }}</h2><p class="body-copy">{{ result.body }}</p>
            <div class="hashtags"><span v-for="tag in result.hashtags" :key="tag">{{ tag }}</span></div>
            <button type="button" class="copy-button" @click="copy(`${result.title}\n\n${result.body}\n\n${result.hashtags.join(' ')}`)"><el-icon><CopyDocument /></el-icon>复制成稿</button>
          </template>
          <template v-else><div class="blank-lines"><i></i><i></i><i></i><i></i><i></i></div><p>成稿会出现在这里。</p></template>
        </div>
        <div v-if="result?.alternatives?.length" class="alternatives"><p>其他表达</p><button v-for="(item, index) in result.alternatives" :key="item" type="button" @click="copy(item)"><span>0{{ Number(index) + 1 }}</span>{{ item }}</button></div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.writing-page { min-height: calc(100vh - 64px); color: #241d22; background: #f7efe8; }
.studio-head { padding-top: 46px; padding-bottom: 26px; display: flex; justify-content: space-between; align-items: flex-end; border-bottom: 2px solid #2d2228; }
.studio-head p { color: #d04c46; font: 800 11px/1 "Cascadia Code", monospace; }.studio-head h1 { margin: 12px 0 0; font: 800 clamp(36px, 5vw, 68px)/1.02 Georgia, "Songti SC", serif; }.head-stamp { width: 82px; height: 82px; border: 2px solid #d04c46; color: #d04c46; transform: rotate(4deg); display: grid; place-items: center; text-align: center; font: 800 10px/1.2 "Cascadia Code", monospace; }
.writing-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(420px, .85fr); gap: 48px; align-items: start; }
.editor-pane { padding: 30px 0; }.control-row { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }.control-row label, .source-editor { display: grid; gap: 7px; font-size: 11px; font-weight: 800; }.control-row select { min-height: 42px; padding: 0 12px; border: 1px solid #cbbdb2; background: rgba(255,255,255,.55); outline: 0; }
.source-editor { position: relative; margin-top: 20px; }.source-editor textarea { min-height: 270px; padding: 18px; resize: vertical; border: 1px solid #cbbdb2; outline: 0; background: rgba(255,255,255,.62); color: #2d2228; font-size: 17px; line-height: 1.8; }.source-editor textarea:focus { border-color: #d04c46; box-shadow: 0 0 0 3px rgba(208,76,70,.1); }.source-editor small { position: absolute; right: 10px; bottom: 8px; color: #9b8c82; font-weight: 400; }
.tone-control { margin-top: 22px; display: flex; align-items: center; justify-content: space-between; }.tone-control > span, .intensity > span { font-size: 11px; font-weight: 800; }.tone-control div { display: flex; gap: 6px; }.tone-control button { padding: 7px 13px; border: 1px solid #cbbdb2; background: transparent; cursor: pointer; }.tone-control button.active { border-color: #2d2228; color: white; background: #2d2228; }
.intensity { margin-top: 20px; display: grid; grid-template-columns: 70px 1fr 30px; align-items: center; gap: 12px; }.intensity strong { color: #d04c46; font-family: "Cascadia Code", monospace; }
.generate-button { width: 100%; min-height: 50px; margin-top: 22px; padding: 0 18px; display: flex; align-items: center; justify-content: space-between; border: 0; background: #d04c46; color: white; cursor: pointer; }.generate-button:hover { background: #b53c37; }.generate-button:disabled { opacity: .6; }
.preview-pane { padding: 30px 0; }.paper { position: relative; min-height: 520px; padding: 30px 32px 76px; background: #fffdfa; box-shadow: 0 18px 50px rgba(79,55,42,.16); transform: rotate(.5deg); }.paper::before { content: ''; position: absolute; inset: 12px; border: 1px solid #e8ded5; pointer-events: none; }.paper-meta { position: relative; display: flex; justify-content: space-between; padding-bottom: 14px; border-bottom: 1px solid #2d2228; color: #77665b; font: 700 9px/1 "Cascadia Code", monospace; }.paper h2 { position: relative; margin: 42px 0 18px; font: 800 32px/1.22 Georgia, "Songti SC", serif; }.body-copy { position: relative; white-space: pre-wrap; font-size: 15px; line-height: 1.95; }.hashtags { position: relative; margin-top: 25px; display: flex; gap: 8px; flex-wrap: wrap; color: #d04c46; font-size: 12px; }.copy-button { position: absolute; right: 32px; bottom: 30px; padding: 8px 12px; border: 1px solid #2d2228; background: transparent; display: flex; gap: 6px; align-items: center; cursor: pointer; }.paper.empty { display: grid; align-content: center; text-align: center; color: #a49489; }.blank-lines { display: grid; gap: 15px; }.blank-lines i { height: 1px; background: #e8ded5; }.blank-lines i:nth-child(2), .blank-lines i:nth-child(4) { width: 82%; }.alternatives { margin-top: 18px; }.alternatives > p { font-size: 11px; font-weight: 800; }.alternatives button { width: 100%; padding: 11px 0; display: grid; grid-template-columns: 32px 1fr; gap: 8px; border: 0; border-top: 1px solid #d8cbc1; background: transparent; text-align: left; cursor: pointer; }.alternatives button span { color: #d04c46; font-family: "Cascadia Code", monospace; }
@media (max-width: 980px) { .writing-grid { grid-template-columns: 1fr; gap: 0; }.paper { transform: none; } }
@media (max-width: 560px) { .studio-head h1 { font-size: 37px; }.head-stamp { display: none; }.control-row { grid-template-columns: 1fr; }.tone-control { align-items: flex-start; gap: 12px; flex-direction: column; }.tone-control div { flex-wrap: wrap; }.paper { padding: 24px 22px 72px; } }
</style>

<style scoped>
.writing-page { color: #17231f; background: #eef2f0; }
.studio-head { position: relative; min-height: 238px; margin-top: 24px; padding: 34px; overflow: hidden; border: 0; border-radius: 8px; color: white; background: linear-gradient(90deg, rgba(12,34,28,.94), rgba(12,34,28,.62)), url('../../assets/images/auth-newsroom.jpg') center 46%/cover; box-shadow: 0 18px 44px rgba(22,48,40,.14); }
.studio-head p { color: #82d4c8; letter-spacing: .12em; }.studio-head h1 { max-width: 800px; font: 600 clamp(36px, 4.5vw, 62px)/1.05 Georgia, "Songti SC", serif; }.head-stamp { border-color: #ef746c; color: #ef8c85; background: rgba(9,28,23,.38); backdrop-filter: blur(8px); }
.writing-grid { gap: 38px; }.editor-pane, .preview-pane { padding-top: 34px; }.control-row select, .source-editor textarea { border-color: #c7d3ce; border-radius: 5px; color: #20352e; background: rgba(255,255,255,.84); }.source-editor textarea { min-height: 286px; box-shadow: 0 10px 28px rgba(25,54,45,.04); }.source-editor textarea:focus { border-color: #218a80; box-shadow: 0 0 0 4px rgba(33,138,128,.1); }
.tone-control button { border-color: #bdcbc6; border-radius: 4px; color: #4f6860; transition: color 160ms ease, background 160ms ease, transform 160ms ease; }.tone-control button:hover { transform: translateY(-1px); border-color: #5e8f85; }.tone-control button.active { border-color: #18312a; background: #18312a; }.intensity strong { color: #df625b; }
.generate-button { border-radius: 5px; background: #167f76; box-shadow: 0 10px 24px rgba(22,127,118,.18); transition: transform 160ms ease, background 160ms ease; }.generate-button:hover { transform: translateY(-2px); background: #116a63; }
.paper { border-radius: 4px; background: #fff; box-shadow: 0 22px 55px rgba(31,58,49,.14); }.paper::before { border-color: #e1e8e5; }.paper-meta { color: #6d817a; border-color: #20352e; }.hashtags, .alternatives button span { color: #d95751; }.copy-button { border-color: #244039; border-radius: 4px; }.alternatives button { border-color: #ccd7d2; }
@media (max-width: 980px) { .studio-head { min-height: 220px; }.writing-grid { gap: 0; } }
@media (max-width: 560px) { .studio-head { min-height: 250px; margin-top: 12px; padding: 26px 22px; }.studio-head h1 { font-size: 36px; }.writing-grid { width: calc(100% - 24px); }.paper { box-shadow: 0 16px 36px rgba(31,58,49,.12); } }
</style>
