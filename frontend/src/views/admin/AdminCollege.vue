<script setup lang="ts">
import { ElMessage, type UploadRequestOptions } from 'element-plus'
import { ref } from 'vue'

import { type Schemas, unwrap } from '@/api/client'
import YearSelect from '@/components/YearSelect.vue'
import { useAuthStore } from '@/stores/auth'
import { useYearStore } from '@/stores/year'
import { errorMessage } from '@/utils/errors'
import { fileUpload } from '@/utils/files'

const auth = useAuthStore()
const years = useYearStore()
const result = ref<Schemas['CollegeImportResult'] | null>(null)

async function upload(options: UploadRequestOptions): Promise<void> {
  if (years.selectedId === null) {
    ElMessage.warning('请先选择学年')
    return
  }
  try {
    result.value = unwrap(
      await auth.api.POST('/api/v1/years/{year_id}/college-data/import', {
        params: { path: { year_id: years.selectedId } },
        ...fileUpload(options.file),
      }),
    )
    ElMessage.success(`导入完成：变化 ${result.value.changed} 项`)
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}
</script>

<template>
  <section>
    <h3>导入学院成绩表</h3>
    <p class="muted">
      表头需含“学号”；其余列按关键词识别：学分绩点、第二课堂、公益劳动、体测、宿舍、政治素养、品德修养、纪律观念、诚信评价、综合素质评价总分。思想品德四项的单元格有多个数字时视为全班评议名单。每一项变化都记入审计日志。
    </p>
    <div class="toolbar">
      <YearSelect />
      <el-upload :show-file-list="false" :http-request="upload" accept=".xlsx,.csv">
        <el-button type="primary">选择文件并导入</el-button>
      </el-upload>
    </div>
    <template v-if="result">
      <el-descriptions :column="2" border class="gap">
        <el-descriptions-item label="数据行">{{ result.rows }}</el-descriptions-item>
        <el-descriptions-item label="批次">#{{ result.batch_id }}</el-descriptions-item>
        <el-descriptions-item label="有变化">{{ result.changed }}</el-descriptions-item>
        <el-descriptions-item label="无变化">{{ result.unchanged }}</el-descriptions-item>
      </el-descriptions>
      <p>
        识别的列：
        <el-tag v-for="(field, header) in result.mapped_columns" :key="header" class="tag">
          {{ header }} → {{ field }}
        </el-tag>
      </p>
      <p v-if="result.ignored_columns.length">
        忽略的列：
        <el-tag v-for="h in result.ignored_columns" :key="h" type="info" class="tag">{{
          h
        }}</el-tag>
      </p>
      <el-table v-if="result.errors.length" :data="result.errors" size="small">
        <el-table-column prop="row" label="行" width="70" />
        <el-table-column prop="message" label="问题" />
      </el-table>
    </template>
  </section>
</template>

<style scoped>
.gap {
  margin: 12px 0;
}

.tag {
  margin: 0 4px 4px 0;
}
</style>
