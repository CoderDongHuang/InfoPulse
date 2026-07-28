<script setup lang="ts">
import { ref } from 'vue'

const open = ref('start')
const topics = [
  { id: 'start', title: '开始使用', body: '先在数据源中心连接公开来源并完成同步，再到 Discover 或搜索中心查看真实内容。Workspace 只聚合已有数据，不生成模拟建议。' },
  { id: 'evidence', title: '引用与可信度', body: 'AI 分析、Agent 和报告中的事实结论必须附带来源。点击引用可回到公开内容或你有权访问的私有知识段落；证据不足时系统会拒绝给出结论。' },
  { id: 'alerts', title: '预警处置', body: '在预警中心创建规则并先执行历史回放。真实触发后可以确认、分派、记录处置、关闭或标记误报，所有状态变化都会进入审计记录。' },
  { id: 'privacy', title: '隐私与删除', body: '知识库按用户隔离。删除文档后内容将无法继续召回；删除账号需要再次验证密码，并同步删除私有知识文件及关联业务数据。' },
  { id: 'support', title: '问题诊断', body: '请求失败时记录页面显示的诊断编号、发生时间和操作入口。不要提交访问令牌、Cookie、Webhook 密钥、私有文档正文或完整请求头。' },
]
</script>

<template>
  <main>
    <header><small>PRODUCT GUIDE</small><h1>帮助中心</h1><p>按工作流程查找操作说明、证据规则和故障处理入口。</p></header>
    <section class="guide">
      <nav aria-label="帮助主题">
        <button v-for="topic in topics" :key="topic.id" :class="{active: open===topic.id}" @click="open=topic.id">{{ topic.title }}</button>
      </nav>
      <article v-for="topic in topics" v-show="open===topic.id" :key="topic.id">
        <span>{{String(topics.indexOf(topic)+1).padStart(2,'0')}}</span>
        <h2>{{topic.title}}</h2>
        <p>{{topic.body}}</p>
      </article>
    </section>
    <section class="quick"><h2>常用入口</h2><div><router-link to="/sources">数据源中心</router-link><router-link to="/search">搜索中心</router-link><router-link to="/alerts">预警中心</router-link><router-link to="/knowledge">知识库</router-link></div></section>
  </main>
</template>

<style scoped>
main{padding:30px;min-height:100vh;background:#f5f7f8;color:#17211d}header{max-width:760px}header small{color:#176f67;font-weight:800}h1{margin:5px 0;font-size:30px}header p{color:#65706b}.guide{display:grid;grid-template-columns:250px minmax(0,1fr);margin-top:28px;border:1px solid #d8e0dd;background:#fff;min-height:360px}.guide nav{display:flex;flex-direction:column;padding:12px;border-right:1px solid #e0e6e3}.guide button{padding:13px;border:0;border-radius:4px;background:none;text-align:left;color:#4f5c57}.guide button.active{background:#e8f2ef;color:#176f67;font-weight:700}.guide article{padding:36px;max-width:740px}.guide article span{color:#a64a42;font-weight:800}.guide h2{font-size:22px}.guide article p{line-height:1.8;color:#52605a}.quick{margin-top:24px}.quick div{display:flex;flex-wrap:wrap;gap:8px}.quick a{padding:10px 13px;border:1px solid #cfd9d5;border-radius:4px;background:#fff;color:#176f67;text-decoration:none}@media(max-width:720px){main{padding:76px 12px 20px}.guide{display:block}.guide nav{border-right:0;border-bottom:1px solid #e0e6e3}.guide article{padding:24px 18px}}
</style>
