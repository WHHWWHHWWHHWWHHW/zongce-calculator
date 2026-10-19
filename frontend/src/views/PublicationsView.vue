<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'

import { type Schemas, unwrap } from '@/api/client'
import RankTable from '@/components/RankTable.vue'
import { useAuthStore } from '@/stores/auth'
import { errorMessage } from '@/utils/errors'
import { APPEAL_STATUS, formatTime } from '@/utils/format'

const auth = useAuthStore()
const publications = ref<Schemas['PublicationOut'][]>([])
const appeals = ref<Schemas['AppealOut'][]>([])
const loading = ref(false)
const appealFor = ref<Schemas['PublicationOut'] | null>(null)
const appealText = ref('')
const busy = ref(false)

async function load(): Promise<void> {
  loading.value = true
  try {
    publications.value = unwrap(await auth.api.GET('/api/v1/publications'))
    appeals.value = unwrap(await auth.api.GET('/api/v1/appeals'))
  } catch (e) {
    ElMessage.error(errorMessage(e))
  } finally {
    loading.value = false
  }
}

onMounted(load)

const canAppeal = (p: Schemas['PublicationOut']) =>
  p.is_open && auth.hasRole('student') && auth.user?.class_name === p.class_name

async function submitAppeal(): Promise<void> {
  if (!appealFor.value || !appealText.value.trim()) return
  busy.value = true
  try {
    unwrap(
      await auth.api.POST('/api/v1/publications/{publication_id}/appeals', {
        params: { path: { publication_id: appealFor.value.id } },
        body: { content: appealText.value },
      }),
    )
    ElMessage.success('已提交异议，请等待学院答复')
    appealFor.value = null
    appealText.value = ''
    await load()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div v-loading="loading" class="page">
    <div class="page-header"><h2>成绩公示</h2></div>
    <el-empty v-if="!publications.length && !loading" description="暂无公示" />
    <el-card v-for="p in publications" :key="p.id" shadow="never" class="block">
      <template #header>
        <div class="toolbar">
          <strong>{{ p.title }}</strong>
          <el-tag :type="p.is_open ? 'success' : 'info'">{{
            p.is_open ? '公示中' : '已结束'
          }}</el-tag>
          <span class="muted">{{ formatTime(p.starts_at) }} 至 {{ formatTime(p.ends_at) }}</span>
          <el-button v-if="canAppeal(p)" size="small" type="warning" @click="appealFor = p">
            提出异议
          </el-button>
        </div>
      </template>
      <RankTable :rows="p.rows" />
    </el-card>

    <template v-if="appeals.length">
      <h3>我的异议</h3>
      <el-table :data="appeals" size="small">
        <el-table-column prop="content" label="内容" min-width="200" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="APPEAL_STATUS[row.status as Schemas['AppealStatus']].type as never">
              {{ APPEAL_STATUS[row.status as Schemas['AppealStatus']].label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="response" label="学院答复" min-width="200" />
        <el-table-column label="提交时间" width="150">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </template>

    <el-dialog
      :model-value="appealFor !== null"
      title="提出异议"
      width="520px"
      @update:model-value="appealFor = null"
    >
      <p class="muted">请写明对哪一项成绩有异议、理由，以及可以核实的材料。</p>
      <el-input v-model="appealText" type="textarea" :rows="5" maxlength="2000" show-word-limit />
      <template #footer>
        <el-button @click="appealFor = null">取消</el-button>
        <el-button type="primary" :loading="busy" @click="submitAppeal">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.block {
  margin-bottom: 16px;
}
</style>
