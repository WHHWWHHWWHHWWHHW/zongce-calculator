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
  <div class="login-page">
    <header class="login-title">
      <h1>综测智能核算平台</h1>
      <p>信息科学与工程学院 · 综合测评申报与审核</p>
    </header>

    <section class="login-box" aria-labelledby="login-heading">
      <h2 id="login-heading" class="login-heading">账号登录</h2>
      <form class="login-form" @submit.prevent="submit">
        <el-input
          v-model.trim="form.username"
          autocomplete="username"
          placeholder="学号 / 账号"
          aria-label="学号或账号"
          size="large"
          data-testid="login-username"
        />
        <el-input
          v-model="form.password"
          type="password"
          show-password
          autocomplete="current-password"
          placeholder="密码"
          aria-label="密码"
          size="large"
          data-testid="login-password"
        />
        <p v-if="error" class="login-error" role="alert">{{ error }}</p>
        <el-button
          type="primary"
          native-type="submit"
          :loading="busy"
          class="login-button"
          data-testid="login-submit"
        >
          登录
        </el-button>
      </form>
      <div class="login-notes">
        <p class="note">
          学生账号为学号，初始密码由学院统一发放，首次登录后需要修改密码。忘记密码请联系班级审核员或学院管理员重置。
        </p>
        <p class="note note-muted">同一账号连续输错多次会暂时停止登录，请稍候再试。</p>
      </div>
    </section>

    <footer class="login-footer">2026 年大学生创新训练计划项目 · 综测智能核算平台</footer>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 56px 16px 24px;
  /* 晴空的蓝到浅蓝，两团淡云；不用照片和校徽 */
  background:
    radial-gradient(ellipse 38% 16% at 18% 22%, rgb(255 255 255 / 55%), transparent 70%),
    radial-gradient(ellipse 30% 12% at 82% 34%, rgb(255 255 255 / 45%), transparent 70%),
    linear-gradient(180deg, #3f8ddb 0%, #8ec0ef 42%, #dceaf8 78%, #eef4fa 100%);
}

.login-title {
  text-align: center;
  color: #fff;
  margin-bottom: 24px;
  text-shadow: 0 1px 2px rgb(0 40 100 / 25%);
}

.login-title h1 {
  margin: 0;
  font-size: 28px;
  font-weight: 600;
  letter-spacing: 2px;
}

.login-title p {
  margin: 6px 0 0;
  font-size: 14px;
  opacity: 0.92;
}

.login-box {
  width: 100%;
  max-width: 420px;
  background: rgb(255 255 255 / 94%);
  border: 1px solid #dedede;
}

.login-heading {
  margin: 0;
  height: 48px;
  line-height: 48px;
  text-align: center;
  font-size: 16px;
  font-weight: 400;
  color: #333;
  border-bottom: 1px solid #dedede;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 24px 28px 8px;
  --el-input-border-radius: 0;
  --el-input-border-color: #dedede;
}

.login-error {
  margin: -4px 0 0;
  color: var(--el-color-danger);
  font-size: 13px;
}

.login-button {
  width: 100%;
  height: 40px;
  border-radius: 6px;
  font-size: 16px;
  letter-spacing: 2px;
}

.login-notes {
  padding: 8px 28px 20px;
}

.note {
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.7;
  color: var(--el-color-primary);
}

.note-muted {
  color: #888;
}

.login-footer {
  margin-top: auto;
  padding-top: 32px;
  font-size: 12px;
  color: #6b7f96;
}

@media (max-width: 600px) {
  .login-page {
    padding-top: 40px;
  }

  .login-title h1 {
    font-size: 24px;
  }

  .login-form,
  .login-notes {
    padding-left: 18px;
    padding-right: 18px;
  }
}
</style>
