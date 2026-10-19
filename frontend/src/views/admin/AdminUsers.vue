<script setup lang="ts">
import { ElMessage, ElMessageBox, type UploadRequestOptions } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { type Role, type Schemas, unwrap } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { errorMessage } from '@/utils/errors'
import { fileUpload, saveBlob, toCsv } from '@/utils/files'
import { ROLE_NAMES } from '@/utils/format'
import { useNarrow } from '@/utils/viewport'

type User = Schemas['UserOut']

const narrow = useNarrow()
const auth = useAuthStore()
const result = ref<Schemas['UserImportResult'] | null>(null)
const users = ref<Schemas['UserOut'][]>([])
const filter = reactive({ className: '', role: '' as Role | '' })

async function load(): Promise<void> {
  try {
    const query = {
      ...(filter.className ? { class_name: filter.className } : {}),
      ...(filter.role ? { role: filter.role } : {}),
    }
    users.value = unwrap(await auth.api.GET('/api/v1/users', { params: { query } }))
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

onMounted(load)

async function upload(options: UploadRequestOptions): Promise<void> {
  try {
    result.value = unwrap(await auth.api.POST('/api/v1/users/import', fileUpload(options.file)))
    ElMessage.success(`新建 ${result.value.created.length} 个账号`)
    await load()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

function downloadPasswords(): void {
  if (!result.value) return
  const rows = [
    ['学号', '姓名', '初始密码'],
    ...result.value.created.map((c) => [c.username, c.name, c.initial_password]),
  ]
  saveBlob(toCsv(rows), '初始密码.csv')
}

async function resetPassword(user: Schemas['UserOut']): Promise<void> {
  try {
    await ElMessageBox.confirm(`重置 ${user.name}（${user.username}）的密码？`, '重置密码', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    const reset = unwrap(
      await auth.api.POST('/api/v1/users/{user_id}/reset-password', {
        params: { path: { user_id: user.id } },
      }),
    )
    await ElMessageBox.alert(
      `新的初始密码：${reset.initial_password}（只显示这一次，请转交本人）`,
      '已重置',
    )
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

async function toggleActive(user: Schemas['UserOut']): Promise<void> {
  try {
    unwrap(
      await auth.api.PATCH('/api/v1/users/{user_id}', {
        params: { path: { user_id: user.id } },
        body: { is_active: !user.is_active },
      }),
    )
    await load()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}
</script>

<template>
  <section>
    <h3>批量导入账号</h3>
    <p class="muted">
      上传 .xlsx 或 .csv，表头含“学号”“姓名”，可选“班级”“角色”（学生 / 班级审核员 /
      学院管理员，多个用顿号分隔）。新账号的随机初始密码只显示这一次。
    </p>
    <el-upload :show-file-list="false" :http-request="upload" accept=".xlsx,.csv">
      <el-button type="primary">选择文件并导入</el-button>
    </el-upload>
    <template v-if="result">
      <el-alert
        :title="`新建 ${result.created.length}，更新 ${result.updated}，未变 ${result.unchanged}，错误 ${result.errors.length}`"
        type="success"
        :closable="false"
        class="gap"
      />
      <el-button v-if="result.created.length" size="small" @click="downloadPasswords">
        下载初始密码（CSV）
      </el-button>
      <el-table v-if="result.errors.length" :data="result.errors" size="small" class="gap">
        <el-table-column prop="row" label="行" width="70" />
        <el-table-column prop="message" label="错误" />
      </el-table>
    </template>

    <h3>账号列表</h3>
    <div class="toolbar gap">
      <el-input
        v-model.trim="filter.className"
        placeholder="班级"
        style="width: 140px"
        clearable
        @change="load"
      />
      <el-select v-model="filter.role" style="width: 140px" @change="load">
        <el-option label="全部角色" value="" />
        <el-option v-for="(name, key) in ROLE_NAMES" :key="key" :label="name" :value="key" />
      </el-select>
    </div>
    <el-table :data="users" size="small" max-height="480">
      <el-table-column prop="username" label="学号 / 账号" min-width="110" />
      <el-table-column prop="name" label="姓名" min-width="90" />
      <el-table-column prop="class_name" label="班级" min-width="100" />
      <el-table-column label="角色" min-width="140">
        <template #default="{ row }">
          <el-tag v-for="r in row.roles" :key="r" size="small" class="role">
            {{ ROLE_NAMES[r as Role] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          {{ row.is_active ? (row.must_change_password ? '未改初始密码' : '正常') : '已停用' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" :fixed="narrow ? false : 'right'">
        <template #default="{ row }">
          <el-button link type="primary" @click="resetPassword(row as User)">重置密码</el-button>
          <el-button
            v-if="row.id !== auth.user?.id"
            link
            :type="row.is_active ? 'danger' : 'success'"
            @click="toggleActive(row as User)"
          >
            {{ row.is_active ? '停用' : '启用' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </section>
</template>

<style scoped>
.gap {
  margin: 12px 0;
}

.role {
  margin-right: 4px;
}
</style>
