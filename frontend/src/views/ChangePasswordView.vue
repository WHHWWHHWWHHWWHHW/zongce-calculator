<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { errorMessage } from '@/utils/errors'

const auth = useAuthStore()
const router = useRouter()
const form = reactive({ old: '', next: '', confirm: '' })
const error = ref('')
const busy = ref(false)

async function submit(): Promise<void> {
  error.value = ''
  if (form.next.length < 8) {
    error.value = '新密码至少 8 位'
    return
  }
  if (form.next !== form.confirm) {
    error.value = '两次输入的新密码不一致'
    return
  }
  busy.value = true
  try {
    await auth.changePassword(form.old, form.next)
    ElMessage.success('密码已修改，请用新密码重新登录')
    await router.replace({ name: 'login' })
  } catch (e) {
    error.value = errorMessage(e, '修改失败，请稍后重试')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="page narrow">
    <div class="page-header"><h2>修改密码</h2></div>
    <el-alert
      v-if="auth.mustChangePassword"
      title="首次登录请先修改初始密码，修改后才能使用其他功能。"
      type="warning"
      :closable="false"
      show-icon
    />
    <el-form label-position="top" class="form" @submit.prevent="submit">
      <el-form-item label="原密码">
        <el-input v-model="form.old" type="password" show-password data-testid="pw-old" />
      </el-form-item>
      <el-form-item label="新密码（至少 8 位，不能与学号相同）">
        <el-input v-model="form.next" type="password" show-password data-testid="pw-new" />
      </el-form-item>
      <el-form-item label="再次输入新密码">
        <el-input v-model="form.confirm" type="password" show-password data-testid="pw-confirm" />
      </el-form-item>
      <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
      <el-button type="primary" native-type="submit" :loading="busy" data-testid="pw-submit">
        确认修改
      </el-button>
    </el-form>
  </div>
</template>

<style scoped>
.narrow {
  max-width: 480px;
}

.form {
  margin-top: 16px;
}
</style>
