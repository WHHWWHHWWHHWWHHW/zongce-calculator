<script setup lang="ts">
// 占位实现：组件库选定后替换为正式页面，交互逻辑（store、错误处理）保持不变
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const username = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit(): Promise<void> {
  busy.value = true
  error.value = ''
  try {
    await auth.login(username.value, password.value)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.replace(auth.mustChangePassword ? { name: 'change-password' } : redirect)
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : '登录失败，请稍后重试'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <main>
    <h1>综测智能核算平台</h1>
    <form @submit.prevent="submit">
      <label>学号 / 账号 <input v-model.trim="username" autocomplete="username" required /></label>
      <label>
        密码 <input v-model="password" type="password" autocomplete="current-password" required />
      </label>
      <p v-if="error" role="alert">{{ error }}</p>
      <button type="submit" :disabled="busy">登录</button>
    </form>
  </main>
</template>
