<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, ref, watch } from 'vue'

import { type Schemas, unwrap } from '@/api/client'
import ScoreItems, { type ScoreItem } from '@/components/ScoreItems.vue'
import YearSelect from '@/components/YearSelect.vue'
import { useAuthStore } from '@/stores/auth'
import { useYearStore } from '@/stores/year'
import { errorMessage } from '@/utils/errors'
import { formatTime, scoreText } from '@/utils/format'
import { loadRuleNames } from '@/utils/rules'

const auth = useAuthStore()
const years = useYearStore()
const score = ref<Schemas['StoredScoreOut'] | null>(null)
const names = ref<Record<string, string>>({})
const loading = ref(false)

const items = computed(() => (score.value?.detail.items as ScoreItem[] | undefined) ?? [])

async function load(): Promise<void> {
  score.value = null
  if (years.selectedId === null) return
  loading.value = true
  try {
    const rows = unwrap(
      await auth.api.GET('/api/v1/years/{year_id}/scores', {
        params: { path: { year_id: years.selectedId } },
      }),
    )
    score.value = rows.find((r) => r.student_username === auth.user?.username) ?? null
    if (score.value) names.value = await loadRuleNames(score.value.rule_version_id)
  } catch (e) {
    ElMessage.error(errorMessage(e))
  } finally {
    loading.value = false
  }
}

watch(() => years.selectedId, load, { immediate: true })
</script>

<template>
  <div v-loading="loading" class="page">
    <div class="page-header">
      <h2>我的成绩</h2>
      <YearSelect />
    </div>
    <el-empty v-if="!score && !loading" description="学院尚未核算本学年成绩" />
    <template v-if="score">
      <el-descriptions :column="2" border class="summary">
        <el-descriptions-item label="综合测评成绩">
          <strong class="score final" data-testid="my-final">{{ score.final_score }}</strong>
        </el-descriptions-item>
        <el-descriptions-item label="学业水平（GPA）">{{ score.gpa }}</el-descriptions-item>
        <el-descriptions-item label="综合素质评价">{{ score.quality_total }}</el-descriptions-item>
        <el-descriptions-item label="思想品德行为习惯">
          {{ scoreText(score.moral_total) }}
        </el-descriptions-item>
        <el-descriptions-item label="综合能力表现">
          {{ scoreText(score.competence_total) }}
        </el-descriptions-item>
        <el-descriptions-item label="其中能力分">{{ score.ability_total }}</el-descriptions-item>
      </el-descriptions>
      <p class="muted">核算时间：{{ formatTime(score.computed_at) }}</p>
      <h3>计分明细</h3>
      <ScoreItems :items="items" :names="names" />
    </template>
  </div>
</template>

<style scoped>
.summary {
  margin-bottom: 8px;
}

.final {
  font-size: 20px;
  color: var(--el-color-primary);
}
</style>
