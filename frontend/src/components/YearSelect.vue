<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted } from 'vue'

import { useYearStore } from '@/stores/year'
import { errorMessage } from '@/utils/errors'
import { YEAR_STATUS } from '@/utils/format'

const store = useYearStore()

onMounted(async () => {
  if (store.years.length === 0) {
    try {
      await store.load()
    } catch (e) {
      ElMessage.error(errorMessage(e))
    }
  }
})
</script>

<template>
  <el-select
    :model-value="store.selectedId"
    placeholder="选择学年"
    style="width: 190px"
    data-testid="year-select"
    @update:model-value="(id: number) => store.select(id)"
  >
    <el-option
      v-for="year in store.years"
      :key="year.id"
      :value="year.id"
      :label="`${year.name}（${YEAR_STATUS[year.status]}）`"
    />
  </el-select>
</template>
