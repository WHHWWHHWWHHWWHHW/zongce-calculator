<script setup lang="ts">
import { ElMessage, ElMessageBox, type UploadRequestOptions } from 'element-plus'

import { type Schemas, unwrap } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import type { Declaration } from '@/utils/catalog'
import { errorMessage } from '@/utils/errors'
import { fileUpload, saveBlob } from '@/utils/files'
import { formatTime } from '@/utils/format'

type Evidence = Schemas['EvidenceOut']

const props = defineProps<{ declaration: Declaration | null; editable: boolean }>()
const visible = defineModel<boolean>({ required: true })
const emit = defineEmits<{ changed: [] }>()
const auth = useAuthStore()

async function download(item: Schemas['EvidenceOut']): Promise<void> {
  try {
    const blob = unwrap(
      await auth.api.GET('/api/v1/evidence/{evidence_id}', {
        params: { path: { evidence_id: item.id } },
        parseAs: 'blob',
      }),
    )
    saveBlob(blob as Blob, item.original_name)
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

async function upload(options: UploadRequestOptions): Promise<void> {
  if (!props.declaration) return
  try {
    unwrap(
      await auth.api.POST('/api/v1/declarations/{declaration_id}/evidence', {
        params: { path: { declaration_id: props.declaration.id } },
        ...fileUpload(options.file),
      }),
    )
    ElMessage.success(`已上传 ${options.file.name}`)
    emit('changed')
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

async function remove(item: Schemas['EvidenceOut']): Promise<void> {
  try {
    await ElMessageBox.confirm(`删除“${item.original_name}”？`, '删除材料', { type: 'warning' })
  } catch {
    return
  }
  try {
    const result = await auth.api.DELETE('/api/v1/evidence/{evidence_id}', {
      params: { path: { evidence_id: item.id } },
    })
    if (!result.response.ok) unwrap(result)
    emit('changed')
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}
</script>

<template>
  <el-dialog v-model="visible" title="证明材料" width="600px">
    <p class="muted">支持 PDF、PNG、JPEG；以文件内容识别类型。</p>
    <el-table :data="declaration?.evidence ?? []" empty-text="还没有上传材料" size="small">
      <el-table-column prop="original_name" label="文件" min-width="160" />
      <el-table-column label="上传时间" width="150">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="download(row as Evidence)">下载</el-button>
          <el-button v-if="editable" link type="danger" @click="remove(row as Evidence)"
            >删除</el-button
          >
        </template>
      </el-table-column>
    </el-table>
    <el-upload
      v-if="editable"
      :show-file-list="false"
      :http-request="upload"
      accept=".pdf,.png,.jpg,.jpeg"
      multiple
      class="uploader"
    >
      <el-button type="primary" data-testid="evidence-upload">上传材料</el-button>
    </el-upload>
  </el-dialog>
</template>

<style scoped>
.uploader {
  margin-top: 12px;
}
</style>
