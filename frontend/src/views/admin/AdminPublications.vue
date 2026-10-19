<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { type Schemas, unwrap } from '@/api/client'
import YearSelect from '@/components/YearSelect.vue'
import { useAuthStore } from '@/stores/auth'
import { useYearStore } from '@/stores/year'
import { errorMessage } from '@/utils/errors'
import { APPEAL_STATUS, formatTime } from '@/utils/format'

const auth = useAuthStore()
const years = useYearStore()
const form = reactive({ className: '', days: 3, title: '' })
const publications = ref<Schemas['PublicationOut'][]>([])
const appeals = ref<Schemas['AppealOut'][]>([])

async function load(): Promise<void> {
  try {
    publications.value = unwrap(await auth.api.GET('/api/v1/publications'))
    appeals.value = unwrap(await auth.api.GET('/api/v1/appeals'))
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

onMounted(load)

async function publish(): Promise<void> {
  if (years.selectedId === null || !form.className) {
    ElMessage.warning('请选择学年并填写班级')
    return
  }
  try {
    unwrap(
      await auth.api.POST('/api/v1/years/{year_id}/publications', {
        params: { path: { year_id: years.selectedId } },
        body: { class_name: form.className, days: form.days, title: form.title || null },
      }),
    )
    ElMessage.success('已发布公示')
    await load()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

async function close(p: Schemas['PublicationOut']): Promise<void> {
  try {
    unwrap(
      await auth.api.POST('/api/v1/publications/{publication_id}/close', {
        params: { path: { publication_id: p.id } },
      }),
    )
    await load()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

async function resolve(
  appeal: Schemas['AppealOut'],
  status: 'accepted' | 'rejected',
): Promise<void> {
  let response: string
  try {
    const answer = await ElMessageBox.prompt(
      `${appeal.student_name}：${appeal.content}`,
      status === 'accepted' ? '采纳异议' : '不予采纳',
      { inputPlaceholder: '答复内容（必填）', inputValidator: (v) => !!v?.trim() || '请填写答复' },
    )
    response = answer.value
  } catch {
    return
  }
  try {
    unwrap(
      await auth.api.POST('/api/v1/appeals/{appeal_id}/resolve', {
        params: { path: { appeal_id: appeal.id } },
        body: { status, response },
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
    <h3>发布班级公示</h3>
    <p class="muted">以当前核算结果为快照；办法正文第十四条规定班级公示 3 天。</p>
    <div class="toolbar">
      <YearSelect />
      <el-input v-model.trim="form.className" placeholder="班级" style="width: 140px" />
      <el-input-number v-model="form.days" :min="1" :max="30" />
      <span class="muted">天</span>
      <el-input v-model="form.title" placeholder="标题（可选）" style="width: 200px" />
      <el-button type="primary" @click="publish">发布</el-button>
    </div>

    <h3>公示列表</h3>
    <el-table :data="publications" size="small">
      <el-table-column prop="title" label="标题" min-width="220" />
      <el-table-column prop="class_name" label="班级" min-width="100" />
      <el-table-column label="期限" min-width="200">
        <template #default="{ row }">
          {{ formatTime(row.starts_at) }} 至 {{ formatTime(row.ends_at) }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">{{ row.is_open ? '公示中' : '已结束' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button
            v-if="row.is_open"
            link
            type="danger"
            @click="close(row as Schemas['PublicationOut'])"
            >提前结束</el-button
          >
        </template>
      </el-table-column>
    </el-table>

    <h3>异议</h3>
    <el-table :data="appeals" size="small" empty-text="暂无异议">
      <el-table-column label="学生" min-width="120">
        <template #default="{ row }">
          {{ row.student_name }}<span class="muted"> {{ row.student_username }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="class_name" label="班级" min-width="90" />
      <el-table-column prop="content" label="内容" min-width="200" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="APPEAL_STATUS[row.status as Schemas['AppealStatus']].type as never">
            {{ APPEAL_STATUS[row.status as Schemas['AppealStatus']].label }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="response" label="答复" min-width="160" />
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <template v-if="row.status === 'pending'">
            <el-button link type="success" @click="resolve(row as Schemas['AppealOut'], 'accepted')"
              >采纳</el-button
            >
            <el-button link type="info" @click="resolve(row as Schemas['AppealOut'], 'rejected')"
              >不予采纳</el-button
            >
          </template>
        </template>
      </el-table-column>
    </el-table>
  </section>
</template>
