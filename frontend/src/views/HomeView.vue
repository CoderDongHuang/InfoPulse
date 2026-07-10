<script setup lang="ts">
/**
 * InfoPulse — Home Page
 * ======================
 * Hero section + three feature cards + CTA.
 */
import { useRouter } from 'vue-router'

const router = useRouter()

const features = [
  {
    icon: '🛡️',
    title: '避坑雷达',
    description: '多平台水军识别，买到真正好货',
    route: '/anti-scam',
    color: '#409EFF',
  },
  {
    icon: '🔥',
    title: '互联网嘴替',
    description: 'AI 帮你把心里话，说成爆款',
    route: '/mouthpiece',
    color: '#6B46C1',
  },
  {
    icon: '🕐',
    title: '吃瓜时间线',
    description: '碎片信息结构化，吃瓜吃明白',
    route: '/timeline',
    color: '#67c23a',
  },
]

function goTo(route: string) {
  router.push(route)
}
</script>

<template>
  <div class="home-page">
    <!-- Hero -->
    <section class="hero">
      <h1 class="hero-title">穿透信息迷雾，洞察真实情绪</h1>
      <p class="hero-subtitle">
        基于 AI 大模型的舆情洞察平台 · 实时数据抓取 · 智能分析
      </p>
      <el-button type="primary" size="large" round @click="goTo('/anti-scam')">
        立即体验 →
      </el-button>
    </section>

    <!-- Feature Cards -->
    <section class="features">
      <div
        v-for="f in features"
        :key="f.title"
        class="feature-card glass-card"
        @click="goTo(f.route)"
      >
        <div class="feature-icon" :style="{ background: f.color }">
          {{ f.icon }}
        </div>
        <h3 class="feature-title">{{ f.title }}</h3>
        <p class="feature-desc">{{ f.description }}</p>
        <span class="feature-link">立即使用 →</span>
      </div>
    </section>

    <!-- Stats -->
    <section class="stats">
      <div class="stat-item">
        <span class="stat-number">3</span>
        <span class="stat-label">核心功能</span>
      </div>
      <div class="stat-item">
        <span class="stat-number">3+</span>
        <span class="stat-label">支持平台</span>
      </div>
      <div class="stat-item">
        <span class="stat-number">24h</span>
        <span class="stat-label">持续运行</span>
      </div>
    </section>
  </div>
</template>

<style scoped>
.home-page {
  padding-bottom: 60px;
}

/* --- Hero --- */
.hero {
  text-align: center;
  padding: 80px 20px 60px;
  background: linear-gradient(180deg, rgba(64, 158, 255, 0.05), transparent);
}

.hero-title {
  font-size: 42px;
  font-weight: 800;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 16px;
}

.hero-subtitle {
  font-size: 16px;
  color: var(--text-secondary);
  margin-bottom: 32px;
  line-height: 1.8;
}

/* --- Features --- */
.features {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
  max-width: 1000px;
  margin: 0 auto;
  padding: 0 24px;
}

.feature-card {
  padding: 32px 24px;
  text-align: center;
  cursor: pointer;
}

.feature-icon {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  margin: 0 auto 16px;
  color: white;
}

.feature-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--text-primary);
}

.feature-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 12px;
}

.feature-link {
  font-size: 13px;
  color: var(--color-primary);
  font-weight: 500;
}

/* --- Stats --- */
.stats {
  display: flex;
  justify-content: center;
  gap: 60px;
  margin-top: 60px;
  padding: 30px 0;
  border-top: 1px solid var(--border-color);
}

.stat-item {
  text-align: center;
}

.stat-number {
  display: block;
  font-size: 28px;
  font-weight: 700;
  color: var(--color-primary);
}

.stat-label {
  font-size: 13px;
  color: var(--text-secondary);
}

/* --- Responsive --- */
@media (max-width: 768px) {
  .hero-title {
    font-size: 28px;
  }

  .features {
    grid-template-columns: 1fr;
  }

  .stats {
    gap: 30px;
  }
}
</style>
