<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { type Schemas, unwrap } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { formatTime } from '@/utils/format'

const props = defineProps<{ declarationId: number }>()
const auth = useAuthStore()
const records = ref<Schemas['ReviewOut'][]>([])
const ACTION: Record<Schemas['ReviewAction'], string> = {
  approve: '通过',
  adjust: '改分',
  reject: '驳回',
}

onMounted(async () => {
  try {
    records.value = unwrap(
      await auth.api.GET('/api/v1/declarations/{declaration_id}/reviews', {
        params: { path: { declaration_id: props.declarationId } },
      }),
    )
  } catch {
    records.value = []
  }
})
</script>

<template>
  <el-timeline v-if="records.length" class="history">
    <el-timeline-item
      v-for="r in records"
      :key="r.id"
      :timestamp="formatTime(r.created_at)"
      placement="top"
    >
      {{ ACTION[r.action] }}：{{ r.score_before ?? '—' }} → {{ r.score_after ?? '—' }}；理由：{{
        r.reason
      }}
    </el-timeline-item>
  </el-timeline>
  <p v-else class="muted">暂无审核记录</p>
</template>

<style scoped>
.history {
  padding: 8px 0 0;
}
</style>
