<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { stage3Api } from '@/api/stage3'
const router=useRouter(), loading=ref(true), data=ref<any>({attention:[],recommendations:[],favorites:[],recent_views:[],recent_reports:[],source_warnings:[]})
async function load(){ loading.value=true; try{data.value=await stage3Api.workspace()}finally{loading.value=false} }
async function ignore(id:string){await stage3Api.feedback(id,'not_interested');await load()}
onMounted(load)
</script>
<template><main class="stage-page"><header class="page-head"><div><p>WORKSPACE / {{ data.date }}</p><h1>今天，从重要信号开始</h1><span>你的关注、建议和最近工作集中在一个可执行视图中。</span></div><button @click="router.push('/discover')">打开 Discover</button></header>
<section v-if="loading" class="empty">正在读取真实情报数据…</section>
<template v-else><section v-if="data.source_warnings.length" class="warning"><strong>数据覆盖提醒</strong><span>{{data.source_warnings[0].message}}</span><button @click="router.push('/sources')">管理数据源</button></section>
<div class="workspace-grid"><section class="main-column"><div class="section-title"><div><small>AI DAILY BRIEF</small><h2>今日建议</h2></div><span>{{data.recommendations.length}} 条</span></div>
<div v-if="!data.recommendations.length" class="empty"><strong>暂无真实建议</strong><p>建议只从今日已同步内容中生成，不使用模拟数据。</p></div>
<article v-for="(item,i) in data.recommendations" :key="item.id" class="recommend"><b>0{{Number(i)+1}}</b><div><h3>{{item.title}}</h3><p>{{item.summary||'原始内容暂无摘要'}}</p><ul><li v-for="reason in item.recommendation_reasons" :key="reason.rule">{{reason.label}}</li></ul><footer><a :href="item.canonical_url" target="_blank">查看原文</a><button @click="stage3Api.favorite('content',item.id)">收藏</button><button @click="ignore(item.id)">不感兴趣</button></footer></div></article></section>
<aside><section><div class="section-title"><h2>今日关注</h2></div><div v-if="!data.attention.length" class="mini-empty">尚未关注主题</div><button v-for="topic in data.attention" :key="topic.id" class="row" @click="router.push({path:'/search',query:{q:topic.name}})"><span>{{topic.name}}</span><b>{{topic.count}}</b></button></section>
<section><div class="section-title"><h2>我的收藏</h2></div><div v-if="!data.favorites.length" class="mini-empty">暂无收藏</div><div v-for="item in data.favorites" :key="item.target_id" class="row"><span>{{item.target_type}}</span><small>{{item.target_id.slice(0,8)}}</small></div></section>
<section><div class="section-title"><h2>最近浏览</h2></div><div v-if="!data.recent_views.length" class="mini-empty">暂无浏览记录</div><div v-for="item in data.recent_views" :key="item.target_id" class="row"><span>{{item.title||item.target_type}}</span></div></section>
<section><div class="section-title"><h2>最近报告</h2></div><div class="mini-empty">报告中心尚未产生真实报告</div></section></aside></div></template></main></template>
<style scoped src="@/assets/styles/stage3.css"></style>
