<script setup lang="ts">
/** 计分明细表：每条规则的原始值、得分、是否触发上下限。 */
export interface ScoreItem {
  rule_id: string
  score: string
  raw: string | null
  /** 4 位小数的展示值（后端提供；旧的核算结果没有时退回精确值） */
  score_display?: string
  raw_display?: string | null
  capped: boolean
  floored: boolean
  peer_count?: number | null
  peer_trimmed_per_side?: number | null
}

defineProps<{ items: ScoreItem[]; names: Record<string, string> }>()
</script>

<template>
  <el-table :data="items" size="small" class="items">
    <el-table-column label="项目" min-width="140">
      <template #default="{ row }">{{ names[row.rule_id] ?? row.rule_id }}</template>
    </el-table-column>
    <el-table-column label="原始值" min-width="110" class-name="score">
      <template #default="{ row }">{{ row.raw_display ?? row.raw ?? '—' }}</template>
    </el-table-column>
    <el-table-column label="得分" min-width="110" class-name="score">
      <template #default="{ row }">{{ row.score_display ?? row.score }}</template>
    </el-table-column>
    <el-table-column label="说明" min-width="150">
      <template #default="{ row }">
        <el-tag v-if="row.capped" type="warning" size="small">已封顶</el-tag>
        <el-tag v-if="row.floored" type="info" size="small">已取下限</el-tag>
        <span v-if="row.peer_count" class="muted">
          评议 {{ row.peer_count }} 人，两端各去掉 {{ row.peer_trimmed_per_side }} 人
        </span>
      </template>
    </el-table-column>
  </el-table>
</template>
