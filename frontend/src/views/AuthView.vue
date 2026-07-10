<script setup lang="ts">
/**
 * InfoPulse — Auth Page
 * ======================
 * Full-screen centered login/register card.
 * No header/footer for immersion.
 */
import { useRouter, useRoute } from 'vue-router'
import LoginCard from '@/components/auth/LoginCard.vue'

const router = useRouter()
const route = useRoute()

function onSuccess() {
  const redirect = (route.query.redirect as string) || '/'
  router.push(redirect)
}
</script>

<template>
  <div class="auth-page">
    <LoginCard @success="onSuccess" />
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(64, 158, 255, 0.08), rgba(107, 70, 193, 0.08));
}
</style>
