<script setup lang="ts">
defineProps<{ value: unknown }>()
const labels: Record<string, string> = {
  topic: '主题', title: '标题', overview: '概览', summary: '摘要', body: '正文',
  sentiment: '情绪分布', positive: '正向', neutral: '中性', negative: '负向', confidence: '置信度',
  volume: '样本量', sources: '数据来源', platform: '平台', count: '数量', status: '状态',
  key_points: '核心观点', label: '要点', detail: '详情', stance: '立场',
  representative_opinions: '代表性观点', content: '内容', url: '来源链接', risks: '风险提示',
  generated_at: '生成时间', events: '事件节点', date: '时间', time: '时间', description: '说明',
  timeline: '事件脉络', significance: '影响', evidence: '证据', references: '参考来源',
  hashtags: '话题标签', tips: '建议', keyword: '关键词', platforms: '平台范围', max_items: '采集上限',
  source_text: '原始文本', tone: '语气', length: '篇幅', target_platform: '目标平台',
}
</script>
<template>
  <ol v-if="Array.isArray(value) && value.length" class="result-list"><li v-for="(item, index) in value" :key="index"><WorkflowResult :value="item" /></li></ol>
  <p v-else-if="Array.isArray(value)" class="result-text">无</p>
  <dl v-else-if="value !== null && typeof value === 'object'" class="result-fields"><template v-for="(item, key) in value" :key="key"><dt>{{ labels[String(key)] || key }}</dt><dd><WorkflowResult :value="item" /></dd></template></dl>
  <p v-else class="result-text">{{ value ?? '未提供' }}</p>
</template>
<style scoped>
.result-fields{margin:12px 0}.result-fields>dt{margin:16px 0 6px;font-size:13px;font-weight:700;color:var(--color-primary,#167f76)}.result-fields>dd{margin:0 0 12px;padding-left:12px;border-left:2px solid #e1e9e5}.result-text{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.85}.result-list{padding-left:22px}.result-list>li{margin:10px 0}
</style>
