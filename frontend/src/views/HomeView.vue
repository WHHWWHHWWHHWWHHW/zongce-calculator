<script setup lang="ts">
import { useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

async function logout(): Promise<void> {
  auth.logout()
  await router.replace({ name: 'login' })
}
</script>

<template>
  <main>
    <h1>你好，{{ auth.user?.name }}</h1>
    <p>正式页面将在组件库选定后实现。</p>
    <button type="button" @click="logout">退出登录</button>
  </main>
</template>
