<script setup lang="ts">
import type { Schemas } from '@/api/client'
import { scoreText } from '@/utils/format'

defineProps<{ rows: Schemas['RankRow'][]; showClass?: boolean }>()
</script>

<template>
  <el-table :data="rows" size="small" empty-text="暂无数据">
    <el-table-column v-if="showClass" prop="class_name" label="班级" min-width="100" />
    <el-table-column prop="rank" label="排名" width="64" />
    <el-table-column prop="username" label="学号" min-width="110" />
    <el-table-column prop="name" label="姓名" min-width="90" />
    <el-table-column prop="final_score" label="综测成绩" min-width="96" class-name="score" />
    <el-table-column prop="gpa" label="GPA" min-width="80" class-name="score" />
    <el-table-column label="思想品德" min-width="90" class-name="score">
      <template #default="{ row }">{{ scoreText(row.moral_total) }}</template>
    </el-table-column>
    <el-table-column label="综合能力" min-width="90" class-name="score">
      <template #default="{ row }">{{ scoreText(row.competence_total) }}</template>
    </el-table-column>
    <el-table-column prop="quality_total" label="综合素质" min-width="90" class-name="score" />
  </el-table>
</template>
