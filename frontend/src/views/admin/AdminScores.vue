<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { reactive, ref, watch } from 'vue'

import { type Schemas, unwrap } from '@/api/client'
import RankTable from '@/components/RankTable.vue'
import YearSelect from '@/components/YearSelect.vue'
import { useAuthStore } from '@/stores/auth'
import { useYearStore } from '@/stores/year'
import { errorMessage } from '@/utils/errors'
import { filenameFrom, saveBlob } from '@/utils/files'

const auth = useAuthStore()
const years = useYearStore()
const form = reactive({ className: '', reason: '核算' })
const rows = ref<Schemas['RankRow'][]>([])
const busy = ref(false)

async function loadRankings(): Promise<void> {
  if (years.selectedId === null) return
  try {
    rows.value = unwrap(
      await auth.api.GET('/api/v1/years/{year_id}/rankings', {
        params: {
          path: { year_id: years.selectedId },
          query: form.className ? { class_name: form.className } : {},
        },
      }),
    )
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

watch(() => years.selectedId, loadRankings, { immediate: true })

async function compute(): Promise<void> {
  if (years.selectedId === null) return
  busy.value = true
  try {
    const result = unwrap(
      await auth.api.POST('/api/v1/years/{year_id}/scores/compute', {
        params: { path: { year_id: years.selectedId } },
        body: { class_name: form.className || null, reason: form.reason || '核算' },
      }),
    )
    ElMessage.success(`已核算 ${result.computed} 人，其中 ${result.changed} 人综测成绩有变化`)
    await loadRankings()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  } finally {
    busy.value = false
  }
}

async function exportExcel(): Promise<void> {
  if (years.selectedId === null) return
  try {
    const result = await auth.api.GET('/api/v1/years/{year_id}/rankings/export', {
      params: {
        path: { year_id: years.selectedId },
        query: form.className ? { class_name: form.className } : {},
      },
      parseAs: 'blob',
    })
    const blob = unwrap(result) as Blob
    saveBlob(blob, filenameFrom(result.response, '综测排名.xlsx'))
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}
</script>

<template>
  <section>
    <h3>核算</h3>
    <p class="muted">
      用学院成绩表数据和已通过的能力分申报计算综测成绩；结果有变化的写入审计日志。
    </p>
    <div class="toolbar">
      <YearSelect />
      <el-input
        v-model.trim="form.className"
        placeholder="班级（留空为全部）"
        style="width: 160px"
        clearable
        @change="loadRankings"
      />
      <el-input v-model="form.reason" placeholder="核算理由" style="width: 160px" />
      <el-button type="primary" :loading="busy" data-testid="compute" @click="compute">
        核算
      </el-button>
      <el-button data-testid="export" @click="exportExcel">导出 Excel</el-button>
    </div>
    <h3>班级排名</h3>
    <RankTable :rows="rows" show-class />
  </section>
</template>
