<script setup lang="ts">
import { ref } from 'vue'

import AdminCollege from './admin/AdminCollege.vue'
import AdminPublications from './admin/AdminPublications.vue'
import AdminScores from './admin/AdminScores.vue'
import AdminUsers from './admin/AdminUsers.vue'
import AdminYears from './admin/AdminYears.vue'

const tab = ref('years')
</script>

<template>
  <div class="page">
    <div class="page-header"><h2>管理后台</h2></div>
    <el-tabs v-model="tab">
      <el-tab-pane label="学年与规则" name="years" lazy><AdminYears /></el-tab-pane>
      <el-tab-pane label="账号" name="users" lazy><AdminUsers /></el-tab-pane>
      <el-tab-pane label="成绩表导入" name="college" lazy><AdminCollege /></el-tab-pane>
      <el-tab-pane label="核算与排名" name="scores" lazy><AdminScores /></el-tab-pane>
      <el-tab-pane label="公示与异议" name="publications" lazy><AdminPublications /></el-tab-pane>
    </el-tabs>
  </div>
</template>
