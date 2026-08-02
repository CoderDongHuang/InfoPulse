<template>
  <main class="coordination-page">
    <header class="page-header">
      <div><p class="eyebrow">STAGE 23 CONTROL PLANE</p><h1>全球情报协同</h1><p>联邦互操作、持续验证、全球结算与联合危机指挥。</p></div>
      <el-button :icon="Refresh" circle title="刷新" :loading="loading" @click="load" />
    </header>
    <section class="metrics" aria-label="运行概览">
      <div v-for="item in metrics" :key="item.key" class="metric"><span>{{ item.label }}</span><strong>{{ overview[item.key] ?? 0 }}</strong></div>
    </section>
    <el-tabs v-model="activeTab" class="workspace">
      <el-tab-pane label="协议与证明" name="trust">
        <div class="split"><section><h2>跨云节点登记</h2><el-form label-position="top"><el-form-item label="节点标识"><el-input v-model="node.node_key" /></el-form-item><div class="two"><el-form-item label="云"><el-input v-model="node.cloud" /></el-form-item><el-form-item label="区域"><el-input v-model="node.region" /></el-form-item></div><el-form-item label="身份指纹"><el-input v-model="node.identity_fingerprint" /></el-form-item><el-button type="primary" :icon="Connection" @click="registerNode">登记节点</el-button></el-form></section>
        <section><h2>在线验证状态</h2><div class="gate"><el-icon><CircleCheck /></el-icon><div><strong>执行前验证已启用</strong><p>血缘、TEE、模型签名和责任链失败会阻断执行。</p></div></div></section></div>
      </el-tab-pane>
      <el-tab-pane label="持续合规" name="compliance"><div class="capability-grid"><article v-for="item in compliance" :key="item.title"><el-icon><component :is="item.icon" /></el-icon><h3>{{ item.title }}</h3><p>{{ item.text }}</p></article></div></el-tab-pane>
      <el-tab-pane label="风险与危机" name="crisis"><div class="capability-grid"><article><el-icon><Warning /></el-icon><h3>系统性风险雷达</h3><p>集中度、级联故障、市场操纵和数据投毒进入生产门禁。</p></article><article><el-icon><Money /></el-icon><h3>全球结算</h3><p>汇率锁定、税务预扣、托管与付款必须满足会计守恒。</p></article><article><el-icon><Bell /></el-icon><h3>联合指挥</h3><p>跨租户命令以向前哈希链记录，保留完整责任链。</p></article></div></el-tab-pane>
    </el-tabs>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Bell, CircleCheck, Connection, DataAnalysis, DocumentChecked, Money, Refresh, Warning } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { globalCoordinationApi } from '@/api/globalCoordination'

const loading = ref(false); const activeTab = ref('trust'); const overview = reactive<Record<string, number>>({})
const node = reactive({ node_key: '', cloud: '', region: '', protocol_versions: ['2.0'], capabilities: ['proof', 'settlement', 'crisis'], identity_issuer: 'enterprise-oidc', identity_fingerprint: '' })
const metrics = computed(() => [{ key: 'nodes', label: '联邦节点' }, { key: 'proofs', label: '在线证明' }, { key: 'risks', label: '风险信号' }, { key: 'drifts', label: '控制漂移' }, { key: 'settlements', label: '全球结算' }, { key: 'crisis_rooms', label: '危机室' }])
const compliance = [{ title: '监管增量', text: '版本化更新、冲突解析与紧急撤回。', icon: DocumentChecked }, { title: '控制漂移', text: '实时比对期望状态并生成修复建议。', icon: Warning }, { title: '联邦评测', text: '仅持久化聚合指标和可验证证明。', icon: DataAnalysis }]
async function load() { loading.value = true; try { Object.assign(overview, await globalCoordinationApi.overview()) } finally { loading.value = false } }
async function registerNode() { try { await globalCoordinationApi.createNode(node); ElMessage.success('节点已登记'); await load() } catch { ElMessage.error('请检查节点信息和 64 位身份指纹') } }
onMounted(load)
</script>

<style scoped>
.coordination-page{max-width:1200px;margin:0 auto;padding:28px 24px 48px;color:var(--el-text-color-primary)}.page-header{display:flex;align-items:flex-start;justify-content:space-between;border-bottom:1px solid var(--el-border-color);padding-bottom:20px}.page-header h1{font-size:30px;margin:4px 0 6px;letter-spacing:0}.page-header p{margin:0;color:var(--el-text-color-secondary)}.eyebrow{font-size:12px;color:var(--el-color-primary)!important;font-weight:700}.metrics{display:grid;grid-template-columns:repeat(6,1fr);border-bottom:1px solid var(--el-border-color)}.metric{padding:20px 16px;border-right:1px solid var(--el-border-color)}.metric:last-child{border-right:0}.metric span{display:block;font-size:13px;color:var(--el-text-color-secondary)}.metric strong{font-size:27px}.workspace{margin-top:24px}.split{display:grid;grid-template-columns:1fr 1fr;gap:40px;padding:12px 0}.split section{min-width:0}.split h2{font-size:18px}.two{display:grid;grid-template-columns:1fr 1fr;gap:12px}.gate{display:flex;gap:14px;padding:18px 0;border-top:1px solid var(--el-border-color);border-bottom:1px solid var(--el-border-color)}.gate .el-icon{font-size:26px;color:var(--el-color-success)}.gate p{margin:5px 0;color:var(--el-text-color-secondary)}.capability-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--el-border-color);border:1px solid var(--el-border-color)}.capability-grid article{background:var(--el-bg-color);padding:22px;min-height:140px}.capability-grid .el-icon{font-size:24px;color:var(--el-color-primary)}.capability-grid h3{font-size:16px}.capability-grid p{font-size:14px;color:var(--el-text-color-secondary);line-height:1.6}@media(max-width:800px){.metrics{grid-template-columns:repeat(2,1fr)}.metric{border-bottom:1px solid var(--el-border-color)}.split,.capability-grid{grid-template-columns:1fr}.coordination-page{padding:18px 14px}.page-header h1{font-size:25px}}
</style>
