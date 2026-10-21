<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { errorMessage } from '@/utils/errors'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const form = reactive({ username: '', password: '' })
const error = ref('')
const busy = ref(false)

async function submit(): Promise<void> {
  if (!form.username || !form.password) {
    error.value = '请输入学号和密码'
    return
  }
  busy.value = true
  error.value = ''
  try {
    await auth.login(form.username, form.password)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.replace(auth.mustChangePassword ? { name: 'change-password' } : redirect)
  } catch (e) {
    error.value = errorMessage(e, '登录失败，请稍后重试')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="login-wrap">
    <el-card class="login-card" shadow="never">
      <h1>综测智能核算平台</h1>
      <p class="muted">济南大学信息科学与工程学院 · 综合测评</p>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="学号 / 账号">
          <el-input
            v-model.trim="form.username"
            autocomplete="username"
            placeholder="请输入学号"
            data-testid="login-username"
          />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            autocomplete="current-password"
            placeholder="请输入密码"
            data-testid="login-password"
          />
        </el-form-item>
        <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
        <el-button
          type="primary"
          native-type="submit"
          :loading="busy"
          class="login-button"
          data-testid="login-submit"
        >
          登录
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.login-card {
  width: 100%;
  max-width: 380px;
}

h1 {
  margin: 0 0 4px;
  font-size: 22px;
}

.login-button {
  width: 100%;
  margin-top: 16px;
}
</style>
