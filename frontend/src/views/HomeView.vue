<script setup lang="ts">
import { computed } from 'vue'

import { appRoutes } from '@/router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

const DESCRIPTIONS: Record<string, string> = {
  'my-declarations': '申报能力分（评优、社会工作、竞赛等），上传证明材料并提交审核。',
  'my-scores': '查看学院核算后的综测成绩和各项明细。',
  preview: '输入各项成绩，即时预估综测成绩（由后端按规则计算）。',
  publications: '查看本班成绩公示，公示期内可以提出异议。',
  review: '审核本班同学的能力分申报：通过、改分或驳回。',
  admin: '学年与规则、账号导入、成绩表导入、核算排名、公示与异议。',
}

const entries = computed(() =>
  appRoutes.filter(
    (r) =>
      r.meta?.menu && r.name !== 'home' && (!r.meta.roles || auth.hasRole(...(r.meta.roles ?? []))),
  ),
)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>你好，{{ auth.user?.name }}</h2>
      <span class="muted">{{ auth.user?.class_name }}</span>
    </div>
    <el-row :gutter="16">
      <el-col v-for="entry in entries" :key="String(entry.name)" :xs="24" :sm="12" :md="8">
        <RouterLink :to="{ name: entry.name }" class="card-link">
          <el-card shadow="hover" class="entry">
            <h3>{{ entry.meta?.title }}</h3>
            <p class="muted">{{ DESCRIPTIONS[String(entry.name)] }}</p>
          </el-card>
        </RouterLink>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.card-link {
  text-decoration: none;
}

.entry {
  margin-bottom: 16px;
  min-height: 120px;
}

.entry h3 {
  margin: 0 0 8px;
  color: var(--el-color-primary);
}
</style>
