<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import LoginCard from '@/components/auth/LoginCard.vue'

const router = useRouter()
const route = useRoute()
const onSuccess = () => router.push((route.query.redirect as string) || '/')
</script>

<template>
  <main class="auth-page">
    <section class="news-panel">
      <img src="@/assets/images/auth-newsroom.jpg" alt="报纸与公开信息" />
      <div class="news-overlay"></div>
      <div class="masthead">
        <span class="signal-mark"><i></i><i></i><i></i></span>
        <strong>InfoPulse</strong>
      </div>
      <div class="edition-copy">
        <p>PUBLIC OPINION DESK · 2026</p>
        <h1>别被热度带着走，<br>先看清信息从哪里来。</h1>
        <div class="edition-meta">
          <span>微博</span><span>B站</span><span>百度贴吧</span><span>DeepSeek</span>
        </div>
      </div>
      <div class="signal-board"><span><i></i>微博公开热榜</span><span><i></i>B站公开讨论</span><span><i></i>贴吧兴趣社区</span></div>
      <div class="live-strip"><span>LIVE</span> 公开讨论采集与 AI 结构化分析</div>
    </section>

    <section class="auth-panel">
      <button class="back-home" type="button" @click="router.push('/')"><el-icon><ArrowLeft /></el-icon>返回今日工作台</button>
      <LoginCard @success="onSuccess" />
      <p class="privacy-note">登录凭证仅保存在当前浏览器会话中。</p>
    </section>
  </main>
</template>

<style scoped>
.auth-page { min-height: 100vh; display: grid; grid-template-columns: minmax(0, 1.12fr) minmax(440px, .88fr); background: #f4f7f5; }
.news-panel { position: relative; min-height: 100vh; overflow: hidden; color: white; }
.news-panel > img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; filter: saturate(.58) contrast(1.08); transform: scale(1.015); }
.news-overlay { position: absolute; inset: 0; background: linear-gradient(90deg, rgba(8,25,21,.92), rgba(8,25,21,.56) 66%, rgba(8,25,21,.28)); }
.masthead { position: absolute; top: 42px; left: 48px; display: flex; align-items: center; gap: 12px; font-size: 18px; }
.signal-mark { width: 32px; height: 32px; display: flex; align-items: flex-end; gap: 4px; padding: 6px; border: 1px solid rgba(255,255,255,.42); }
.signal-mark i { width: 4px; background: white; }
.signal-mark i:nth-child(1) { height: 7px; }.signal-mark i:nth-child(2) { height: 18px; background: #66d3c4; }.signal-mark i:nth-child(3) { height: 12px; background: #ef746c; }
.edition-copy { position: absolute; left: 8%; bottom: 18%; max-width: 720px; }
.edition-copy > p { font: 700 11px/1.4 "Cascadia Code", monospace; color: #82d4c8; letter-spacing: .12em; }
.edition-copy h1 { margin: 18px 0 30px; max-width: 780px; font: 600 clamp(40px, 4.6vw, 66px)/1.12 Georgia, "Songti SC", serif; letter-spacing: 0; }
.edition-meta { display: flex; flex-wrap: wrap; gap: 10px; }
.edition-meta span { padding: 8px 12px; border: 1px solid rgba(255,255,255,.32); background: rgba(7,16,29,.26); font-size: 12px; backdrop-filter: blur(8px); }
.signal-board { position: absolute; left: 8%; bottom: 11%; display: flex; gap: 22px; color: #b8d0c9; font-size: 10px; }.signal-board span { display: flex; align-items: center; gap: 7px; }.signal-board i { width: 6px; height: 6px; border-radius: 50%; background: #55c5b7; box-shadow: 0 0 10px rgba(85,197,183,.8); }
.live-strip { position: absolute; left: 0; right: 0; bottom: 0; padding: 14px 48px; background: rgba(8,25,21,.84); border-top: 1px solid rgba(255,255,255,.15); font-size: 11px; }
.live-strip span { margin-right: 12px; padding: 3px 7px; background: #e5484d; font-weight: 900; }
.auth-panel { position: relative; display: grid; place-items: center; padding: 80px 56px; background-image: linear-gradient(rgba(24,52,45,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(24,52,45,.035) 1px, transparent 1px); background-size: 28px 28px; }
.back-home { position: absolute; left: 34px; top: 32px; border: 0; background: transparent; color: #667085; display: flex; align-items: center; gap: 6px; cursor: pointer; }
.privacy-note { position: absolute; bottom: 26px; margin: 0; color: #98a2b3; font-size: 11px; }
@media (max-width: 920px) { .auth-page { grid-template-columns: 1fr; } .news-panel { min-height: 320px; } .edition-copy { bottom: 84px; } .edition-copy h1 { font-size: 34px; margin: 10px 0 16px; } .signal-board { left: 8%; bottom: 50px; }.auth-panel { min-height: 600px; padding: 82px 24px; } }
@media (max-width: 520px) { .news-panel { min-height: 285px; } .masthead { left: 24px; top: 24px; } .edition-copy { left: 24px; right: 24px; bottom: 58px; } .edition-copy h1 { font-size: 29px; } .edition-meta, .signal-board { display: none; }.live-strip { padding: 10px 24px; } .auth-panel { min-height: 590px; }.back-home { left: 22px; top: 24px; } }
</style>
