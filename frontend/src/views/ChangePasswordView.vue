<script setup lang="ts">
// 占位实现：组件库选定后替换为正式页面
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { ApiError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const oldPassword = ref('')
const newPassword = ref('')
const confirm = ref('')
const error = ref('')

async function submit(): Promise<void> {
  error.value = ''
  if (newPassword.value !== confirm.value) {
    error.value = '两次输入的新密码不一致'
    return
  }
  try {
    await auth.changePassword(oldPassword.value, newPassword.value)
    await router.replace({ name: 'login' })
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : '修改失败，请稍后重试'
  }
}
</script>

<template>
  <main>
    <h1>修改密码</h1>
    <p v-if="auth.mustChangePassword">首次登录请先修改初始密码。</p>
    <form @submit.prevent="submit">
      <label>原密码 <input v-model="oldPassword" type="password" required /></label>
      <label
        >新密码（至少 8 位）<input v-model="newPassword" type="password" minlength="8" required
      /></label>
      <label>再次输入 <input v-model="confirm" type="password" minlength="8" required /></label>
      <p v-if="error" role="alert">{{ error }}</p>
      <button type="submit">确认修改</button>
    </form>
  </main>
</template>
